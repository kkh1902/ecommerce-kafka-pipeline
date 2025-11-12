-- ===== 실시간 지표 조회 SQL 쿼리 =====
-- Spark Streaming으로 수집된 통계 데이터 조회

-- 1. 최근 1시간 윈도우 집계 통계 (5분 단위)
-- 최근 1시간 동안의 이벤트별 추세 확인
SELECT
    window_start,
    window_end,
    event,
    event_count,
    unique_users,
    unique_items,
    created_at
FROM windowed_stats
WHERE window_start >= NOW() - INTERVAL '1 hour'
ORDER BY window_start DESC, event;

-- 2. 실시간 이벤트별 전체 통계
-- 누적된 전체 이벤트 통계
SELECT
    event,
    total_count,
    unique_visitors,
    unique_items,
    updated_at,
    -- 이벤트별 비율 계산
    ROUND(100.0 * total_count / SUM(total_count) OVER (), 2) as percentage
FROM event_statistics
ORDER BY total_count DESC;

-- 3. 최근 30분 이벤트 추세
-- 최근 30분 동안 이벤트가 어떻게 변화하는지 확인
SELECT
    event,
    COUNT(*) as window_count,
    SUM(event_count) as total_events,
    AVG(event_count) as avg_events_per_window,
    SUM(unique_users) as total_unique_users,
    AVG(unique_users) as avg_users_per_window
FROM windowed_stats
WHERE window_start >= NOW() - INTERVAL '30 minutes'
GROUP BY event
ORDER BY total_events DESC;

-- 4. 시간대별 활동 패턴 (최근 24시간)
-- 시간대별로 사용자 활동이 언제 많은지 확인
SELECT
    DATE_TRUNC('hour', window_start) as hour,
    event,
    SUM(event_count) as total_count,
    SUM(unique_users) as total_users,
    SUM(unique_items) as total_items
FROM windowed_stats
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', window_start), event
ORDER BY hour DESC, total_count DESC;

-- 5. 전환율 분석 (view → addtocart → transaction)
-- 사용자가 어떤 단계에서 이탈하는지 확인
WITH funnel AS (
    SELECT
        SUM(CASE WHEN event = 'view' THEN total_count ELSE 0 END) as views,
        SUM(CASE WHEN event = 'addtocart' THEN total_count ELSE 0 END) as add_to_carts,
        SUM(CASE WHEN event = 'transaction' THEN total_count ELSE 0 END) as transactions
    FROM event_statistics
)
SELECT
    views,
    add_to_carts,
    transactions,
    ROUND(100.0 * add_to_carts / NULLIF(views, 0), 2) as view_to_cart_rate,
    ROUND(100.0 * transactions / NULLIF(add_to_carts, 0), 2) as cart_to_transaction_rate,
    ROUND(100.0 * transactions / NULLIF(views, 0), 2) as overall_conversion_rate
FROM funnel;

-- 6. 최근 5분 실시간 활동
-- 지금 막 일어나고 있는 활동 확인
SELECT
    window_start,
    window_end,
    event,
    event_count,
    unique_users,
    unique_items
FROM windowed_stats
WHERE window_start >= NOW() - INTERVAL '5 minutes'
ORDER BY window_start DESC, event_count DESC;

-- 7. 인기 아이템 분석 (원본 이벤트 기반)
-- 가장 많이 조회/담긴/구매된 아이템 TOP 10
SELECT
    itemid,
    COUNT(*) as total_interactions,
    COUNT(CASE WHEN event = 'view' THEN 1 END) as views,
    COUNT(CASE WHEN event = 'addtocart' THEN 1 END) as add_to_carts,
    COUNT(CASE WHEN event = 'transaction' THEN 1 END) as purchases
FROM clickstream_events
WHERE timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000
GROUP BY itemid
ORDER BY total_interactions DESC
LIMIT 10;

-- 8. 활성 사용자 분석 (최근 1시간)
-- 최근 1시간 동안 가장 활발한 사용자
SELECT
    visitorid,
    COUNT(*) as action_count,
    COUNT(DISTINCT event) as event_types,
    COUNT(DISTINCT itemid) as items_viewed,
    MIN(TO_TIMESTAMP(timestamp / 1000)) as first_action,
    MAX(TO_TIMESTAMP(timestamp / 1000)) as last_action
FROM clickstream_events
WHERE timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000
GROUP BY visitorid
ORDER BY action_count DESC
LIMIT 20;

-- 9. 이벤트 타임라인 (분 단위, 최근 1시간)
-- 시간대별 이벤트 발생 추이
SELECT
    DATE_TRUNC('minute', TO_TIMESTAMP(timestamp / 1000)) as minute,
    event,
    COUNT(*) as event_count
FROM clickstream_events
WHERE timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000
GROUP BY DATE_TRUNC('minute', TO_TIMESTAMP(timestamp / 1000)), event
ORDER BY minute DESC, event_count DESC
LIMIT 50;

-- 10. 시스템 헬스 체크
-- 데이터 수집 상태 확인
SELECT
    '원본 이벤트' as table_name,
    COUNT(*) as total_records,
    MAX(TO_TIMESTAMP(timestamp / 1000)) as last_event_time,
    EXTRACT(EPOCH FROM (NOW() - MAX(TO_TIMESTAMP(timestamp / 1000)))) as seconds_since_last_event
FROM clickstream_events
UNION ALL
SELECT
    '윈도우 통계',
    COUNT(*),
    MAX(created_at),
    EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))
FROM windowed_stats
UNION ALL
SELECT
    '이벤트 통계',
    COUNT(*),
    MAX(updated_at),
    EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))
FROM event_statistics;
