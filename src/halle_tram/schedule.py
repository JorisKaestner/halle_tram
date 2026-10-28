"""
Builds a small, station-specific timetable out of the huge static GTFS files.

The expensive part (scanning stop_times.txt) runs once per static-feed
refresh; the result is cached on disk and kept in memory at runtime.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_STOP_TIME_COLS = {
    "trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence",
    "stop_headsign", "pickup_type",
}


def parse_gtfs_time(value: str) -> int:
    """'08:05:30' -> seconds since the start of the service day.
    GTFS allows hours >= 24 for trips running past midnight ('25:10:00')."""
    h, m, s = value.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


@dataclass
class ScheduleData:
    """Scheduled departures at one station plus the calendar needed to know
    which service days they run on.

    table columns: trip_id, stop_id, seq, dep_secs, service_id, line, destination
    """

    table: pd.DataFrame
    calendar: pd.DataFrame | None
    calendar_dates: pd.DataFrame | None

    def active_service_ids(self, day: date) -> set[str]:
        ymd = day.strftime("%Y%m%d")
        active: set[str] = set()

        if self.calendar is not None:
            c = self.calendar
            mask = (c[_WEEKDAYS[day.weekday()]] == "1") & (c["start_date"] <= ymd) & (c["end_date"] >= ymd)
            active = set(c.loc[mask, "service_id"])

        if self.calendar_dates is not None:
            d = self.calendar_dates[self.calendar_dates["date"] == ymd]
            active |= set(d.loc[d["exception_type"] == "1", "service_id"])
            active -= set(d.loc[d["exception_type"] == "2", "service_id"])

        return active

    def departures_between(self, start_ts: float, end_ts: float, tz: ZoneInfo) -> pd.DataFrame:
        """All scheduled departures with start_ts <= time <= end_ts.

        Adds columns: sched_ts (unix timestamp) and day (service day, YYYYMMDD).
        We look at the service days around the window, because a trip that
        belongs to yesterday's service day can depart after midnight
        (dep_secs >= 86400).
        """
        first_day = datetime.fromtimestamp(start_ts, tz).date() - timedelta(days=1)
        last_day = datetime.fromtimestamp(end_ts, tz).date()

        parts = []
        day = first_day
        while day <= last_day:
            services = self.active_service_ids(day)
            sub = self.table[self.table["service_id"].isin(services)]
            if not sub.empty:
                # GTFS defines times relative to "noon minus 12h" of the service
                # day, which stays correct on days with a DST change.
                base = datetime.combine(day, dtime(12, 0), tzinfo=tz).timestamp() - 12 * 3600
                ts = base + sub["dep_secs"]
                mask = (ts >= start_ts) & (ts <= end_ts)
                part = sub[mask].copy()
                part["sched_ts"] = ts[mask]
                part["day"] = day.strftime("%Y%m%d")
                parts.append(part)
            day += timedelta(days=1)

        if not parts:
            return self.table.iloc[0:0].assign(sched_ts=pd.Series(dtype=float), day=pd.Series(dtype=str))
        return pd.concat(parts, ignore_index=True)


def _read_optional(path: Path, service_ids: set[str]) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, dtype=str)
    return df[df["service_id"].isin(service_ids)].reset_index(drop=True)


def build_schedule(static_dir: Path, platform_ids: set[str], chunksize: int = 500_000) -> ScheduleData:
    """Scan stop_times.txt once in chunks and keep
    only the rows at our platforms"""
    static_dir = Path(static_dir)

    hits = []
    for chunk in pd.read_csv(
        static_dir / "stop_times.txt",
        dtype=str,
        usecols=lambda c: c in _STOP_TIME_COLS,
        chunksize=chunksize,
    ):
        hit = chunk[chunk["stop_id"].isin(platform_ids)]
        if "pickup_type" in hit:
            # pickup_type 1 = no boarding here. usually final stop
            hit = hit[hit["pickup_type"] != "1"]
        if not hit.empty:
            hits.append(hit)

    columns = ["trip_id", "stop_id", "seq", "dep_secs", "service_id", "line", "destination"]
    if not hits:
        return ScheduleData(pd.DataFrame(columns=columns), None, None)

    at_stop = pd.concat(hits, ignore_index=True)

    dep = at_stop["departure_time"] if "departure_time" in at_stop else at_stop["arrival_time"]
    if "departure_time" in at_stop and "arrival_time" in at_stop:
        dep = dep.fillna(at_stop["arrival_time"])
    at_stop = at_stop.assign(dep=dep).dropna(subset=["dep"])
    at_stop["dep_secs"] = at_stop["dep"].map(parse_gtfs_time)
    at_stop["seq"] = pd.to_numeric(at_stop["stop_sequence"])
    at_stop["destination"] = at_stop["stop_headsign"] if "stop_headsign" in at_stop else None

    trip_ids = set(at_stop["trip_id"])
    trips = pd.read_csv(static_dir / "trips.txt", dtype=str, usecols=["trip_id", "route_id", "service_id"])
    trips = trips[trips["trip_id"].isin(trip_ids)]
    routes = pd.read_csv(static_dir / "routes.txt", dtype=str, usecols=["route_id", "route_short_name"])

    table = (
        at_stop.merge(trips, on="trip_id")
        .merge(routes, on="route_id", how="left")
        .rename(columns={"route_short_name": "line"})[columns]
        .reset_index(drop=True)
    )

    sids = set(table["service_id"])
    return ScheduleData(
        table=table,
        calendar=_read_optional(static_dir / "calendar.txt", sids),
        calendar_dates=_read_optional(static_dir / "calendar_dates.txt", sids),
    )


def load_schedule(
    static_dir: Path, zip_path: Path, platform_ids: set[str], cache_dir: Path
) -> ScheduleData:
    """build_schedule() with an on-disk cache that is invalidated whenever
    the static feed zip is newer than the cached schedule."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(",".join(sorted(platform_ids)).encode()).hexdigest()[:12]
    cache = cache_dir / f"schedule_{key}.pkl"

    if cache.exists() and cache.stat().st_mtime >= Path(zip_path).stat().st_mtime:
        return pd.read_pickle(cache)

    data = build_schedule(static_dir, platform_ids)
    pd.to_pickle(data, cache)
    return data