"""
Statistics Processor
Spark Streaming으로 실시간 통계를 계산해서 PostgreSQL에 저장 (대시보드용)
"""

from pyspark.sql.functions import (
    col, window, count, approx_count_distinct, current_timestamp
)
import psycopg2


class StatsProcessor:
    """통계 데이터 처리 클래스 (대시보드용)"""

    def __init__(self, postgres_config, error_handler):
        """
        Args:
            postgres_config: dict - PostgreSQL 연결 정보
                {host, port, database, user, password}
            error_handler: ErrorHandler 인스턴스
        """
        self.postgres_config = postgres_config
        self.error_handler = error_handler

    # ============================================
    # 윈도우 집계 (5분 단위)
    # ============================================
    def process_windowed_aggregations(self, df):
        """
        5분 윈도우로 이벤트 집계 (대시보드용)

        Args:
            df: Spark DataFrame (event_time 컬럼 포함)

        Returns:
            StreamingQuery 객체

        저장 테이블:
            - windowed_stats

        집계 내용:
            - 5분 윈도우 (1분마다 갱신)
            - 이벤트별 개수, 고유 사용자, 고유 상품
        """
        print("\n=== 윈도우 집계 (5분 단위) 시작 ===")

        # 5분 윈도우로 집계
        windowed_stats = df \
            .withWatermark("event_time", "10 minutes") \
            .groupBy(
                window(col("event_time"), "5 minutes", "1 minute"),  # 5분 윈도우, 1분 슬라이딩
                col("event")
            ) \
            .agg(
                count("*").alias("event_count"),                                  # 이벤트 개수
                approx_count_distinct("visitorid").alias("unique_users"),         # 고유 사용자 수 (근사값)
                approx_count_distinct("itemid").alias("unique_items")             # 고유 상품 수 (근사값)
            ) \
            .select(
                col("window.start").alias("window_start"),            # 윈도우 시작 시간
                col("window.end").alias("window_end"),                # 윈도우 종료 시간
                col("event"),
                col("event_count"),
                col("unique_users"),
                col("unique_items")
            )

        # PostgreSQL에 저장 (UPSERT)
        def write_windowed_batch(batch_df, batch_id):
            """배치 데이터를 windowed_stats 테이블에 UPSERT"""
            if batch_df.count() > 0:
                try:
                    print(f"[윈도우 집계] 배치 {batch_id} 저장 중... ({batch_df.count()}개)")

                    # PostgreSQL 연결
                    conn = psycopg2.connect(**self.postgres_config)
                    cur = conn.cursor()

                    # 각 행을 UPSERT
                    for row in batch_df.collect():
                        cur.execute("""
                            INSERT INTO windowed_stats
                            (window_start, window_end, event, event_count, unique_users, unique_items)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (window_start, window_end, event)
                            DO UPDATE SET
                                event_count = EXCLUDED.event_count,
                                unique_users = EXCLUDED.unique_users,
                                unique_items = EXCLUDED.unique_items,
                                created_at = CURRENT_TIMESTAMP
                        """, (
                            row.window_start, row.window_end, row.event,
                            row.event_count, row.unique_users, row.unique_items
                        ))

                    conn.commit()
                    cur.close()
                    conn.close()

                    print(f"[윈도우 집계] 배치 {batch_id} 저장 완료")

                except Exception as e:
                    error_msg = f"윈도우 집계 저장 실패: {str(e)}"
                    print(f"[윈도우 집계] {error_msg}")
                    # 에러 처리 (분류 → DB 저장 → Slack 알림)
                    self.error_handler.handle_error(
                        error_message=error_msg,
                        batch_id=batch_id,
                        raw_data={"table": "windowed_stats", "error": str(e)}
                    )

        # 스트림 시작
        query = windowed_stats.writeStream \
            .outputMode("update") \
            .foreachBatch(write_windowed_batch) \
            .start()

        print("윈도우 집계 스트림 실행 중 → windowed_stats 테이블")
        return query

    # ============================================
    # 실시간 통계 (전체 누적)
    # ============================================
    def process_realtime_stats(self, df):
        """
        이벤트별 전체 누적 통계 (대시보드용)

        Args:
            df: Spark DataFrame

        Returns:
            StreamingQuery 객체

        저장 테이블:
            - event_statistics

        집계 내용:
            - 이벤트별 전체 개수, 고유 사용자, 고유 상품
        """
        print("\n=== 실시간 누적 통계 시작 ===")

        # 이벤트 유형별 전체 통계
        event_stats = df \
            .groupBy("event") \
            .agg(
                count("*").alias("total_count"),                                # 전체 개수
                approx_count_distinct("visitorid").alias("unique_visitors"),    # 고유 방문자 (근사값)
                approx_count_distinct("itemid").alias("unique_items")           # 고유 상품 (근사값)
            )

        # PostgreSQL에 저장 (UPSERT)
        def write_stats_batch(batch_df, batch_id):
            """배치 데이터를 event_statistics 테이블에 UPSERT"""
            if batch_df.count() > 0:
                try:
                    print(f"[실시간 통계] 배치 {batch_id} 저장 중... ({batch_df.count()}개)")

                    # PostgreSQL 연결
                    conn = psycopg2.connect(**self.postgres_config)
                    cur = conn.cursor()

                    # 각 행을 UPSERT
                    for row in batch_df.collect():
                        cur.execute("""
                            INSERT INTO event_statistics
                            (event, total_count, unique_visitors, unique_items, updated_at)
                            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                            ON CONFLICT (event)
                            DO UPDATE SET
                                total_count = EXCLUDED.total_count,
                                unique_visitors = EXCLUDED.unique_visitors,
                                unique_items = EXCLUDED.unique_items,
                                updated_at = CURRENT_TIMESTAMP
                        """, (row.event, row.total_count, row.unique_visitors, row.unique_items))

                    conn.commit()
                    cur.close()
                    conn.close()

                    print(f"[실시간 통계] 배치 {batch_id} 저장 완료")

                except Exception as e:
                    error_msg = f"실시간 통계 저장 실패: {str(e)}"
                    print(f"[실시간 통계] {error_msg}")
                    # 에러 처리
                    self.error_handler.handle_error(
                        error_message=error_msg,
                        batch_id=batch_id,
                        raw_data={"table": "event_statistics", "error": str(e)}
                    )

        # 스트림 시작
        query = event_stats.writeStream \
            .outputMode("complete") \
            .foreachBatch(write_stats_batch) \
            .start()

        print("실시간 통계 스트림 실행 중 → event_statistics 테이블")
        return query
