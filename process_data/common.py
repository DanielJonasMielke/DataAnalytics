"""Shared settings and helpers for the download scripts in process_data/."""

import argparse
import time
from pathlib import Path

import dynamical_catalog
import pandas as pd

# --- Settings used by all download scripts ---
REPO_ROOT = Path(__file__).resolve().parent.parent  # folder above process_data/
DATA_DIR = REPO_ROOT / "data"

# The single location: DWD station Hamburg-Fuhlsbüttel
STATION_ID = "01975"
STATION_LAT, STATION_LON = 53.6332, 9.9881  # degrees north / east

# Time window: first AIFS Single forecast until today
START = pd.Timestamp("2024-04-01")
END = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()  # today, 00:00 UTC

VARIABLES = ["temperature_2m", "precipitation_surface"]  # names in the dynamical.org datasets


def parse_limit(description):
    """Read the optional command line flag --limit N (quick test run)."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--limit", type=int, default=None, help="only download the first N missing forecasts")
    return parser.parse_args()


def done_init_times(csv_path):
    """Forecast start times already in the CSV, so a re-run skips them."""
    if not csv_path.exists():
        return set()
    column = pd.read_csv(csv_path, usecols=["init_time"], parse_dates=["init_time"])["init_time"]
    return set(column)


def append_csv(df, csv_path):
    """Add rows to the CSV; write the column names only for a new file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, mode="a", header=not csv_path.exists(), index=False)


def print_csv_summary(csv_path):
    df = pd.read_csv(csv_path)
    print(f"\nDone: {csv_path} ({len(df)} rows)")
    print(f"Forecasts: {df['init_time'].nunique()} from {df['init_time'].min()} to {df['init_time'].max()}")


def download_dynamical_point(dataset_name, out_csv, member=None, limit=None, batch_size=20):
    """Download temperature + precipitation at the station for every 00 UTC forecast in the window.

    Values stay as in the archive: temperature in degree Celsius, precipitation as a
    rate in kg m-2 s-1 (= mm/s, averaged since the previous step). All lead times are kept.
    The CSV grows batch by batch, so an interrupted run can simply be started again.
    """
    ds = dynamical_catalog.open(dataset_name, chunks=None)  # opens lazily, nothing downloaded yet

    # Start times to download: 00 UTC, in window, new
    all_inits = pd.DatetimeIndex(ds["init_time"].values)
    inits = all_inits[(all_inits.hour == 0) & (all_inits >= START) & (all_inits <= END)]
    done = done_init_times(out_csv)
    todo = [t for t in inits if t not in done][:limit]  # limit=None keeps all
    print(f"{len(inits)} forecasts in the window, {len(done)} already downloaded, {len(todo)} to do.")
    if not todo:
        return

    point = ds[VARIABLES]
    if member is not None:
        point = point.sel(ensemble_member=member)  # IFS: member 0 = control run
    point = point.sel(latitude=STATION_LAT, longitude=STATION_LON, method="nearest")  # closest grid point
    print(f"Grid point used: {float(point.latitude):.2f}°N, {float(point.longitude):.2f}°E")

    started = time.time()
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        loaded = point.sel(init_time=batch).load()  # the download happens here
        df = loaded.to_dataframe().reset_index()  # table: one row per forecast and lead time

        df["lead_time_h"] = df.pop("lead_time") / pd.Timedelta(hours=1)  # lead time in hours
        df = df.drop(columns=["spatial_ref", "expected_forecast_length", "ingested_forecast_length"], errors="ignore")  # unused extras
        first = ["init_time", "lead_time_h", "valid_time"]
        df = df[first + [c for c in df.columns if c not in first]]  # key columns first

        append_csv(df, out_csv)
        print(f"  {i + len(batch)}/{len(todo)} forecasts done, {time.time() - started:.0f} s elapsed")

    print_csv_summary(out_csv)
