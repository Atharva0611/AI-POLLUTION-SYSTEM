# ORIVA AI: Pune + Pimpri-Chinchwad OGD snapshot

## What's included

- `data/raw/ogd_air_quality_snapshot_original.csv`: original supplied CSV, unchanged.
- `data/processed/pune_pcmc_current_readings.csv`: all rows for Pune and Pimpri-Chinchwad.
- `data/processed/pune_current_readings.csv`: Pune-only pollutant rows.
- `data/processed/pimpri_chinchwad_current_readings.csv`: Pimpri-Chinchwad-only pollutant rows.
- `data/processed/pune_pcmc_station_summary.csv`: one row per station with PM2.5/PM10 columns and coordinates.
- `backend/api/routes/current_snapshot.py`: optional read-only FastAPI endpoint for the station summary.

## Snapshot findings

- 98 pollutant rows total: 49 Pune and 49 Pimpri-Chinchwad.
- 14 stations in total: 7 per city.
- Source observation timestamp in the supplied file: 12 October 2026, 23:00 IST.
- 14 stations in the summary, including stations where PM2.5 and/or PM10 averages are missing. Missing values are preserved as null.
- PM2.5 and PM10 missing values are preserved as null; do not impute missing live values as zero.

## Copy into the existing project

From PowerShell, run in the project root (`C:\final year project\AI-POLLUTION-SYSTEM`) after downloading and extracting this package:

```powershell
Copy-Item .\oriva_pune_pcmc_package\data\raw\ogd_air_quality_snapshot_original.csv .\data\raw\ogd_air_quality_snapshot_original.csv -Force
Copy-Item .\oriva_pune_pcmc_package\data\processed\pune_pcmc_current_readings.csv .\data\processed\pune_pcmc_current_readings.csv -Force
Copy-Item .\oriva_pune_pcmc_package\data\processed\pune_current_readings.csv .\data\processed\pune_current_readings.csv -Force
Copy-Item .\oriva_pune_pcmc_package\data\processed\pimpri_chinchwad_current_readings.csv .\data\processed\pimpri_chinchwad_current_readings.csv -Force
Copy-Item .\oriva_pune_pcmc_package\data\processed\pune_pcmc_station_summary.csv .\data\processed\pune_pcmc_station_summary.csv -Force
Copy-Item .\oriva_pune_pcmc_package\backend\api\routes\current_snapshot.py .\backend\api\routes\current_snapshot.py -Force
```

Ensure `data\raw` and `data\processed` exist first; create them with `New-Item -ItemType Directory -Force .\data\raw, .\data\processed` if needed.

## Register the optional API router

In `backend/main.py`, add this import alongside the existing route imports:

```python
from backend.api.routes import current_snapshot
```

Then add this alongside the other `app.include_router(...)` calls:

```python
app.include_router(current_snapshot.router)
```

Restart Uvicorn, then test:

- `GET http://127.0.0.1:8000/api/current-snapshot`
- `GET http://127.0.0.1:8000/api/current-snapshot?city=Pune`
- `GET http://127.0.0.1:8000/api/current-snapshot?city=Pimpri-Chinchwad`

## Important modeling/data semantics

This is one observation snapshot, not a historical time series. It can power a current station summary/map, but it is not enough to train or validate a forecast model. Do not append it to the historical hourly dataset as if it were an hourly continuation. Keep the existing 72-hour freshness guard for forecasts. The route reports freshness from the source observation timestamp, and missing pollutant values remain null.
