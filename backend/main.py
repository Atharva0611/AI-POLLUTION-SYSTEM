from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import pollution, forecast, rag, anomalies, hotspots, recommendations, source_analysis, current_snapshot
from backend.app.api.chat import router as chat_router
from backend.services.historical_weather import router as historical_weather_router

app = FastAPI(
    title="AI Pollution System",
    description="AI-powered air pollution monitoring and forecasting API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from pathlib import Path
from fastapi.responses import HTMLResponse

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

@app.get("/", tags=["Health"])
def root():
    return {"status": "AI Pollution System running", "dashboard_url": "/dashboard", "docs_url": "/docs"}

@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    dashboard_html = TEMPLATE_DIR / "dashboard.html"
    if dashboard_html.exists():
        return dashboard_html.read_text(encoding="utf-8")
    return "<h1>AI Pollution Dashboard</h1><p>Template not found.</p>"


# ============================================================
# REGISTER ROUTERS
# ============================================================

if hasattr(pollution, "router"):
    app.include_router(pollution.router, prefix="/api/pollution", tags=["Pollution"])

if hasattr(forecast, "router"):
    app.include_router(forecast.router, prefix="/api/forecast", tags=["Forecast"])

if hasattr(rag, "router"):
    app.include_router(rag.router, prefix="/api/rag", tags=["RAG / Policy"])

if hasattr(anomalies, "router"):
    app.include_router(anomalies.router, prefix="/api/anomalies", tags=["Anomalies"])

if hasattr(hotspots, "router"):
    app.include_router(hotspots.router, prefix="/api/hotspots", tags=["Hotspots"])

if hasattr(recommendations, "router"):
    app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])

if hasattr(source_analysis, "router"):
    app.include_router(source_analysis.router, prefix="/api/source-analysis", tags=["Source Analysis"])

if hasattr(current_snapshot, "router"):
    app.include_router(current_snapshot.router, prefix="/api/current-snapshot", tags=["Current Snapshot"])


# Historical meteorological data (separate from measured pollution data)
app.include_router(historical_weather_router, prefix="/api/weather", tags=["Historical Weather"])

# Unified ORIVA conversational API
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
