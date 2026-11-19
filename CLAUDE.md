# CLAUDE.md

Guide for LLM assistants working in this repository.

> **Keep this file up to date.** Whenever you change the codebase (new, renamed or deleted files, changed
> columns or units, new design decisions, finished or new next steps), update this file in the same change.
> If the change affects what users can do, update `README.md` too. Never leave this file describing an old state.

## Project in one paragraph

Student project for the course Data Analytics (M-Inf, HAW Hamburg, WiSe 2026/27, team of two). We compare **AI weather
models** (AIFS Single, GraphCast) with **physics models** (IFS control run, GFS) against **DWD station measurements** at
Hamburg-Fuhlsbüttel. Question: how does each model's error grow with lead time, how do AI and physics differ, and does
that depend on season, time of day or extremes (hypothesis: AI smooths extremes more). Variables: 2 m temperature and
precipitation only. The full project idea lives in the claude.ai project "Data Analytics" (doc "Project idea").

Course milestones: 20.11.2026 data preparation + exploratory analysis, 18.12.2026 modelling + evaluation,
22.01.2027 presentation.

## Fixed design decisions

- **Single forecasts only, no ensembles**
- **Station:** DWD 01975 Hamburg-Fuhlsbüttel (53.6332 N, 9.9881 E). All models use the nearest 0.25° grid point
  (53.75 N, 10.0 E, about 13 km away).
- **Time window:** 01.04.2024 (start of AIFS Single archive) until today.
- **Start time:** 00 UTC forecasts only.
- **Lead times for the comparison:** +6 h to +240 h in 6 h steps (GraphCast reaches 10 days only).
- **Initial state:** AIFS, IFS and GraphCast (IFS start) share ECMWF's initial state. GFS uses NOAA's own, so method and
  initial state are mixed for GFS. State this in the interpretation.
- **Time-of-day trap:** with 00 UTC starts, +12 h is always midday. Compare same-time-of-day lead times (+24 h, +48 h, ...)
  or plot one curve per time of day.
- **Model versions:** AIFS changed versions (test until 25.02.2025, v1, v1.1 on 27.08.2025, v2 on 12.05.2026 together with
  IFS Cycle 50r1). Undecided: keep a version column and split the evaluation, or ignore it. A quick check showed no
  visible jump in the monthly +24 h MAE at the change dates.
- **Precipitation timing (verified by correlation, AIFS/IFS/GFS/GraphCast vs DWD):** model values and DWD `R1` both refer to the interval *before* the
  timestamp. A 6 h window ending at t = DWD hours t-5 ... t.
- **Fair comparison:** only use the init days where all four models have a run (759 days; GraphCast has gaps).

## Current state

Full downloads are done (forecasts 01.04.2024 to 17./18.11.2026). The team copied all CSVs by hand into
`data/full_datasets/`, which is what the notebooks read; there the DWD precipitation file is named
`dwd_01975_rainfall_hourly.csv` (script 01 writes `..._precipitation_hourly.csv`).

Exploratory analysis is done in `explore_data/` (notebooks are in German, executed with outputs):
notebooks 01 to 05 look at each source alone (completeness, missing values, ranges, distributions, precipitation
units, findings at the end); notebook 06 is deliberately short: it unifies all models, joins them with DWD, shows per model a scatter
(day 2) and the temperature MAE by lead time, and compares all models on common days (MAE, share of wet windows).
Keep it short; the team wants only the essentials there. Notebook 06 writes the tidy table `data/prepared/forecasts_vs_dwd.csv`.

Main findings so far (common days): AIFS and GraphCast have the lowest temperature MAE at all lead times (about
0.9 °C at +24 h, 2.8 to 3.0 °C at +240 h), IFS is 0.1 to 0.4 °C worse, GFS worst. All models are too cold, most at
18 UTC. AI models predict light rain far too often (wet 6 h windows: AIFS 50 %, GraphCast 47 %, IFS 34 %, GFS 32 %,
DWD 23 %). A quick check (not in the notebooks) showed no clear sign that AI smooths temperature extremes, and
heavy rain is underestimated by all models.

## Codebase

Download code is in `process_data/`, exploration notebooks in `explore_data/`. Scripts run with `uv run ./process_data/<script>.py`. Scripts 02 to 05 also accept `--limit N` (first N forecasts); script 01 (DWD) has no `--limit` and always saves the full window.

| File                            | Purpose                                                                                                                                                         |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `common.py`                     | Settings (`STATION_ID`, `STATION_LAT/LON`, `START`, `END`, `VARIABLES`, `DATA_DIR`), `parse_limit`, and `download_dynamical_point()` used by scripts 02, 04, 05 |
| `01_download_dwd_data.py`       | Downloads DWD zips (`historical` and `recent`), merges them, writes two hourly CSVs                                                                             |
| `02_download_aifs_data.py`      | AIFS Single via dynamical.org                                                                                                                                   |
| `03_download_graphcast_data.py` | GraphCast from public S3 bucket `noaa-oar-mlwp-data`, parallel (`--workers`, default 4)                                                                         |
| `04_download_ifs_data.py`       | IFS ensemble member 0 (control run) via dynamical.org                                                                                                           |
| `05_download_gfs_data.py`       | GFS via dynamical.org                                                                                                                                           |

