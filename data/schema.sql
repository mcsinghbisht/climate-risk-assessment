-- Climate Risk Assessment - SQLite Database Schema
-- Version: 1.0
-- Created: 2026-07-19

-- Schema versioning table
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY,
    version INTEGER NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Properties table - stores property data and static hazard exposure
CREATE TABLE IF NOT EXISTS properties (
    property_id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    state TEXT,
    county TEXT,
    zip_code TEXT,
    construction_type TEXT,
    elevation_m REAL,
    is_in_wildland_urban_interface BOOLEAN DEFAULT 0,
    is_in_floodplain BOOLEAN DEFAULT 0,
    soil_type TEXT,
    drainage_class TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (latitude >= -90 AND latitude <= 90),
    CHECK (longitude >= -180 AND longitude <= 180)
);

-- Risk assessments table - stores risk score snapshots
CREATE TABLE IF NOT EXISTS risk_assessments (
    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    assessment_timestamp TIMESTAMP NOT NULL,
    wildfire_risk_score REAL,
    wildfire_factors TEXT,
    flood_risk_score REAL,
    flood_factors TEXT,
    overall_risk_score REAL,
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    alerts_triggered TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties(property_id),
    CHECK (wildfire_risk_score IS NULL OR (wildfire_risk_score >= 0 AND wildfire_risk_score <= 100)),
    CHECK (flood_risk_score IS NULL OR (flood_risk_score >= 0 AND flood_risk_score <= 100)),
    CHECK (overall_risk_score IS NULL OR (overall_risk_score >= 0 AND overall_risk_score <= 100))
);

-- Hazard data table - stores ingested external hazard data
CREATE TABLE IF NOT EXISTS hazard_data (
    hazard_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hazard_type TEXT NOT NULL,
    source TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    value REAL,
    confidence REAL DEFAULT 1.0,
    observation_timestamp TIMESTAMP NOT NULL,
    ingested_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data TEXT,
    CHECK (latitude >= -90 AND latitude <= 90),
    CHECK (longitude >= -180 AND longitude <= 180),
    CHECK (confidence >= 0 AND confidence <= 1)
);

-- Alerts table - stores triggered alerts
-- status/resolved_at/last_notified_at added in Task 21b (alert lifecycle;
-- see docs/alert-lifecycle-design.md)
-- property_id made nullable in Task 27: portfolio-level alerts
-- (risk_type='portfolio_high_risk_pct') aren't about one property.
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    risk_type TEXT NOT NULL,
    risk_score REAL,
    threshold_exceeded REAL,
    alert_level TEXT CHECK (alert_level IN ('warning', 'critical')),
    message TEXT,
    triggered_at TIMESTAMP NOT NULL,
    acknowledged_at TIMESTAMP,
    status TEXT CHECK (status IN ('active', 'acknowledged', 'stale', 'resolved')) DEFAULT 'active',
    resolved_at TIMESTAMP,
    last_notified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (property_id) REFERENCES properties(property_id),
    CHECK (risk_score >= 0 AND risk_score <= 100)
);

-- Alert history table - tracks alert status changes
CREATE TABLE IF NOT EXISTS alert_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES alerts(alert_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_properties_state ON properties(state);
CREATE INDEX IF NOT EXISTS idx_properties_county ON properties(county);
CREATE INDEX IF NOT EXISTS idx_properties_coords ON properties(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_risk_property ON risk_assessments(property_id);
CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_assessments(assessment_timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_level ON risk_assessments(risk_level);
CREATE INDEX IF NOT EXISTS idx_hazard_type ON hazard_data(hazard_type, source);
CREATE INDEX IF NOT EXISTS idx_hazard_coords ON hazard_data(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_hazard_timestamp ON hazard_data(ingested_timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_property ON alerts(property_id);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(triggered_at);
