CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS locations (
    id BIGSERIAL PRIMARY KEY,
    location_id TEXT UNIQUE,
    location_name TEXT NOT NULL,
    country TEXT DEFAULT 'India',
    state TEXT DEFAULT 'Maharashtra',
    city TEXT DEFAULT 'Pune',
    location_type TEXT,
    source TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom GEOMETRY(Point, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_locations_geom
ON locations
USING GIST (geom);


CREATE TABLE IF NOT EXISTS air_quality_observations (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT REFERENCES locations(id),
    station_name TEXT,
    observed_at TIMESTAMPTZ NOT NULL,
    pm25 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    so2 DOUBLE PRECISION,
    co DOUBLE PRECISION,
    o3 DOUBLE PRECISION,
    aqi DOUBLE PRECISION,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_air_quality_time
ON air_quality_observations(observed_at);

CREATE INDEX IF NOT EXISTS idx_air_quality_location
ON air_quality_observations(location_id);


CREATE TABLE IF NOT EXISTS weather_observations (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT REFERENCES locations(id),
    observed_at TIMESTAMPTZ NOT NULL,
    temperature_c DOUBLE PRECISION,
    feels_like_c DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    rainfall_mm DOUBLE PRECISION,
    wind_speed_kph DOUBLE PRECISION,
    wind_direction TEXT,
    pressure_mb DOUBLE PRECISION,
    visibility_km DOUBLE PRECISION,
    uv DOUBLE PRECISION,
    condition TEXT,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS forecasts (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT REFERENCES locations(id),
    forecast_time TIMESTAMPTZ NOT NULL,
    model_name TEXT,
    pm25_prediction DOUBLE PRECISION,
    weatherapi_prediction DOUBLE PRECISION,
    ensemble_prediction DOUBLE PRECISION,
    model_station TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS anomalies (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT REFERENCES locations(id),
    station_name TEXT,
    observed_at TIMESTAMPTZ,
    is_anomaly BOOLEAN,
    anomaly_score DOUBLE PRECISION,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS hotspots (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT REFERENCES locations(id),
    station_name TEXT,
    cluster INTEGER,
    pm25_mean DOUBLE PRECISION,
    pm25_max DOUBLE PRECISION,
    hotspot_score DOUBLE PRECISION,
    pollution_level TEXT,
    observed_at TIMESTAMPTZ,
    geom GEOMETRY(Point, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hotspots_geom
ON hotspots
USING GIST (geom);


CREATE TABLE IF NOT EXISTS source_analysis (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT REFERENCES locations(id),
    station_name TEXT,
    source_indicator TEXT,
    evidence_variables TEXT,
    score DOUBLE PRECISION,
    interpretation TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS recommendations (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT REFERENCES locations(id),
    recommendation TEXT NOT NULL,
    severity TEXT,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS agent_logs (
    id BIGSERIAL PRIMARY KEY,
    question TEXT,
    intent TEXT,
    location TEXT,
    response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
