from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from config import DEFAULT_CACHE_DIR, TIMEZONE
from realtime_feed import fetch_feed
from realtime_overlay import index_trip_updates, overlay
from schedule import load_schedule
from static_feed import StaticFeed

LOOK_BACK_MIN = 30     # scheduled slots this far back are checked (delayed trams)
GRACE_S = 30           # keep a departure for this long after its predicted time


@dataclass
class Departure:
    line: str | None
    destination: str | None
    time: datetime
    delay_seconds: int
    is_realtime: bool

    def __str__(self) -> str:
        delay = f" (+{self.delay_seconds // 60}min)" if self.delay_seconds >= 60 else ""
        planned = "" if self.is_realtime else " (planned)"
        return f"{self.time:%H:%M}  {self.line or '?':>3}  {self.destination or '?'}{delay}{planned}"


class DepartureBoard:
    """Departures for one station. Create it once at startup and call
    get_departures() every 20-30 seconds."""

    def __init__(self, station_name: str, static_feed: StaticFeed | None = None,
                 cache_dir: Path | str = DEFAULT_CACHE_DIR):
        self.station_name = station_name
        self.cache_dir = Path(cache_dir)
        self.static = static_feed or StaticFeed()
        self.static.refresh_feed()
        self._load()

    def _load(self) -> None:
        self.platform_ids = self.static.resolve_platform_ids(self.station_name)
        self.schedule = load_schedule(
            self.static.extract_dir, self.static.zip_path, self.platform_ids, self.cache_dir
        )

    def refresh(self) -> None:
        """Re-download the static feed if stale and rebuild the timetable"""
        self.static.refresh_feed()
        self._load()

    def get_departures(self, limit: int = 10, ahead_minutes: int = 90,
                       now: float | None = None) -> list[Departure]:
        tz = ZoneInfo(TIMEZONE)
        now_ts = time.time() if now is None else now

        scheduled = self.schedule.departures_between(
            now_ts - LOOK_BACK_MIN * 60, now_ts + ahead_minutes * 60, tz
        )
        if scheduled.empty:
            return []

        # If the realtime feed is unreachable, fall back to the plain timetable.
        try:
            rt_index = index_trip_updates(fetch_feed(), set(scheduled["trip_id"]))
        except requests.RequestException:
            rt_index = {}

        result: list[Departure] = []
        for row in scheduled.itertuples():
            ov = overlay(row.sched_ts, row.day, self.platform_ids, rt_index.get(row.trip_id, []))
            if ov.status == "cancelled":
                continue
            if ov.predicted_ts < now_ts - GRACE_S:
                continue
            result.append(
                Departure(
                    line=row.line,
                    destination=row.destination,
                    time=datetime.fromtimestamp(ov.predicted_ts, tz=tz),
                    delay_seconds=ov.delay,
                    is_realtime=ov.status == "realtime",
                )
            )

        result.sort(key=lambda d: d.time)
        return result[:limit]

board = DepartureBoard("Rannischer Platz")
for b in board.get_departures(limit=8):
    print(b)