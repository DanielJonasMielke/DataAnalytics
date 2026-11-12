"""Download AIFS Single (ECMWF's AI model, single forecast) at the station.

Source:   dynamical.org catalog 'ecmwf-aifs-single-forecast' (ECMWF Open Data, CC BY 4.0)
Content:  2 m temperature + precipitation, every forecast started at 00 UTC from 2024-04-01 until today,
          all lead times (+0 h to +360 h in 6 h steps), grid point nearest to the station
Output:   data/aifs_single/aifs_single_hamburg_t2m_precip.csv

Run:      uv run ./process_data/02_download_aifs_data.py            (everything)
          uv run ./process_data/02_download_aifs_data.py --limit 5  (quick test with 5 forecasts)
"""

from common import DATA_DIR, download_dynamical_point, parse_limit

args = parse_limit(__doc__)

download_dynamical_point(
    dataset_name="ecmwf-aifs-single-forecast",
    out_csv=DATA_DIR / "aifs_single" / "aifs_single_hamburg_t2m_precip.csv",
    limit=args.limit,
)
