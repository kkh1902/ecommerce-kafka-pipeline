"""
Spark Structured Streaming Consumer
Kafka에서 데이터를 읽어 실시간 처리 및 PostgreSQL 저장
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window, count, countDistinct,
    sum as _sum, avg, current_timestamp, to_timestamp, lit, struct, to_json
)
from pyspark.sql.types import StructType, StructField, StringType, LongType
import sys
import os
import traceback

# 상위 디렉토리 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    KAFKA_BROKERS,
    KAFKA_TOPIC,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)
from error_handler import ErrorHandler          # 에러 처리
from ml_data_processor import MLDataProcessor   # ML 데이터 처리
from stats_processor import StatsProcessor      # 통계 데이터 처리

# 에러 토픽
ERROR_TOPIC = "error_data"


# ============================================
# Spark Streaming Consumer 클래스
# ============================================
class SparkStreamingConsumer:
    def __init__(self):
        self.spark = None
        self.kafka_bootstrap_servers = ','.join(KAFKA_BROKERS)

        # PostgreSQL JDBC URL
        self.jdbc_url = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        self.jdbc_properties = {
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD,
            "driver": "org.postgresql.Driver"
        }

        # PostgreSQL 연결 설정 (dict)
        self.postgres_config = {
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "database": POSTGRES_DB,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD
        }

        # 에러 핸들러 초기화
        self.error_handler = ErrorHandler(
            POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
            POSTGRES_USER, POSTGRES_PASSWORD
        )

        # ML 데이터 프로세서 초기화
        self.ml_processor = MLDataProcessor(self.write_to_postgres)

        # 통계 프로세서 초기화
        self.stats_processor = StatsProcessor(self.postgres_config, self.error_handler)

    # ============================================
    # Spark Session 설정
    # ============================================
    def create_spark_session(self):
        """Spark Session 생성"""
        print("Spark Session 생성 중...")

        # Windows 환경 대응: Hadoop 관련 설정
        import platform
        if platform.system() == 'Windows':
            print("Windows 환경 감지 - Hadoop 관련 설정 우회")
            # 프로젝트 루트 디렉토리 찾기 (src/spark에서 2단계 위)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            hadoop_home = os.path.join(project_root, 'hadoop')
            os.environ['HADOOP_HOME'] = hadoop_home
            print(f"HADOOP_HOME 설정: {hadoop_home}")

            # hadoop 임시 디렉토리 생성
            hadoop_dir = os.path.join(hadoop_home, 'bin')
            os.makedirs(hadoop_dir, exist_ok=True)

        self.spark = SparkSession.builder \
            .appName("E-Commerce Clickstream Processor") \
            .config("spark.jars.packages",
                   "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                   "org.postgresql:postgresql:42.6.0") \
            .config("spark.sql.streaming.checkpointLocation", "./spark-checkpoint") \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.shuffle.partitions", "3") \
            .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.LocalFileSystem") \
            .config("spark.hadoop.fs.file.impl.disable.cache", "true") \
            .master("local[*]") \
            .getOrCreate()

        self.spark.sparkContext.setLogLevel("WARN")
        print(f"Spark Session 생성 완료: {self.spark.version}")
        return self.spark

    # ============================================
    # 스키마 정의
    # ============================================
    def define_schema(self):
        """Kafka 메시지 스키마 정의"""
        return StructType([
            StructField("timestamp", LongType(), True),
            StructField("visitorid", LongType(), True),
            StructField("event", StringType(), True),
            StructField("itemid", LongType(), True),
            StructField("transactionid", StringType(), True)
        ])

    # ============================================
    # Kafka 스트림 읽기
    # ============================================
    def read_from_kafka(self):
        """Kafka에서 스트림 읽기"""
        print(f"Kafka 연결 중: {self.kafka_bootstrap_servers}")
        print(f"토픽 구독: {KAFKA_TOPIC}")

        schema = self.define_schema()

        # Kafka 스트림 읽기
        df = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.kafka_bootstrap_servers) \
            .option("subscribe", KAFKA_TOPIC) \
            .option("startingOffsets", "latest") \
            .option("maxOffsetsPerTrigger", 1000) \
            .load()

        # 원본 메시지 저장 (에러 처리용)
        df = df.withColumn("raw_value", col("value").cast("string"))

        # JSON 파싱 (에러 발생 시 NULL)
        parsed_df = df.selectExpr("CAST(value AS STRING) as json", "raw_value") \
            .select(
                from_json(col("json"), schema).alias("data"),
                col("raw_value")
            )

        # 파싱 성공한 데이터만 선택
        valid_df = parsed_df.filter(col("data").isNotNull()) \
            .select("data.*")

        # Timestamp 변환 (밀리초 -> timestamp)
        valid_df = valid_df.withColumn(
            "event_time",
            to_timestamp(col("timestamp") / 1000)
        )

        print("Kafka 스트림 읽기 완료")
        return valid_df

    # ============================================
    # 잘못된 JSON 처리 (Error Topic)
    # ============================================
    def process_invalid_json(self, df):
        """파싱 실패한 JSON을 error_data 토픽으로 전송"""
        print("\n=== 잘못된 JSON 처리 시작 ===")

        schema = self.define_schema()

        # 원본 메시지와 파싱 결과 함께 가져오기
        df_with_parse = df.selectExpr("CAST(value AS STRING) as json") \
            .select(
                col("json"),
                from_json(col("json"), schema).alias("data")
            )

        # 파싱 실패한 메시지만 필터링 (data가 NULL인 경우)
        invalid_df = df_with_parse.filter(col("data").isNull()) \
            .select(
                col("json").alias("raw_message"),
                lit("JSON parsing failed").alias("error_message"),
                current_timestamp().alias("error_timestamp")
            )

        # error_data 토픽으로 전송
        def write_invalid_batch(batch_df, batch_id):
            if batch_df.count() > 0:
                try:
                    # JSON 형태로 변환
                    error_json = batch_df.select(
                        to_json(struct("*")).alias("value")
                    )

                    # Kafka error_data 토픽으로 전송
                    error_json.write \
                        .format("kafka") \
                        .option("kafka.bootstrap.servers", self.kafka_bootstrap_servers) \
                        .option("topic", ERROR_TOPIC) \
                        .save()

                    print(f"배치 {batch_id}: {batch_df.count()}개의 잘못된 JSON을 {ERROR_TOPIC} 토픽으로 전송 완료")
                except Exception as e:
                    print(f"배치 {batch_id}: 잘못된 JSON 전송 실패: {e}")

        query = invalid_df.writeStream \
            .outputMode("append") \
            .foreachBatch(write_invalid_batch) \
            .start()

        print("잘못된 JSON 처리 스트림 실행 중...")
        return query

    # ============================================
    # 에러 데이터 전송 (Kafka Error Topic)
    # ============================================
    def send_to_error_topic(self, error_df, batch_id, error_message):
        """에러 데이터를 error_data 토픽으로 전송"""
        try:
            # 에러 정보 추가
            error_with_info = error_df \
                .withColumn("error_message", lit(error_message)) \
                .withColumn("error_timestamp", current_timestamp()) \
                .withColumn("batch_id", lit(batch_id))

            # JSON 형태로 변환
            error_json = error_with_info.select(
                to_json(struct("*")).alias("value")
            )

            # Kafka error_data 토픽으로 전송
            error_json.write \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.kafka_bootstrap_servers) \
                .option("topic", ERROR_TOPIC) \
                .save()

            print(f"배치 {batch_id} 에러 데이터 {error_df.count()}개를 {ERROR_TOPIC} 토픽으로 전송 완료")
        except Exception as send_error:
            print(f"에러 데이터 전송 실패: {send_error}")

    # ============================================
    # PostgreSQL 저장 (공통 함수)
    # ============================================
    def write_to_postgres(self, df, table_name, mode="append"):
        """PostgreSQL에 저장 (에러 발생 시 error_data 토픽 + DB 저장 + Slack 알림)"""
        def write_batch(batch_df, batch_id):
            try:
                print(f"배치 {batch_id} 저장 중... (레코드: {batch_df.count()}개)")

                batch_df.write \
                    .jdbc(
                        url=self.jdbc_url,
                        table=table_name,
                        mode=mode,
                        properties=self.jdbc_properties
                    )

                print(f"배치 {batch_id} 저장 완료")
            except Exception as e:
                error_msg = f"PostgreSQL 저장 실패 (Table: {table_name}): {str(e)}\n{traceback.format_exc()}"
                print(f"배치 {batch_id} 저장 실패: {e}")

                # 1. error_data 토픽으로 전송 (재처리용 보관)
                self.send_to_error_topic(batch_df, batch_id, error_msg)

                # 2. 통합 에러 처리 (분류 → DB 저장 → Slack 알림)
                self.error_handler.handle_error(
                    error_message=error_msg,
                    batch_id=batch_id,
                    raw_data={"table": table_name, "error": str(e)}
                )

        return write_batch
    def run(self):
        """스트리밍 파이프라인 실행"""
        print("=" * 60)
        print("Spark Structured Streaming 시작")
        print("=" * 60)

        try:
            # Spark Session 생성
            self.create_spark_session()

            # Kafka에서 원본 스트림 읽기
            raw_stream = self.spark.readStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.kafka_bootstrap_servers) \
                .option("subscribe", KAFKA_TOPIC) \
                .option("startingOffsets", "latest") \
                .option("maxOffsetsPerTrigger", 1000) \
                .load()

            # 유효한 데이터 스트림 (파싱 성공)
            df = self.read_from_kafka()

            # 여러 스트림 처리 시작
            queries = []

            # 0. 잘못된 JSON 처리 (error_data 토픽으로 전송) - Windows 환경에서 winutils.exe 문제로 주석 처리
            # queries.append(self.process_invalid_json(raw_stream))

            # 1. ML 학습용 원본 이벤트 저장 (MLDataProcessor 사용)
            queries.append(self.ml_processor.process_raw_events(df))

            # 2. 윈도우 집계 (StatsProcessor 사용)
            queries.append(self.stats_processor.process_windowed_aggregations(df))

            # 3. 실시간 통계 (StatsProcessor 사용)
            queries.append(self.stats_processor.process_realtime_stats(df))


            # 모든 쿼리가 종료될 때까지 대기
            for query in queries:
                query.awaitTermination()

        except KeyboardInterrupt:
            print("\n\n사용자가 중단했습니다")
        except Exception as e:
            print(f"\n에러 발생: {e}")
            raise
        finally:
            if self.spark:
                self.spark.stop()
                print("\nSpark Session 종료")


# ============================================
# 프로그램 엔트리 포인트
# ============================================
def main():
    consumer = SparkStreamingConsumer()
    consumer.run()


if __name__ == '__main__':
    main()