| Notebook (`explore_data/`)      | Purpose                                                                                       |
| ------------------------------- | --------------------------------------------------------------------------------------------- |
| `01_first_look_dwd.ipynb`       | DWD temperature, humidity, precipitation, quality levels                                      |
| `02_first_look_aifs.ipynb`      | AIFS completeness, temperature, precipitation in mm per 6 h                                   |
| `03_first_look_graphcast.ipynb` | GraphCast gaps per month, fill-value cleaning, Kelvin/metre conversion, negative precip       |
| `04_first_look_ifs.ipynb`       | IFS completeness, step change at +144 h, precipitation per 6 h window                         |
| `05_first_look_gfs.ipynb`       | GFS completeness, step change at +120 h, 43 °C outlier at +255 h, precipitation per 6 h window |
| `06_compare_dwd_vs_models.ipynb`| Unify and join, DWD vs each model (scatter + MAE), all models on common days, short findings  |

How the downloads work:

- **dynamical.org scripts** open the lazy dataset with `dynamical_catalog.open(name, chunks=None)`, pick the 00 UTC start
  times in the window, select the nearest grid point and download in batches of 20 start times, appending to the CSV.
  Start times already in the CSV are skipped, so interrupted runs resume.
- **GraphCast** reads one NetCDF file per day directly from S3 (`GRAP_v200_IFS` first, then `GRAP_v100_IFS`), only the
  station grid point. Days without a file are listed in `data/graphcast/graphcast_missing_inits.txt`. A network error skips that day (not saved, retried on the next run); a full run takes many hours, so use `--workers 12` or more.
- **DWD**: `historical` and `recent` zips are merged, `historical` wins on overlap, `-999` becomes NaN.

## Output files and their quirks

All in `data/` (git-ignored, re-created by the scripts).

| File                                             | Key columns                                                                 | Units / quirks                                                                                                                                                           |
| ------------------------------------------------ | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `aifs_single/aifs_single_hamburg_t2m_precip.csv` | `init_time, lead_time_h, valid_time, temperature_2m, precipitation_surface` | °C; precipitation is a **rate in kg m-2 s-1**; precipitation NaN at lead 0                                                                                               |
| `ifs/ifs_control_hamburg_t2m_precip.csv`         | same + `ensemble_member` (always 0)                                         | same units; steps are 3-hourly up to +144 h, then 6-hourly                                                                                                               |
| `gfs/gfs_hamburg_t2m_precip.csv`                 | same as AIFS                                                                | hourly up to +120 h, then 3-hourly; precipitation NaN at lead 0                                                                                                          |
| `graphcast/graphcast_ifs_hamburg_t2m_precip.csv` | `init_time, s3_prefix, time, t2, apcp`                                      | **Kelvin**; `apcp` is 6 h accumulation in **metres**; no lead-time column (`time` is the valid time); about 3500 tiny negative `apcp` values (clip to 0); NetCDF fill value 9.97e36 since 18.06.2026 at lead 0 and +6 h (set to NaN); only `GRAP_v100_IFS`; 201 of 962 days missing, mostly late Aug 2024 to Jan 2025 and May/Jun 2026 |
| `dwd/dwd_01975_air_temperature_hourly.csv`       | `time, TT_TU, RF_TU, QN_9, source`                                          | °C, relative humidity %; `time` in UTC                                                                                                                                   |
| `dwd/dwd_01975_precipitation_hourly.csv`         | `time, R1, RS_IND, WRTR, QN_8, source`                                      | `R1` is mm per hour; `time` in UTC; values from 05.09.2026 on only formally checked (`QN` = 1)                                                                          |
| `prepared/forecasts_vs_dwd.csv` (from notebook 06) | `model, init_time, lead_time_h, valid_time, t2m, precip, obs_t2m, obs_precip` | °C and mm per 6 h; lead times +6 h to +240 h; one row per model, run and lead time                                                                                      |

Also present in `data/dwd/`: the raw DWD zip files (re-downloaded automatically when missing).

## Next steps

1. Optional: move the preparation from notebook 06 into a script in `process_data/` so the tidy table is rebuilt
   without running the notebook; decide whether to keep the AIFS version column.
2. Modelling and evaluation (18.12.): regression, clustering, outlier detection, association rules, as in the project
   idea. Starting hypotheses: AI better on temperature; AI smears precipitation into frequent light rain;
   cold bias depends on time of day (strongest at 18 UTC); temperature extremes need a closer look.

## Working conventions

- The user is **not experienced with Python**. Write simple, readable code. Avoid clever one-liners, heavy abstraction
  and defensive code that is unlikely to fail (retries, extra validation, fallbacks "just in case").
- Comment complex lines with short comments saying what happens to the data: **never more than 10 words, ideally about 5**.
- Keep scripts short and flat. Prefer one clear step per line.
- Use `uv` (`uv sync`, `uv run`). Python 3.13, dependencies in `pyproject.toml`; add new ones there.
- Do not commit anything in `data/`. Scripts must stay resumable.
- The user is on Windows (`C:\Users\Daniel\Code\DataAnalytics`). Scripts using multiprocessing need
  `if __name__ == "__main__":`.
- When reporting to the user, be short and non-technical (project-manager level), unless asked for details.
