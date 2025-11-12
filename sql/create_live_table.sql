-- Spark 실시간 처리용 테이블
CREATE TABLE IF NOT EXISTS live_clickstream_events (
    id SERIAL PRIMARY KEY,
    timestamp BIGINT NOT NULL,
    visitorid BIGINT NOT NULL,
    event VARCHAR(50) NOT NULL,
    itemid BIGINT NOT NULL,
    transactionid VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_live_timestamp ON live_clickstream_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_live_visitorid ON live_clickstream_events(visitorid);
CREATE INDEX IF NOT EXISTS idx_live_event ON live_clickstream_events(event);
CREATE INDEX IF NOT EXISTS idx_live_itemid ON live_clickstream_events(itemid);
CREATE INDEX IF NOT EXISTS idx_live_created_at ON live_clickstream_events(created_at);
