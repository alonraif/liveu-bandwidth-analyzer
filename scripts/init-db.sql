CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY,
    ticket_id VARCHAR(100),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metrics_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bandwidth_metrics (
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    session_id UUID NOT NULL REFERENCES sessions(session_id),
    modem_id INTEGER NOT NULL,
    bandwidth_mbps DECIMAL(10, 3),
    packet_loss_percent DECIMAL(5, 2),
    upstream_delay_ms INTEGER,
    shortest_rtt_ms INTEGER,
    smooth_rtt_ms INTEGER,
    min_rtt_ms INTEGER,
    -- Legacy fields for backward compatibility
    rtt_ms INTEGER,
    signal_strength INTEGER
);

SELECT create_hypertable('bandwidth_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX idx_bandwidth_session ON bandwidth_metrics(session_id);
CREATE INDEX idx_bandwidth_modem ON bandwidth_metrics(modem_id);