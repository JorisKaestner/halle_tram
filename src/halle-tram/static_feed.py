import requests
import os
import time
import pandas as pd
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

    ## data frames ##

    @property
    def stops(self) -> pd.DataFrame:
        if self._stops is None:
            self._stops = pd.read_csv(self.extract_dir / "stops.txt", dtype=str)
        return self._stops

    @property
    def trips(self) -> pd.DataFrame:
        if self._trips is None:
            self._trips = pd.read_csv(self.extract_dir / "trips.txt", dtype=str).set_index("trip_id")
        return self._trips

    @property
    def routes(self) -> pd.DataFrame:
        if self._routes is None:
            self._routes = pd.read_csv(self.extract_dir / "routes.txt", dtype=str).set_index("route_id")
        return self._routes

    def resolve_platform_ids(self, station_name:str) -> set[str]:
        """Get a set of platform IDs from a station name"""
        stops = self.stops
        station = stops[(stops["stop_name"] == station_name) & (stops["location_type"] == "1")]

        if station.empty:
            # check if stop is a direct stop without child platform
            direct_stops = stops[(stops["stop_name"] == station_name)]
            if direct_stops.empty:
                raise ValueError(f"No stop with name '{station_name}'")
            return set(direct_stops["stop_id"])

        station_id = station.iloc[0]["stop_id"]
        platforms = stops[(stops["parent_station"] == station_id) & (stops["location_type"] == "0")]
        return set(platforms["stop_id"])

    def search_station_names(self, keyword:str) -> set[str]:
        """Get a set of station names which contain the keyword (case-insensitive)"""
        stations = self.stops[self.stops["stop_name"].str.contains(keyword, case=False)]
        return set(stations["stop_name"].tolist())

    def trip_info(self, trip_id: str) -> tuple[str | None, str | None]:
        if trip_id not in self.trips.index:
            return None, None
        trip_row = self.trips.loc[trip_id]
        route_id = trip_row.get("route_id")
        line = self.routes.loc[route_id].get("route_short_name") if route_id in self.routes.index else None
        return route_id, line

feed = StaticFeed()
feed.refresh_feed(force=False)
print(feed.resolve_platform_ids("Rannischer Platz"))