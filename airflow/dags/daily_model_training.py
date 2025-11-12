"""
Airflow DAG: Daily Model Training
매일 추천 모델을 재학습하는 DAG
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import sys
import os

# 프로젝트 경로 추가
sys.path.append('/opt/airflow/project')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'daily_model_training',
    default_args=default_args,
    description='매일 추천 모델 재학습',
    schedule_interval='0 2 * * *',  # 매일 새벽 2시
    catchup=False,
)


def check_data_quality():
    """데이터 품질 검사"""
    from src.ml.data_preparation import DataPreparation

    prep = DataPreparation()
    prep.connect_db()
    df = prep.load_data(limit=1000)

    if df is None or len(df) == 0:
        raise ValueError("데이터가 없습니다")

    # 기본 검증
    assert 'visitorid' in df.columns
    assert 'itemid' in df.columns
    assert 'event' in df.columns

    print(f"✅ 데이터 품질 검사 통과: {len(df)}개")
    prep.close()


def train_model():
    """모델 학습"""
    from src.ml.data_preparation import DataPreparation
    from src.ml.recommendation_model import RecommendationModel

    prep = DataPreparation()
    prep.connect_db()

    # 전체 데이터 로드
    df = prep.load_data()
    train_df, test_df = prep.get_train_test_split()

    # 모델 학습
    model = RecommendationModel()
    model.fit(train_df)

    # 평가
    hit_rate = model.evaluate(test_df)

    # 모델 저장
    model.save('/opt/airflow/project/models/recommendation_model.pkl')

    print(f"✅ 모델 학습 완료! Hit Rate: {hit_rate:.4f}")
    prep.close()


# Task 정의
check_quality = PythonOperator(
    task_id='check_data_quality',
    python_callable=check_data_quality,
    dag=dag,
)

train = PythonOperator(
    task_id='train_model',
    python_callable=train_model,
    dag=dag,
)

notify = BashOperator(
    task_id='notify_completion',
    bash_command='echo "모델 학습 완료: $(date)"',
    dag=dag,
)

# Task 순서
check_quality >> train >> notify
