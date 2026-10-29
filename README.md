# halle_tram

This package is designed to access public german GTFS data, to get upcoming departures of tram and bus stations. Although this tool was created to access the tram schedule of Halle (Saale) specifically, it is applicable to all available stations of the [german GTFS feed](https://gtfs.de/de/realtime/)

## Features

- get departures for a named station, including line and destination
- get live delays from realtime data, with a fallback to the timetable

## How it works

On start-up the [static GTFS timetable](https://download.gtfs.de/germany/nv_free/latest.zip) gets downloaded and cached. On each lookup of departures, the [realtime GTFS feed](https://realtime.gtfs.de/realtime-free.pb) gets accessed to compare station names and delays between scheduled and current departures.

## Installation

Requires Python 3.10 or newer.

```bash
pip install git+https://github.com/JorisKaestner/halle_tram.git
```

## Quick start

Small usage example:

```python
from halle_tram import DepartureBoard

board = DepartureBoard("Halle (Saale), Rannischer Platz")
for departure in board.get_departures(limit=8):
    print(departure)
```

Example Output:
```
12:18    8  Elsa-Brändström-Straße (+3min)
12:19    1  Südstadt, Veszpremer Straße
12:20    3  Trotha (+1min)
12:23    1  Gertraudenfriedhof
``` 

**First run:**
On the first run, the static timetable gets downloaded which is ~200MB and cached at "~/.cache/halle_tram", so this action is very costly. The default cache path can be edited in config.py.

The realtime GTFS lookup of `get_departures()`is cheaper and should be executed every 30-60 seconds for a live display.

## Usage

The API exposes only `DepartureBoard` and `Departure` for now:

```python
DepartureBoard(
    station_name: str, 
    static_feed: StaticFeed | None = None, 
    cache_dir: Path | str = DEFAULT_CACHE_DIR)

@dataclass
class Departure:
    line: str | None
    destination: str | None
    time: datetime
    delay_seconds: int
    is_realtime: bool
```

**Usage example**
Create a self refreshing display for the station "Halle (Saale), Rannischer Platz". Fetch the first 8 departures within the next hour:

```python
import time
from halle_tram import DepartureBoard

board = DepartureBoard("Halle (Saale), Rannischer Platz")
while True:
    board.refresh()
    for dep in board.get_departures(limit=8, ahead_minutes=60):
        print(dep)
    print("-" * 20)
    time.sleep(30)
```

`board.refresh()` redownloads the static timetable, only if it has gone stale (older than 24h). Use `board.refresh(forced=True)` to refresh anyway.

## Finding your station name

The station name needs to match exactly to resolve the platform IDs. You will need to find the name of a parent station. Parent stations usually don't have departures scheduled, unless they are direct stations. When using the name of the parent station, all child platform IDs get resolved automatically.

Open "stops.txt" from your cache. (Create an empty DepartureBoard to download, if needed). Search for your station name in in the first coloumn "stop_name". Check if it is a parent station in the second last coloumn ("location_type" == 1).

The parent station names are unique in this dataset, but often share names with their platforms. You can also use the name of a child stop directly, but all stops with the same name get merged as one station. 

## Data sources

- Static timetable: "https://download.gtfs.de/germany/nv_free/latest.zip"
- Realtime data: "https://realtime.gtfs.de/realtime-free.pb"
- License / attribution: [Creative Commons 4.0](https://creativecommons.org/licenses/by/4.0/)

## Development

Install the environment to run from source:

```bash
git clone https://github.com/JorisKaestner/halle_tram.git
cd [repo-name]
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Disclaimer

This is a hobby project for personal use. I can not guarantee the correctness of any outputs or calculations. This software is neither fast nor secure enough to be used in critical applications.

## License

MIT, see [LICENSE](LICENSE).