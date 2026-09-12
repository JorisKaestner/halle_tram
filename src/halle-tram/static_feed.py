import requests
import pandas
from pathlib import Path

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "halle_tram"
STATIC_FIELD_URL = "https://download.gtfs.de/germany/nv_free/latest.zip"

class StaticFeed:
    def __init__(self, cache_dir = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir
        self.extract_dir = self.cache_dir / "gtfs_static"
        self.zip_path = self.cache_dir / "latest.zip"
        self._stops = None
        self._trips = None
        self._routes = None

    # check if zip is older than 24 hours
    def _isStale(self) -> bool:
        pass

    # redownload feed and extract if stale
    def refresh_feed(self, force:bool = False):
        pass

    # get platform id from station name
    def resolve_platform_id():
        pass

    def trip_info():
        pass