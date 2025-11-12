"""
Data Preparation for Recommendation Model
PostgreSQL에서 데이터를 로드하고 ML 학습을 위한 특징 추출
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.settings import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)


class DataPreparation:
    """데이터 전처리 클래스"""

    def __init__(self):
        self.conn = None
        self.df = None

    def connect_db(self):
        """PostgreSQL 연결"""
        try:
            self.conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            print(f"PostgreSQL 연결 성공: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
            return True
        except Exception as e:
            print(f"PostgreSQL 연결 실패: {e}")
            return False

    def load_data(self, limit=None, min_events_per_user=3):
        """
        데이터 로드 (활성 사용자만 필터링)

        Args:
            limit: 로드할 레코드 수 제한
            min_events_per_user: 사용자당 최소 이벤트 수 (기본: 3)
        """
        try:
            # 활성 사용자만 필터링하여 로드
            query = f"""
                WITH user_counts AS (
                    SELECT visitorid, COUNT(*) as event_count
                    FROM clickstream_events
                    GROUP BY visitorid
                    HAVING COUNT(*) >= {min_events_per_user}
                )
                SELECT ce.*
                FROM clickstream_events ce
                INNER JOIN user_counts uc ON ce.visitorid = uc.visitorid
                ORDER BY ce.visitorid, ce.timestamp
            """

            if limit:
                query += f" LIMIT {limit}"

            self.df = pd.read_sql_query(query, self.conn)

            n_users = self.df['visitorid'].nunique()
            n_items = self.df['itemid'].nunique()
            avg_events = len(self.df) / n_users if n_users > 0 else 0

            print(f"데이터 로드 완료: {len(self.df):,}개")
            print(f"  활성 사용자: {n_users:,}명 (최소 {min_events_per_user}개 이벤트)")
            print(f"  고유 상품: {n_items:,}개")
            print(f"  사용자당 평균 이벤트: {avg_events:.1f}건")

            return self.df
        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            return None

    def extract_features(self):
        """특징 추출"""
        if self.df is None:
            print("먼저 데이터를 로드하세요")
            return None

        print("특징 추출 중...")

        # 타임스탬프를 datetime으로 변환
        self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms')
        self.df['hour'] = self.df['datetime'].dt.hour
        self.df['dayofweek'] = self.df['datetime'].dt.dayofweek

        # 이벤트 타입 원-핫 인코딩
        event_dummies = pd.get_dummies(self.df['event'], prefix='event')
        self.df = pd.concat([self.df, event_dummies], axis=1)

        # 사용자별 집계 특징
        user_features = self.df.groupby('visitorid').agg({
            'itemid': 'count',  # 총 이벤트 수
            'event': lambda x: (x == 'transaction').sum(),  # 구매 횟수
            'timestamp': ['min', 'max']  # 첫/마지막 이벤트 시간
        }).reset_index()

        user_features.columns = ['visitorid', 'total_events', 'purchase_count',
                                 'first_event_time', 'last_event_time']

        # 구매 전환율
        user_features['conversion_rate'] = (
            user_features['purchase_count'] / user_features['total_events']
        ).fillna(0)

        # 활동 기간 (일)
        user_features['activity_days'] = (
            (user_features['last_event_time'] - user_features['first_event_time']) / 1000 / 86400
        )

        # 상품별 인기도
        item_popularity = self.df.groupby('itemid').size().reset_index(name='item_popularity')

        # 특징 병합
        self.df = self.df.merge(user_features, on='visitorid', how='left')
        self.df = self.df.merge(item_popularity, on='itemid', how='left')

        print(f"특징 추출 완료: {self.df.shape[1]}개 컬럼")
        return self.df

    def create_sequences(self, seq_length=10):
        """시퀀스 데이터 생성 (추천 모델용)"""
        if self.df is None:
            print("먼저 데이터를 로드하세요")
            return None

        print(f"시퀀스 데이터 생성 중 (길이: {seq_length})...")

        # 사용자별로 시간순 정렬
        df_sorted = self.df.sort_values(['visitorid', 'timestamp'])

        sequences = []
        targets = []

        for visitor_id in df_sorted['visitorid'].unique():
            user_items = df_sorted[df_sorted['visitorid'] == visitor_id]['itemid'].values

            # 시퀀스 길이보다 긴 경우만 사용
            if len(user_items) > seq_length:
                for i in range(len(user_items) - seq_length):
                    sequences.append(user_items[i:i+seq_length])
                    targets.append(user_items[i+seq_length])

        print(f"시퀀스 데이터 생성 완료: {len(sequences):,}개")
        return np.array(sequences), np.array(targets)

    def get_train_test_split(self, test_size=0.2, user_based=True):
        """학습/테스트 데이터 분할

        Args:
            test_size: 테스트 데이터 비율
            user_based: True면 사용자별로 분할, False면 시간 기반 분할
        """
        if self.df is None:
            print("먼저 데이터를 로드하세요")
            return None, None

        if user_based:
            # 사용자별 분할: 각 사용자의 최신 이벤트를 테스트로
            # 모든 사용자가 학습/테스트 데이터에 모두 포함됨
            train_list = []
            test_list = []

            for user_id in self.df['visitorid'].unique():
                user_data = self.df[self.df['visitorid'] == user_id].sort_values('timestamp')
                n_events = len(user_data)

                # 최소 2개 이벤트가 있는 경우만 분할
                if n_events >= 2:
                    split_idx = int(n_events * (1 - test_size))
                    if split_idx == 0:
                        split_idx = 1

                    train_list.append(user_data.iloc[:split_idx])
                    test_list.append(user_data.iloc[split_idx:])
                else:
                    # 이벤트가 1개만 있으면 학습에만 포함
                    train_list.append(user_data)

            train_df = pd.concat(train_list, ignore_index=True)
            test_df = pd.concat(test_list, ignore_index=True)

        else:
            # 시간 기반 분할 (기존 방식)
            sorted_df = self.df.sort_values('timestamp')
            split_idx = int(len(sorted_df) * (1 - test_size))

            train_df = sorted_df.iloc[:split_idx]
            test_df = sorted_df.iloc[split_idx:]

        train_ratio = (1 - test_size) * 100
        test_ratio = test_size * 100

        print(f"학습 데이터: {len(train_df):,}개 ({len(train_df)/len(self.df)*100:.0f}%)")
        print(f"테스트 데이터: {len(test_df):,}개 ({len(test_df)/len(self.df)*100:.0f}%)")
        print(f"  - 학습 사용자: {train_df['visitorid'].nunique():,}명")
        print(f"  - 테스트 사용자: {test_df['visitorid'].nunique():,}명")

        # 공통 사용자 확인
        train_users = set(train_df['visitorid'].unique())
        test_users = set(test_df['visitorid'].unique())
        common_users = train_users & test_users
        print(f"  - 학습/테스트 공통 사용자: {len(common_users):,}명 (테스트의 {len(common_users)/len(test_users)*100:.1f}%)")

        return train_df, test_df

    def save_processed_data(self, output_dir='data/processed'):
        """전처리된 데이터 저장"""
        if self.df is None:
            print("저장할 데이터가 없습니다")
            return False

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'processed_data.csv')

        self.df.to_csv(output_path, index=False)
        print(f"데이터 저장 완료: {output_path}")
        return True

    def close(self):
        """연결 종료"""
        if self.conn:
            self.conn.close()
            print("PostgreSQL 연결 종료")


def main():
    """메인 실행"""
    print("=" * 60)
    print("데이터 전처리 시작")
    print("=" * 60)

    # 데이터 전처리 객체 생성
    prep = DataPreparation()

    try:
        # DB 연결
        if not prep.connect_db():
            return

        # 데이터 로드 (샘플로 10000개만)
        df = prep.load_data(limit=10000)
        if df is None:
            return

        # 기본 통계
        print("\n데이터 통계:")
        print(f"  총 레코드: {len(df):,}개")
        print(f"  고유 사용자: {df['visitorid'].nunique():,}명")
        print(f"  고유 상품: {df['itemid'].nunique():,}개")
        print(f"\n이벤트 분포:")
        print(df['event'].value_counts())

        # 특징 추출
        df_with_features = prep.extract_features()

        # 학습/테스트 분할
        train_df, test_df = prep.get_train_test_split()

        # 시퀀스 데이터 생성
        sequences, targets = prep.create_sequences(seq_length=5)
        print(f"\n시퀀스 shape: {sequences.shape}")
        print(f"타겟 shape: {targets.shape}")

        # 저장
        prep.save_processed_data()

        print("\n" + "=" * 60)
        print("데이터 전처리 완료!")
        print("=" * 60)

    except Exception as e:
        print(f"\n에러 발생: {e}")
        raise
    finally:
        prep.close()


if __name__ == '__main__':
    main()
