-- E-commerce Clickstream 테이블 생성

CREATE TABLE IF NOT EXISTS clickstream_events (
    id SERIAL PRIMARY KEY,
    timestamp BIGINT NOT NULL,
    visitorid INTEGER NOT NULL,
    event VARCHAR(50) NOT NULL,
    itemid INTEGER NOT NULL,
    transactionid INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성 (조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_timestamp ON clickstream_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_visitorid ON clickstream_events(visitorid);
CREATE INDEX IF NOT EXISTS idx_event ON clickstream_events(event);
CREATE INDEX IF NOT EXISTS idx_itemid ON clickstream_events(itemid);

-- 통계를 위한 뷰
CREATE OR REPLACE VIEW event_summary AS
SELECT
    event,
    COUNT(*) as event_count,
    COUNT(DISTINCT visitorid) as unique_visitors,
    COUNT(DISTINCT itemid) as unique_items
FROM clickstream_events
GROUP BY event;

-- ===== Spark Streaming 실시간 통계 테이블 =====

-- 윈도우 기반 집계 통계 (5분 단위)
CREATE TABLE IF NOT EXISTS windowed_stats (
    id SERIAL PRIMARY KEY,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    event VARCHAR(50) NOT NULL,
    event_count BIGINT NOT NULL,
    unique_users BIGINT NOT NULL,
    unique_items BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(window_start, window_end, event)
);

-- 임시 테이블 (Spark에서 UPSERT용)
CREATE TABLE IF NOT EXISTS windowed_stats_temp (
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    event VARCHAR(50) NOT NULL,
    event_count BIGINT NOT NULL,
    unique_users BIGINT NOT NULL,
    unique_items BIGINT NOT NULL
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_windowed_stats_window ON windowed_stats(window_start, window_end);
CREATE INDEX IF NOT EXISTS idx_windowed_stats_event ON windowed_stats(event);

-- 실시간 이벤트별 통계 (전체 누적)
CREATE TABLE IF NOT EXISTS event_statistics (
    id SERIAL PRIMARY KEY,
    event VARCHAR(50) NOT NULL UNIQUE,
    total_count BIGINT NOT NULL,
    unique_visitors BIGINT NOT NULL,
    unique_items BIGINT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 실시간 지표 조회용 뷰
CREATE OR REPLACE VIEW realtime_metrics AS
SELECT
    window_start,
    window_end,
    event,
    event_count,
    unique_users,
    unique_items
FROM windowed_stats
WHERE window_start >= NOW() - INTERVAL '1 hour'
ORDER BY window_start DESC, event;

-- 최근 통계 요약 뷰
CREATE OR REPLACE VIEW latest_stats AS
SELECT
    event,
    total_count,
    unique_visitors,
    unique_items,
    updated_at
FROM event_statistics
ORDER BY total_count DESC;
