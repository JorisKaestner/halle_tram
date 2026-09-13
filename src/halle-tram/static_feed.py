import requests
import os
import time
from zipfile import ZipFile
from pathlib import Path

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "halle_tram"
STATIC_FEED_URL = "https://download.gtfs.de/germany/nv_free/latest.zip"

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
        if (not Path(self.zip_path).exists()):
            return True
        modify_time = int(os.path.getmtime(self.zip_path))  # in seconds since epoch
        hours_elapsed = int((time.time() - modify_time)/3600)
        return hours_elapsed>24

    # redownload feed and extract if stale
    def refresh_feed(self, force:bool = False):
        # do nothing if not stale
        if (not force and not self._isStale()):
            return

        # download static feed zip file
        print(f"Downloading static feed from {STATIC_FEED_URL} ...")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        resp = requests.get(STATIC_FEED_URL, timeout=120)
        resp.raise_for_status()
        self.zip_path.write_bytes(resp.content)

        # extract zip
        print(f"Extracting files to {self.cache_dir}...")
        with ZipFile(self.zip_path) as zFile:
            zFile.extractall(self.extract_dir)

        # Reset dataframes to force reload
        self._stops = self._trips = self._routes = None


    # get platform id from station name
    def resolve_platform_id():
        pass

    def trip_info():
        pass

feed = StaticFeed()
feed.refresh_feed(force=True)