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

-- User management tables
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'regular' CHECK (role IN ('regular', 'administrator')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    created_by UUID REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    session_token VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_expires ON user_sessions(expires_at);

-- Create default admin user (password: admin123 - change immediately!)
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@example.com', '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'administrator')
ON CONFLICT (username) DO NOTHING;