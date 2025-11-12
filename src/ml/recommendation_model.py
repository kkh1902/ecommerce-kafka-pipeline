"""
Recommendation Model
간단한 협업 필터링 기반 추천 시스템
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict, Counter
import pickle
from datetime import datetime


class RecommendationModel:
    """추천 모델 클래스"""

    def __init__(self):
        self.user_item_matrix = None
        self.item_similarity = None
        self.item_popularity = None
        self.trained = False

    def fit(self, df):
        """모델 학습"""
        print("모델 학습 시작...")

        # 사용자-아이템 행렬 생성 (암시적 피드백)
        # 이벤트 가중치: view=1, addtocart=2, transaction=3
        event_weights = {'view': 1, 'addtocart': 2, 'transaction': 3}
        df['weight'] = df['event'].map(event_weights)

        # 피벗 테이블 생성
        self.user_item_matrix = df.pivot_table(
            index='visitorid',
            columns='itemid',
            values='weight',
            aggfunc='sum',
            fill_value=0
        )

        print(f"사용자-아이템 행렬: {self.user_item_matrix.shape}")

        # 아이템 유사도 계산 (코사인 유사도)
        self.item_similarity = cosine_similarity(self.user_item_matrix.T)
        self.item_similarity = pd.DataFrame(
            self.item_similarity,
            index=self.user_item_matrix.columns,
            columns=self.user_item_matrix.columns
        )

        print(f"아이템 유사도 행렬: {self.item_similarity.shape}")

        # 아이템 인기도 계산
        self.item_popularity = df.groupby('itemid').size().sort_values(ascending=False)

        self.trained = True
        print("모델 학습 완료!")

    def predict(self, user_id, n_recommendations=10):
        """특정 사용자에게 상품 추천"""
        if not self.trained:
            raise ValueError("모델이 학습되지 않았습니다")

        if user_id not in self.user_item_matrix.index:
            # 신규 사용자: 인기 상품 추천
            return self._recommend_popular(n_recommendations)

        # 사용자가 이미 본 상품
        user_items = self.user_item_matrix.loc[user_id]
        seen_items = user_items[user_items > 0].index.tolist()

        if len(seen_items) == 0:
            return self._recommend_popular(n_recommendations)

        # 본 상품들과 유사한 상품 찾기
        similar_items = []
        for item in seen_items:
            if item in self.item_similarity.index:
                similar = self.item_similarity[item].sort_values(ascending=False)[1:n_recommendations+1]
                similar_items.extend(similar.index.tolist())

        # 이미 본 상품 제외
        recommended = [item for item in similar_items if item not in seen_items]

        # 중복 제거 및 빈도순 정렬
        item_counts = Counter(recommended)
        recommended = [item for item, count in item_counts.most_common(n_recommendations)]

        # 부족하면 인기 상품으로 채우기
        if len(recommended) < n_recommendations:
            popular = self._recommend_popular(n_recommendations - len(recommended), exclude=seen_items + recommended)
            recommended.extend(popular)

        return recommended[:n_recommendations]

    def _recommend_popular(self, n=10, exclude=None):
        """인기 상품 추천"""
        if exclude is None:
            exclude = []

        popular_items = [item for item in self.item_popularity.index if item not in exclude]
        return popular_items[:n]

    def batch_predict(self, user_ids, n_recommendations=10):
        """여러 사용자에게 배치 추천"""
        results = {}
        for user_id in user_ids:
            results[user_id] = self.predict(user_id, n_recommendations)
        return results

    def evaluate(self, test_df, n_recommendations=10):
        """모델 평가"""
        if not self.trained:
            raise ValueError("모델이 학습되지 않았습니다")

        print("모델 평가 중...")

        # 테스트 데이터에서 실제 구매한 상품
        actual_purchases = test_df[test_df['event'] == 'transaction'].groupby('visitorid')['itemid'].apply(list).to_dict()

        hits = 0
        total_users = 0
        skipped_users = 0

        for user_id, actual_items in actual_purchases.items():
            # 학습 데이터에 있는 사용자만 평가 (Cold Start 문제)
            if user_id not in self.user_item_matrix.index:
                skipped_users += 1
                continue

            # 추천 상품
            recommended = self.predict(user_id, n_recommendations)

            # Hit@N 계산
            if any(item in recommended for item in actual_items):
                hits += 1
            total_users += 1

        hit_rate = hits / total_users if total_users > 0 else 0

        print(f"Hit Rate@{n_recommendations}: {hit_rate:.4f}")
        print(f"평가 사용자 수: {total_users}")
        print(f"  - 학습 데이터에 있는 사용자: {total_users}명")
        print(f"  - 학습 데이터에 없는 사용자 (스킵): {skipped_users}명")
        if total_users > 0:
            print(f"  - Hit 수: {hits}명")

        return hit_rate

    def save(self, filepath='models/recommendation_model.pkl'):
        """모델 저장"""
        if not self.trained:
            raise ValueError("모델이 학습되지 않았습니다")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        model_data = {
            'user_item_matrix': self.user_item_matrix,
            'item_similarity': self.item_similarity,
            'item_popularity': self.item_popularity,
            'trained': self.trained,
            'saved_at': datetime.now().isoformat()
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"모델 저장 완료: {filepath}")

    def load(self, filepath='models/recommendation_model.pkl'):
        """모델 로드"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {filepath}")

        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.user_item_matrix = model_data['user_item_matrix']
        self.item_similarity = model_data['item_similarity']
        self.item_popularity = model_data['item_popularity']
        self.trained = model_data['trained']

        print(f"모델 로드 완료: {filepath}")
        print(f"저장 시각: {model_data.get('saved_at', 'N/A')}")


class ItemBasedCF(RecommendationModel):
    """아이템 기반 협업 필터링 (별칭)"""
    pass


def main():
    """메인 실행"""
    from data_preparation import DataPreparation

    print("=" * 60)
    print("추천 모델 학습")
    print("=" * 60)

    # 데이터 전처리
    prep = DataPreparation()

    try:
        # DB 연결 및 데이터 로드
        if not prep.connect_db():
            return

        df = prep.load_data(limit=50000)  # 샘플 5만개로 학습
        if df is None:
            return

        # 학습/테스트 분할
        train_df, test_df = prep.get_train_test_split()

        # 모델 학습
        model = RecommendationModel()
        model.fit(train_df)

        # 모델 평가
        hit_rate = model.evaluate(test_df, n_recommendations=10)

        # 샘플 추천
        print("\n샘플 추천 결과:")
        sample_users = train_df['visitorid'].unique()[:5]
        for user_id in sample_users:
            recommendations = model.predict(user_id, n_recommendations=5)
            print(f"  사용자 {user_id}: {recommendations}")

        # 모델 저장
        model.save()

        print("\n" + "=" * 60)
        print("추천 모델 학습 완료!")
        print("=" * 60)

    except Exception as e:
        print(f"\n에러 발생: {e}")
        raise
    finally:
        prep.close()


if __name__ == '__main__':
    main()
