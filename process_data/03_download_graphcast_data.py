"""Download GraphCast (Google's AI model, started from ECMWF's IFS initial state) at the station.

Source:   NOAA/CIRA "AI Weather Prediction (AIWP) model reforecasts" on AWS (public bucket, no account needed)
          s3://noaa-oar-mlwp-data/GRAP_vNNN_IFS/YYYY/mmdd/GRAP_vNNN_IFS_YYYYmmddhh_f000_f240_06.nc
Content:  2 m temperature + precipitation, every forecast started at 00 UTC from 2024-04-01 until today,
          all lead times (+0 h to +240 h in 6 h steps), grid point nearest to the station
Output:   data/graphcast/graphcast_ifs_hamburg_t2m_precip.csv
          data/graphcast/graphcast_missing_inits.txt  (start times for which no file exists in the archive)

Each file is one *global* forecast. By default we do NOT download whole files: the file is read remotely
and only the bytes of the nearest grid point are fetched. If that is too slow or fails, use --full-download
(downloads each file to a temporary folder, takes the point, deletes the file again; needs much more bandwidth).

The variable names inside the files are detected automatically (and printed for the first file).
If detection picks the wrong ones, set them with --temp-var / --precip-var.

Run:      uv run ./process_data/03_download_graphcast_data.py --limit 3   (test with 3 forecasts first!)
          uv run ./process_data/03_download_graphcast_data.py             (everything, can be stopped and restarted)
"""

import argparse
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import fsspec
import pandas as pd
import xarray as xr
from common import (
    DATA_DIR,
    END,
    START,
    STATION_LAT,
    STATION_LON,
    append_csv,
    done_init_times,
    print_csv_summary,
    with_retries,
)

DEFAULT_BUCKET_URL = "https://noaa-oar-mlwp-data.s3.amazonaws.com"
FALLBACK_PREFIXES = ["GRAP_v100_IFS", "GRAP_v200_IFS"]
OUT_DIR = DATA_DIR / "graphcast"
OUT_CSV = OUT_DIR / "graphcast_ifs_hamburg_t2m_precip.csv"
MISSING_TXT = OUT_DIR / "graphcast_missing_inits.txt"

# Names we look for inside the netCDF files (first match wins)
TEMP_CANDIDATES = ["t2", "t2m", "2t", "temperature_2m"]
PRECIP_CANDIDATES = [
    "apcp",  # name in the real files: 6-hour accumulated precipitation
    "tp",
    "tp6",
    "tp6h",
    "tp_6h",
    "precip",
    "precipitation",
    "total_precipitation_6hr",
    "total_precipitation",
]

_printed_structure = False  # print the file structure only once


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="only download the first N missing forecasts")
    parser.add_argument("--workers", type=int, default=4, help="forecasts downloaded at the same time (default 4; 1 = one by one)")
    parser.add_argument("--full-download", action="store_true", help="download whole files instead of remote reading")
    parser.add_argument("--prefix", default=None, help="use only this folder, e.g. GRAP_v100_IFS (default: auto)")
    parser.add_argument("--temp-var", default=None, help="name of the 2 m temperature variable in the files")
    parser.add_argument("--precip-var", default=None, help="name of the precipitation variable in the files")
    parser.add_argument("--bucket-url", default=DEFAULT_BUCKET_URL, help=argparse.SUPPRESS)  # for tests only
    return parser.parse_args()


def discover_prefixes(bucket_url):
    """Ask the bucket which GraphCast folders with IFS initial state exist (e.g. GRAP_v100_IFS)."""
    try:
        url = f"{bucket_url}/?list-type=2&delimiter=/&prefix=GRAP_"
        with urllib.request.urlopen(url, timeout=60) as response:
            root = ET.fromstring(response.read())
        namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        found = [e.text.rstrip("/") for e in root.findall(".//s3:CommonPrefixes/s3:Prefix", namespace)]
        prefixes = sorted((p for p in found if p.endswith("_IFS")), reverse=True)  # newer version first
        if prefixes:
            return prefixes
        print(f"WARNING: no GRAP_*_IFS folders found in the bucket listing (found: {found}).")
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: could not list the bucket ({error!r}).")
    print(f"Using the default folders {FALLBACK_PREFIXES} instead.")
    return FALLBACK_PREFIXES


def file_url(bucket_url, prefix, init):
    return f"{bucket_url}/{prefix}/{init:%Y}/{init:%m%d}/{prefix}_{init:%Y%m%d%H}_f000_f240_06.nc"


def file_exists(url):
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=60):
            return True
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):  # S3 answers 403 or 404 for a key that does not exist
            return False
        raise


def find_file(bucket_url, prefixes, init):
    """Return (folder, url) of the first folder that has a file for this start time, or None."""
    for prefix in prefixes:
        url = file_url(bucket_url, prefix, init)
        if with_retries(lambda: file_exists(url)):
            return prefix, url
    return None


