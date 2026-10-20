# ORIVA AI Pollution System — Implementation Context and Continuation

## Project overview

- **Project:** ORIVA AI Pollution System
- **Repository:** [Atharva0611/AI-POLLUTION-SYSTEM](https://github.com/Atharva0611/AI-POLLUTION-SYSTEM)
- **Local path:** `C:\\final year project\\AI-POLLUTION-SYSTEM-GITHUB`
- **Implementation branch:** `feat/oriva-live-data-quality-frontend`
- **Draft pull request:** [#6 — Verify ORIVA live data and forecasting frontend](https://github.com/Atharva0611/AI-POLLUTION-SYSTEM/pull/6)
- **Branch URL:** https://github.com/Atharva0611/AI-POLLUTION-SYSTEM/tree/feat/oriva-live-data-quality-frontend

Continue on the implementation branch. Do not merge PR #6 or PR #5 without explicit authorization. Do not overwrite local changes, reset user work, or commit real API keys.

## Objective

Improve ORIVA with a professional light-themed frontend, real air-quality station measurements, current weather, forecast provenance, SHAP explainability, and explicit data-quality labels.

Preserve existing ML forecasting, DBSCAN hotspot detection, LangGraph agent orchestration, RAG policy retrieval, and existing backend functionality. Do not fabricate air-quality values. Clearly distinguish provider measurements, model predictions, estimates, and official CPCB AQI.

## Implementation changes

### OpenAQ station integration

File: `backend/services/openaq_service.py`

- OpenAQ v3 API client using the `X-API-Key` header.
- Retrieves station metadata and latest sensor measurements.
- Exposes timestamps and units.
- Classifies freshness as fresh, delayed, stale, missing/invalid, or future-dated.
- Uses configurable freshness thresholds and sanitizes provider errors.
- OpenAQ readings are not automatically represented as official CPCB AQI.

Environment template in `.env.example`:

```dotenv
OPENAQ_API_KEY=replace_with_your_openaq_key
WEATHER_API_KEY=replace_with_your_weatherapi_key
DATA_GOV_IN_API_KEY=
OPENAQ_FRESH_HOURS=24
OPENAQ_DELAYED_HOURS=72
OPENAQ_TIMEOUT_SECONDS=12
```

Never commit real API keys. Keep secrets in an untracked local environment file.

### Air-quality API

File: `backend/api/routes/air_quality.py`

- `GET /api/air-quality/locations`
- `GET /api/air-quality/stations/{location_id}`

The locations route accepts latitude, longitude, radius, and limit; Pune is the default area.

### Current weather API

File: `backend/api/routes/weather_current.py`

- `GET /api/weather/current?location=Pune`

Uses the existing weather service and sanitizes provider failures.

### Router registration

File: `backend/main.py`

Registers the air-quality and current-weather routers while retaining existing routes.

### OpenAQ unit tests

File: `backend/tests/test_openaq_service.py`

Covers fresh, stale, missing/invalid, future-dated, and near-future timestamps.

### Backend requirements

File: `backend/requirements.txt`

The branch's requirements file currently lists FastAPI, Uvicorn, Pandas, NumPy, scikit-learn, XGBoost, SHAP, LangChain, LangGraph, LangChain Community, ChromaDB, pypdf, SQLAlchemy, psycopg2-binary, python-dotenv, and requests. Inspect package compatibility before changing versions.

### Live air-quality frontend

File: `frontend/src/pages/LiveAirQuality.jsx`

- Station explorer with search/list/detail.
- Pollutant measurements, timestamps, and freshness labels.
- Current weather panel.
- Explicit notice that OpenAQ measurements are not automatically official CPCB AQI.

### Forecast and SHAP frontend

File: `frontend/src/pages/Forecast.jsx`

Consumes `GET /api/forecast/universal?location=...` and displays available next-hour PM2.5 prediction, forecast method, model provenance/version, contributing stations, hourly context, SHAP contributions, validation metrics, and quality warnings.

Keep direct station forecasts distinct from spatially estimated forecasts. When data is insufficient and forecasts are suppressed, do not show a number as a valid prediction.

### Light theme and navigation

- `frontend/src/oriva-light.css`: professional light styles, responsive layout, station explorer, forecast, SHAP bars, provenance, warnings.
- `frontend/src/App.jsx`: Overview, Live air quality, Hotspot map, Forecast & SHAP, ORIVA Assistant.

Preserve existing components and navigation behavior.

### CI workflow

File: `.github/workflows/frontend-build.yml`

Includes a Vite production build and an OpenAQ freshness-test job that runs:

`python -m pytest -q backend/tests/test_openaq_service.py`

## Verification record

Workflow URL: https://github.com/Atharva0611/AI-POLLUTION-SYSTEM/actions/runs/39437746510

Last recorded results:
- **Vite production build:** passed.
- **OpenAQ freshness unit tests:** passed.

These checks do not prove that the full backend test suite passes, that local Windows startup works, or that real OpenAQ/weather API credentials work. Live provider integration has not been verified with real credentials. Direct official CPCB integration has not been implemented/verified.

## Current local backend blocker

Developer environment: Windows PowerShell, Python 3.14.

Repository:
`C:\\final year project\\AI-POLLUTION-SYSTEM-GITHUB`

Existing virtual environment:
`C:\\final year project\\.venv`

The environment activation succeeds:

```powershell
cd "C:\\final year project\\AI-POLLUTION-SYSTEM-GITHUB"
& "C:\\final year project\\.venv\\Scripts\\Activate.ps1"
```

Packages previously present include FastAPI, Uvicorn, NumPy, Pandas, scikit-learn, SHAP, XGBoost, and requests. Backend startup fails at:

`ModuleNotFoundError: No module named 'langchain_core'`

Import path:
`backend/main.py` → `backend/api/routes/rag.py` → `backend/agents/policy_agent.py` → `backend/rag/retriever.py` → `from langchain_core.documents import Document`.

A scan found the existing `C:\\final year project\\.venv`; no separate environment containing LangChain was confirmed.

### Required recovery steps

1. Keep the existing virtual environment; do not delete/recreate it.
2. Inspect the repository requirements and dependency versions.
3. Install dependencies from the existing backend requirements into the activated environment, only after reviewing errors/conflicts.
4. Check for Python 3.14 package compatibility and report dependency conflicts; do not force random upgrades/downgrades.
5. Verify imports before launching Uvicorn.
6. First run Uvicorn without `--reload` for a clearer trace.
7. Diagnose any further errors based on the actual traceback.

Backend startup:

```powershell
cd "C:\\final year project\\AI-POLLUTION-SYSTEM-GITHUB"
& "C:\\final year project\\.venv\\Scripts\\Activate.ps1"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend startup, in a second terminal:

```powershell
cd "C:\\final year project\\AI-POLLUTION-SYSTEM-GITHUB\\frontend"
npm install
npm run dev
```

Open the Vite URL shown in the terminal, commonly `http://localhost:5173`. The frontend can run without the backend, but API-dependent features may show connection errors.

### Local endpoints to verify

- Backend root: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- Forecast: http://127.0.0.1:8000/api/forecast/universal?location=Pune
- Stations: http://127.0.0.1:8000/api/air-quality/locations?latitude=18.5204&longitude=73.8567&radius_m=15000&limit=20

## Git safety and continuation workflow

- Work only on `feat/oriva-live-data-quality-frontend` unless explicitly instructed otherwise.
- Do not merge PR #6 into `main) without explicit authorization.
- Do not merge PR #5.
- Never reset, discard, or overwrite local user changes.
- Never commit secrets, API keys, large raw datasets, virtual environments, or generated caches.
- Inspect `git status` and diffs before committing local modifications.
- For GitHub edits, make focused commits with clear messages and confirm the resulting SHA.
- Do not claim tests, local startup, or live APIs passed without evidence.

## Next tasks

1. Diagnose and repair the missing LangChain dependencies in the existing local environment.
2. Start the backend and validate startup/API docs.
3. Start the frontend.
4. Test station and forecast pages against actual API responses.
5. Report each verification as passed, failed, or not yet tested.
6. Preserve existing architecture and source provenance; do not substitute fabricated air-quality values.
