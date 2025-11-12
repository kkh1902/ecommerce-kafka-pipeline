-- 에러 이벤트 저장 테이블
CREATE TABLE IF NOT EXISTS error_events (
    id SERIAL PRIMARY KEY,
    error_type VARCHAR(50) NOT NULL,
    error_message TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    raw_data JSONB,
    batch_id BIGINT,
    error_timestamp TIMESTAMP NOT NULL,
    retry_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_error_type ON error_events(error_type);
CREATE INDEX IF NOT EXISTS idx_error_severity ON error_events(severity);
CREATE INDEX IF NOT EXISTS idx_error_status ON error_events(status);
CREATE INDEX IF NOT EXISTS idx_error_timestamp ON error_events(error_timestamp);
CREATE INDEX IF NOT EXISTS idx_error_created_at ON error_events(created_at);

-- severity: INFO, WARNING, ERROR, CRITICAL
-- status: pending, retrying, resolved, failed
-- error_type: json_parse, db_connection, timeout, constraint_violation