def find_name(names, candidates):
    lookup = {str(n).lower(): n for n in names}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def extract_point(ds, args):
    """From an opened GraphCast file, take 2 m temperature + precipitation at the grid point nearest to the station."""
    global _printed_structure
    if not _printed_structure:
        print("\nStructure of the first file:")
        print(ds)
        print()
        _printed_structure = True

    lat_name = find_name(ds.variables, ["lat", "latitude"])
    lon_name = find_name(ds.variables, ["lon", "longitude"])
    temp_name = args.temp_var or find_name(ds.data_vars, TEMP_CANDIDATES)
    precip_name = args.precip_var or find_name(ds.data_vars, PRECIP_CANDIDATES)
    for given in (args.temp_var, args.precip_var):
        if given is not None and given not in ds.data_vars:
            raise SystemExit(f"Variable '{given}' does not exist in the file. Variables: {list(ds.data_vars)}")
    if lat_name is None or lon_name is None or temp_name is None:
        raise SystemExit(
            f"Could not find lat/lon/temperature in the file (found lat={lat_name}, lon={lon_name}, "
            f"temperature={temp_name}). Variables: {list(ds.data_vars)}. Use --temp-var / --precip-var."
        )
    if precip_name is None:
        print(f"WARNING: no precipitation variable detected, only temperature is saved. Variables: {list(ds.data_vars)}")

    lon_target = STATION_LON % 360 if float(ds[lon_name].max()) > 180 else STATION_LON  # grid may run 0..360
    chosen = [temp_name] + ([precip_name] if precip_name else [])
    point = ds[chosen].sel({lat_name: STATION_LAT, lon_name: lon_target}, method="nearest").load()
    df = point.to_dataframe().reset_index()

    for column in df.select_dtypes("timedelta").columns:  # e.g. a lead-time column -> hours
        df[column + "_h"] = df.pop(column) / pd.Timedelta(hours=1)
    return df


def read_point(url, args):
    if args.full_download:
        with tempfile.TemporaryDirectory() as tmp:
            local_path = Path(tmp) / "graphcast.nc"
            urllib.request.urlretrieve(url, local_path)
            with xr.open_dataset(local_path, engine="h5netcdf") as ds:
                return extract_point(ds, args)
    with fsspec.open(url, "rb", block_size=4 * 2**20, cache_type="blockcache") as f:
        with xr.open_dataset(f, engine="h5netcdf") as ds:
            return extract_point(ds, args)


def fetch_one(init, prefixes, args):
    """Find and read one forecast. Returns (init, folder, table); table is None if the archive has no file."""
    global _printed_structure
    if args.workers > 1:
        _printed_structure = True  # with several workers the structure printout would be repeated; skip it
    found = find_file(args.bucket_url, prefixes, init)
    if found is None:
        return init, None, None
    prefix, url = found
    df = with_retries(lambda: read_point(url, args), attempts=3, wait_seconds=15)
    return init, prefix, df


def main():
    args = parse_args()
    prefixes = [args.prefix] if args.prefix else discover_prefixes(args.bucket_url)
    print("GraphCast folders (IFS initial state):", prefixes)

    all_inits = pd.date_range(START, END, freq="D")  # one forecast per day, 00 UTC
    done = done_init_times(OUT_CSV)
    todo = [t for t in all_inits if t not in done]
    print(f"{len(all_inits)} days in the window, {len(done)} already downloaded, {len(todo)} to do.")

    downloaded, missing = 0, []
    started = time.time()

    def record(init, prefix, df):
        """Store one finished forecast (runs in the main process only, so the CSV is never written twice at once)."""
        nonlocal downloaded
        if df is None:
            missing.append(init)
            print(f"  {init:%Y-%m-%d}: no file in the archive")
            return
        df.insert(0, "init_time", init)
        df.insert(1, "s3_prefix", prefix)
        append_csv(df, OUT_CSV)
        downloaded += 1
        print(f"  {init:%Y-%m-%d} ({prefix}) done; {downloaded} downloaded, {time.time() - started:.0f} s elapsed")

    if args.workers <= 1:
        for init in todo:
            if args.limit is not None and downloaded >= args.limit:
                break
            record(*fetch_one(init, prefixes, args))
    else:
        print(f"Downloading {args.workers} forecasts at the same time.")
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            queue, pending = iter(todo), set()
            while True:
                # keep the workers busy, but never start more than --limit forecasts in total
                while len(pending) < args.workers and (args.limit is None or downloaded + len(pending) < args.limit):
                    init = next(queue, None)
                    if init is None:
                        break
                    pending.add(pool.submit(fetch_one, init, prefixes, args))
                if not pending:
                    break
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    record(*future.result())

    if missing:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        MISSING_TXT.write_text("\n".join(f"{t:%Y-%m-%d}" for t in missing) + "\n")
        print(f"\n{len(missing)} start times have no file; listed in {MISSING_TXT}")
    if OUT_CSV.exists():
        print_csv_summary(OUT_CSV)


if __name__ == "__main__":
    main()
