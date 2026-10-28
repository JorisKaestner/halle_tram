from dataclasses import dataclass
import requests
from google.transit import gtfs_realtime_pb2
from .config import REALTIME_FEED_URL

@dataclass
class RawStopTimeUpdate:
    trip_id: str
    route_id: str | None
    stop_id: str
    departure_time: int  # unix timestamp
    delay: int  # seconds

def fetch_feed() -> gtfs_realtime_pb2.FeedMessage:
    response = requests.get(REALTIME_FEED_URL, timeout=30)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed

def get_stop_time_updates(
    feed: gtfs_realtime_pb2.FeedMessage, stop_ids: set[str]
) -> list[RawStopTimeUpdate]:
    """Extract every stop_time_update in the feed matching one of stop_ids."""
    results: list[RawStopTimeUpdate] = []

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update

        for stoptime in tu.stop_time_update:
            if stoptime.stop_id not in stop_ids:
                continue
            if not stoptime.HasField("departure"):
                continue

            results.append(
                RawStopTimeUpdate(
                    trip_id=tu.trip.trip_id,
                    route_id=tu.trip.route_id or None,
                    stop_id=stoptime.stop_id,
                    departure_time=stoptime.departure.time,
                    delay=stoptime.departure.delay,
                )
            )
    return results
