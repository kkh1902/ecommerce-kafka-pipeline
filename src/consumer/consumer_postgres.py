"""
Kafka Consumer for PostgreSQL
Kafka에서 메시지 받아서 PostgreSQL에 저장
"""

from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import execute_values
import json
import sys
import os
import math

# 상위 디렉토리 경로 추가 (src/consumer/ -> comerce-kafka/)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    KAFKA_BROKERS,
    KAFKA_TOPIC,
    CONSUMER_GROUP_ID,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)


def create_consumer():
    """Kafka Consumer 생성"""
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKERS,
            group_id=f"{CONSUMER_GROUP_ID}_postgres",  # 다른 consumer group
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        print(f"Kafka 연결 성공: {KAFKA_BROKERS}")
        print(f"토픽 구독: {KAFKA_TOPIC}")
        return consumer
    except Exception as e:
        print(f"Kafka 연결 실패: {e}")
        raise


def create_db_connection():
    """PostgreSQL 연결"""
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        print(f"PostgreSQL 연결 성공: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
        return conn
    except Exception as e:
        print(f"PostgreSQL 연결 실패: {e}")
        raise


def init_database(conn):
    """데이터베이스 초기화"""
    try:
        with conn.cursor() as cur:
            # 스키마 파일 읽기
            schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sql', 'schema.sql')
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            # 스키마 실행
            cur.execute(schema_sql)
            conn.commit()
            print("데이터베이스 초기화 완료")
    except Exception as e:
        print(f"데이터베이스 초기화 실패: {e}")
        raise


def insert_batch(conn, batch_data):
    """배치 데이터 삽입"""
    try:
        with conn.cursor() as cur:
            # 데이터 준비
            values = [
                (
                    data['timestamp'],
                    data['visitorid'],
                    data['event'],
                    data['itemid'],
                    data.get('transactionid')  # NaN일 수 있음
                )
                for data in batch_data
            ]

            # 배치 삽입
            execute_values(
                cur,
                """
                INSERT INTO clickstream_events (timestamp, visitorid, event, itemid, transactionid)
                VALUES %s
                """,
                values
            )
            conn.commit()
            return len(batch_data)
    except Exception as e:
        conn.rollback()
        print(f"데이터 삽입 실패: {e}")
        return 0


def consume_messages(consumer, conn):
    """메시지 수신 및 저장"""
    message_count = 0
    batch_data = []
    batch_size = 100  # 100개씩 모아서 저장

    print("\n메시지 대기 중...", flush=True)
    print("종료하려면 Ctrl+C 누르세요\n", flush=True)

    try:
        for message in consumer:
            # NaN 값을 None으로 변환
            msg = message.value
            for key, value in msg.items():
                if isinstance(value, float) and math.isnan(value):
                    msg[key] = None

            # 배치에 추가
            batch_data.append(msg)
            message_count += 1

            # 배치 크기 도달 시 저장
            if len(batch_data) >= batch_size:
                inserted = insert_batch(conn, batch_data)
                if inserted > 0:
                    print(f"DB 저장: {message_count}개 (배치: {inserted}개)", flush=True)
                batch_data = []

    except KeyboardInterrupt:
        print(f"\n\n사용자가 중단했습니다")
    except Exception as e:
        print(f"\n메시지 수신 에러: {e}")
        raise
    finally:
        # 남은 데이터 저장
        if batch_data:
            inserted = insert_batch(conn, batch_data)
            print(f"남은 데이터 저장: {inserted}개")

        print(f"\n총 받은 메시지: {message_count}개")


def main():
    print("=" * 60)
    print("Kafka Consumer (PostgreSQL) 시작")
    print("=" * 60)

    conn = None
    consumer = None

    try:
        # PostgreSQL 연결
        conn = create_db_connection()

        # 데이터베이스 초기화 (주석 처리 - docker-compose에서 자동 실행)
        # init_database(conn)

        # Consumer 생성
        consumer = create_consumer()

        # 메시지 수신
        consume_messages(consumer, conn)

    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n에러 발생: {e}")
        raise
    finally:
        # 종료 처리
        if consumer:
            consumer.close()
            print("\nConsumer 종료")
        if conn:
            conn.close()
            print("PostgreSQL 연결 종료")

        print("=" * 60)


if __name__ == '__main__':
    main()
