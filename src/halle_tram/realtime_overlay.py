"""
Applies GTFS-RT TripUpdates on top of scheduled departures. 
All departures for stations other than the first station of a trip are in the past otherwise.

Two situations are handled:
  1. The feed has an update for exactly our stop  -> use its predicted time.
  2. The feed only has updates for *earlier* stops of the trip -> GTFS-RT says a
     delay carries over to later stops, so we reuse the latest known delay.
If the trip isn't in the feed at all, the departure stays "scheduled".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from google.transit import gtfs_realtime_pb2

_TRIP_CANCELED = gtfs_realtime_pb2.TripDescriptor.CANCELED
_STOP_SKIPPED = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.SKIPPED

EXACT_TOLERANCE_S = 300          # feed's scheduled time for our stop vs. ours
PROPAGATION_MAX_S = 3 * 3600     # don't carry a delay over more than 3 h of trip


@dataclass
class RtStop:
    stop_id: str
    time: int | None   # predicted unix timestamp, None if the update has no absolute time
    delay: int         # seconds
    skipped: bool


@dataclass
class RtTrip:
    start_date: str | None   # service day, YYYYMMDD
    canceled: bool
    stops: list[RtStop] = field(default_factory=list)   # in trip order


@dataclass
class Overlay:
    status: str          # "realtime" | "scheduled" | "cancelled"
    predicted_ts: float
    delay: int


def _predicted(stu) -> tuple[int | None, int]:
    for name in ("departure", "arrival"):
        if stu.HasField(name):
            part = getattr(stu, name)
            if part.time:
                return part.time, part.delay
    return None, 0


def index_trip_updates(feed, trip_ids: set[str]) -> dict[str, list[RtTrip]]:
    """Collect all updates of the given trips (all their stops, not just ours)."""
    result: dict[str, list[RtTrip]] = {}
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        if tu.trip.trip_id not in trip_ids:
            continue

        rt = RtTrip(
            start_date=tu.trip.start_date or None,
            canceled=tu.trip.schedule_relationship == _TRIP_CANCELED,
        )
        for stu in tu.stop_time_update:
            t, delay = _predicted(stu)
            rt.stops.append(
                RtStop(
                    stop_id=stu.stop_id,
                    time=t,
                    delay=delay,
                    skipped=stu.schedule_relationship == _STOP_SKIPPED,
                )
            )
        result.setdefault(tu.trip.trip_id, []).append(rt)
    return result


def overlay(sched_ts: float, day: str, platform_ids: set[str], rt_trips: list[RtTrip]) -> Overlay:
    for rt in rt_trips:
        # The same trip_id runs every day; only use updates for this service day.
        if rt.start_date and rt.start_date != day:
            continue
        if rt.canceled:
            return Overlay("cancelled", sched_ts, 0)

        # 1) update for exactly our stop
        for st in rt.stops:
            if st.stop_id not in platform_ids:
                continue
            if st.skipped:
                return Overlay("cancelled", sched_ts, 0)
            if st.time is not None and abs(st.time - st.delay - sched_ts) <= EXACT_TOLERANCE_S:
                return Overlay("realtime", st.time, int(st.time - sched_ts))

        # 2) delay propagation from the latest earlier stop
        best = None
        for st in rt.stops:
            if st.time is None or st.skipped:
                continue
            if st.time - st.delay <= sched_ts + 1:   # that stop is scheduled before ours
                best = st
        if best is not None and sched_ts - (best.time - best.delay) <= PROPAGATION_MAX_S:
            return Overlay("realtime", sched_ts + best.delay, best.delay)

    return Overlay("scheduled", sched_ts, 0)