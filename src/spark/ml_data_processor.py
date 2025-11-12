"""
ML Data Processor
Spark Streaming으로 ML 학습용 원본 데이터를 PostgreSQL에 저장
"""

from pyspark.sql.functions import col


class MLDataProcessor:
    """ML 학습용 데이터 처리 클래스"""

    def __init__(self, postgres_writer):
        """
        Args:
            postgres_writer: PostgreSQL 저장 함수 (write_to_postgres)
        """
        self.postgres_writer = postgres_writer

    def process_raw_events(self, df):
        """
        원본 이벤트를 PostgreSQL에 저장 (ML 학습용)

        Args:
            df: Spark DataFrame (Kafka에서 읽은 데이터)

        Returns:
            StreamingQuery 객체

        저장 테이블:
            - live_clickstream_events

        용도:
            - 추천 모델 학습
            - 사용자 행동 분석
            - 협업 필터링
        """
        print("\n=== ML 학습용 원본 이벤트 저장 시작 ===")

        # 필요한 컬럼만 선택
        events_df = df.select(
            col("timestamp"),       # 이벤트 발생 시간
            col("visitorid"),       # 사용자 ID
            col("event"),           # 이벤트 타입 (view, addtocart, transaction)
            col("itemid"),          # 상품 ID
            col("transactionid")    # 거래 ID (구매 시에만)
        )

        # PostgreSQL live_clickstream_events 테이블에 저장
        query = events_df.writeStream \
            .outputMode("append") \
            .foreachBatch(self.postgres_writer(events_df, "live_clickstream_events")) \
            .start()

        print("ML 학습용 데이터 스트림 실행 중 → live_clickstream_events 테이블")
        return query
