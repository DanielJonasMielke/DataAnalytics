"""Download GraphCast (Google's AI model, started from ECMWF's IFS initial state) at the station.

Source:   NOAA/CIRA "AI Weather Prediction (AIWP) model reforecasts" on AWS (public bucket, no account needed)
          s3://noaa-oar-mlwp-data/GRAP_vNNN_IFS/YYYY/mmdd/GRAP_vNNN_IFS_YYYYmmddhh_f000_f240_06.nc
Content:  2 m temperature (t2) + 6 h precipitation (apcp), every forecast started at 00 UTC from 2024-04-01
          until today, all lead times (+0 h to +240 h in 6 h steps), grid point nearest to the station
Output:   data/graphcast/graphcast_ifs_hamburg_t2m_precip.csv
          data/graphcast/graphcast_missing_inits.txt  (start times for which no file exists in the archive)

Each file is one *global* forecast. We read it remotely and fetch only the bytes of the
nearest grid point, so the whole file is never downloaded. Raw units: Kelvin and metres.

Run:      uv run ./process_data/03_download_graphcast_data.py --limit 3   (test with 3 forecasts first!)
          uv run ./process_data/03_download_graphcast_data.py             (everything, can be stopped and restarted)
"""

import argparse
import time
import urllib.error
import urllib.request
from concurrent.futures import ProcessPoolExecutor

import fsspec
import pandas as pd
import xarray as xr
from common import DATA_DIR, END, START, STATION_LAT, STATION_LON, append_csv, done_init_times, print_csv_summary

BUCKET_URL = "https://noaa-oar-mlwp-data.s3.amazonaws.com"
PREFIXES = ["GRAP_v200_IFS", "GRAP_v100_IFS"]  # GraphCast folders; first with the file wins
OUT_DIR = DATA_DIR / "graphcast"
OUT_CSV = OUT_DIR / "graphcast_ifs_hamburg_t2m_precip.csv"
MISSING_TXT = OUT_DIR / "graphcast_missing_inits.txt"


def find_file(init):
    """Return (folder, url) of the file for this forecast start time, or None if the archive has none."""
    for prefix in PREFIXES:
        url = f"{BUCKET_URL}/{prefix}/{init:%Y}/{init:%m%d}/{prefix}_{init:%Y%m%d%H}_f000_f240_06.nc"
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="HEAD"))  # only asks if the file exists
            return prefix, url
        except urllib.error.HTTPError:  # file not in this folder
            pass
    return None


def fetch_one(init):
    """Read one forecast at the station. Runs in a worker process. Returns (init, folder, table)."""
    found = find_file(init)
    if found is None:
        return init, None, None
    prefix, url = found

    with fsspec.open(url, "rb", block_size=4 * 2**20, cache_type="blockcache") as f:  # read remotely in 4 MB blocks
        with xr.open_dataset(f, engine="h5netcdf") as ds:
            point = ds[["t2", "apcp"]].sel(latitude=STATION_LAT, longitude=STATION_LON, method="nearest")  # closest grid point
            df = point.load().to_dataframe().reset_index()  # table: one row per lead time
    return init, prefix, df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="only download the first N missing forecasts")
    parser.add_argument("--workers", type=int, default=4, help="forecasts downloaded at the same time (default 4)")
    args = parser.parse_args()

    all_inits = pd.date_range(START, END, freq="D")  # one 00 UTC forecast per day
    done = done_init_times(OUT_CSV)
    todo = [t for t in all_inits if t not in done][: args.limit]  # limit=None keeps all
    print(f"{len(all_inits)} days in the window, {len(done)} already downloaded, {len(todo)} to do.")

    missing = []
    started = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:  # runs fetch_one for several days at once
        for n, (init, prefix, df) in enumerate(pool.map(fetch_one, todo), start=1):
            if df is None:
                missing.append(init)
                print(f"  {init:%Y-%m-%d}: no file in the archive")
                continue
            df.insert(0, "init_time", init)
            df.insert(1, "s3_prefix", prefix)  # which GraphCast folder (version) the data came from
            append_csv(df, OUT_CSV)
            print(f"  {init:%Y-%m-%d} done ({n}/{len(todo)}), {time.time() - started:.0f} s elapsed")

    if missing:
        MISSING_TXT.write_text("\n".join(f"{t:%Y-%m-%d}" for t in missing) + "\n")
        print(f"\n{len(missing)} start times have no file; listed in {MISSING_TXT}")
    print_csv_summary(OUT_CSV)


if __name__ == "__main__":  # required: the worker processes import this file on Windows
    main()
