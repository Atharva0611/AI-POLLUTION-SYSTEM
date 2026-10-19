from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AI Pollution System running"
    assert data["dashboard_url"] == "/dashboard"
    assert data["docs_url"] == "/docs"


def test_dashboard_endpoint():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AI Pollution Dashboard" in response.text or len(response.text) > 0


def test_anomalies_endpoint():
    response = client.get("/api/anomalies/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)


def test_hotspots_endpoint():
    response = client.get("/api/hotspots/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "hotspots" in data
    assert isinstance(data["hotspots"], list)


def test_validation_report_endpoint():
    response = client.get("/api/forecast/validation-report")

    assert response.status_code == 200
    data = response.json()

    if "validation_metadata" in data:
        metadata = data["validation_metadata"]
        assert metadata["total_records"] > 0
        assert metadata["station_count"] > 0
        assert isinstance(metadata["stations_covered"], list)
    else:
        assert data["status"] == "pending"

def test_rag_pm10_standards():
    response = client.get(
        "/api/rag/query",
        params={"q": "What are the CPCB PM10 annual and 24-hour standards?"},
    )

    assert response.status_code == 200
    data = response.json()
    answer = data["answer"]

    assert "60 ug/m3" in answer
    assert "100 ug/m3" in answer
    assert "?g/m?" not in answer
    assert any(
        source.get("file") == "cpcb_naaqs.pdf"
        for source in data["sources"]
    )


def test_rag_grap_thresholds():
    response = client.get(
        "/api/rag/query",
        params={"q": "What are the GRAP PM2.5 and PM10 thresholds?"},
    )

    assert response.status_code == 200
    data = response.json()
    answer = data["answer"]

    assert "300 ug/m3" in answer
    assert "500 ug/m3" in answer
    assert "121-250 ug/m3" in answer
    assert "?g/m?" not in answer
    assert any(
        source.get("file") == "CPCB_Dust_Mitigation_Guidelines.pdf"
        and source.get("page") == 8
        for source in data["sources"]
    )


def test_rag_ncap_vs_grap_comparison():
    response = client.get(
        "/api/rag/query",
        params={"q": "What is the difference between NCAP and GRAP?"},
    )

    assert response.status_code == 200
    data = response.json()
    answer = data["answer"]
    source_files = {source.get("file") for source in data["sources"]}

    assert "NCAP - National Clean Air Programme" in answer
    assert "GRAP - Graded Response Action Plan" in answer
    assert "Main difference" in answer
    assert "NCAP_Guidelines.pdf" in source_files
    assert "CPCB_Dust_Mitigation_Guidelines.pdf" in source_files
    assert len(answer) < 2500

def test_forecast_stations_endpoint():
    response = client.get("/api/forecast/stations")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["station_count"] > 0
    assert isinstance(data["stations"], dict)


def test_legacy_pm25_forecast_endpoint():
    response = client.get(
        "/api/forecast/pm25",
        params={"location": "Pune"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data.get("status") != "error", data.get("message")
    assert data["location"] == "Pune"
    assert "forecast_available" in data
    assert "contributing_stations" in data
    assert isinstance(data["contributing_stations"], list)

    if data["forecast_available"]:
        assert isinstance(data.get("pm25_next_1h"), (int, float))
        assert data["pm25_next_1h"] >= 0
