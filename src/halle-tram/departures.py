from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from static_feed import StaticFeed
from realtime_feed import fetch_feed, get_stop_time_updates
from config import DEFAULT_CACHE_DIR, TIMEZONE
import time

@dataclass
class Departure:
    line: str | None
    time: datetime
    delay_seconds: int

    def __str__(self) -> str:
        delay = f" (+{int(self.delay_seconds/60)}min)" if self.delay_seconds and self.delay_seconds>60 else ""
        return f"{self.time:%H:%M}  Line {self.line or '?'} {delay}"

_static_feed = StaticFeed()

def get_departures(
    station_name: str,
    limit: int = 10,
    cache_dir=DEFAULT_CACHE_DIR,
) -> list[Departure]:
    """Fetch the next upcoming departures for station_name

    Downloads/refreshes the static feed automatically when it's missing
    or stale (see config.STATIC_MAX_AGE_HOURS), and always fetches a
    fresh copy of the realtime feed.
    """
    static = _static_feed
    static.refresh_feed()   # executes only if stale

    platform_ids = static.resolve_platform_ids(station_name)

    feed = fetch_feed()

    raw_updates = get_stop_time_updates(feed, platform_ids)
    now = time.time()

    tz = ZoneInfo(TIMEZONE)
    departures = []
    for update in raw_updates:
        if(time.time() > update.departure_time):    # skip departures in past
            continue
        line= static.trip_info(update.trip_id)
        departures.append(
            Departure(
                line=line,
                time=datetime.fromtimestamp(update.departure_time, tz=tz),
                delay_seconds=update.delay,
            )
        )

    departures.sort(key=lambda d: d.time)
    return departures[:limit]
