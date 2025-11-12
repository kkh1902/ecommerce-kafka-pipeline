"""
Airflow DAG: Data Validation
데이터 검증 DAG
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

sys.path.append('/opt/airflow/project')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'data_validation',
    default_args=default_args,
    description='데이터 검증 및 품질 체크',
    schedule_interval='0 * * * *',  # 매시간
    catchup=False,
)


def validate_schema():
    """스키마 검증"""
    import psycopg2
    from config.settings import (
        POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
        POSTGRES_USER, POSTGRES_PASSWORD
    )

    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        database=POSTGRES_DB, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

    with conn.cursor() as cur:
        # 테이블 존재 확인
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'clickstream_events'
        """)
        if cur.fetchone() is None:
            raise ValueError("clickstream_events 테이블이 없습니다")

        # 레코드 수 확인
        cur.execute("SELECT COUNT(*) FROM clickstream_events")
        count = cur.fetchone()[0]
        print(f"✅ 스키마 검증 통과. 레코드 수: {count:,}개")

    conn.close()


def check_duplicates():
    """중복 데이터 확인"""
    import psycopg2
    from config.settings import (
        POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
        POSTGRES_USER, POSTGRES_PASSWORD
    )

    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        database=POSTGRES_DB, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

    with conn.cursor() as cur:
        cur.execute("""
            SELECT timestamp, visitorid, event, itemid, COUNT(*) as cnt
            FROM clickstream_events
            GROUP BY timestamp, visitorid, event, itemid
            HAVING COUNT(*) > 1
            LIMIT 10
        """)
        duplicates = cur.fetchall()

        if duplicates:
            print(f"⚠️ 중복 데이터 발견: {len(duplicates)}개")
        else:
            print("✅ 중복 데이터 없음")

    conn.close()


def validate_event_types():
    """이벤트 타입 검증"""
    import psycopg2
    from config.settings import (
        POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
        POSTGRES_USER, POSTGRES_PASSWORD
    )

    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        database=POSTGRES_DB, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

    valid_events = ['view', 'addtocart', 'transaction']

    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT event FROM clickstream_events")
        events = [row[0] for row in cur.fetchall()]

        for event in events:
            if event not in valid_events:
                raise ValueError(f"유효하지 않은 이벤트 타입: {event}")

        print(f"✅ 이벤트 타입 검증 통과: {events}")

    conn.close()


# Tasks
validate_schema_task = PythonOperator(
    task_id='validate_schema',
    python_callable=validate_schema,
    dag=dag,
)

check_duplicates_task = PythonOperator(
    task_id='check_duplicates',
    python_callable=check_duplicates,
    dag=dag,
)

validate_events_task = PythonOperator(
    task_id='validate_event_types',
    python_callable=validate_event_types,
    dag=dag,
)

# Task 순서
validate_schema_task >> [check_duplicates_task, validate_events_task]
