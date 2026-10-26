from pathlib import Path

STATIC_FEED_URL = "https://download.gtfs.de/germany/nv_free/latest.zip"
REALTIME_FEED_URL = "https://realtime.gtfs.de/realtime-free.pb"

# cahing location of large static feed
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "halle_tram"
STATIC_MAX_AGE_HOURS = 24

TIMEZONE = "Europe/Berlin"