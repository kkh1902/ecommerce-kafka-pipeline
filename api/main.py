"""
FastAPI Recommendation Service
추천 모델 서빙 API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import psycopg2
from datetime import datetime
import os

from src.ml.recommendation_model import RecommendationModel
from config.settings import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)


# FastAPI 앱 생성
app = FastAPI(
    title="E-commerce Recommendation API",
    description="클릭스트림 데이터 기반 상품 추천 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 글로벌 변수
model = None
db_conn = None


# 요청/응답 모델
class RecommendationRequest(BaseModel):
    user_id: int
    n_recommendations: int = 10


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[int]
    timestamp: str


class BatchRecommendationRequest(BaseModel):
    user_ids: List[int]
    n_recommendations: int = 10


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    db_connected: bool
    timestamp: str


# 데이터베이스 연결
def get_db_connection():
    """PostgreSQL 연결"""
    global db_conn
    if db_conn is None or db_conn.closed:
        db_conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
    return db_conn


# 모델 로드
def load_model():
    """추천 모델 로드"""
    global model
    if model is None:
        model = RecommendationModel()
        model_path = 'models/recommendation_model.pkl'
        if os.path.exists(model_path):
            model.load(model_path)
            print("추천 모델 로드 완료")
        else:
            print("⚠️ 모델 파일이 없습니다. 인기 상품 기반 추천을 사용합니다.")
            print("   모델을 학습하려면: python train_model.py --limit 50000")
    return model


# 시작 이벤트
@app.on_event("startup")
async def startup_event():
    """API 시작 시 실행"""
    print("=" * 60)
    print("FastAPI 서버 시작")
    print("=" * 60)
    try:
        # 데이터베이스 연결
        get_db_connection()
        print(f"PostgreSQL 연결 성공: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")

        # 모델 로드 (실패해도 계속)
        try:
            load_model()
        except Exception as e:
            print(f"⚠️ 모델 로드 실패: {e}")

        print("=" * 60)
        print("웹 페이지: http://localhost:8000")
        print("API 문서: http://localhost:8000/docs")
        print("=" * 60)
    except Exception as e:
        print(f"시작 중 에러 발생: {e}")


# 종료 이벤트
@app.on_event("shutdown")
async def shutdown_event():
    """API 종료 시 실행"""
    global db_conn
    if db_conn and not db_conn.closed:
        db_conn.close()
    print("FastAPI 서버 종료")


# 엔드포인트
@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 페이지"""
    return """
    <html>
        <head>
            <title>E-commerce 추천 시스템 API</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                h1 { color: #3b82f6; }
                a { color: #3b82f6; text-decoration: none; }
                a:hover { text-decoration: underline; }
                .info { background: #f0f9ff; padding: 20px; border-radius: 8px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>🛒 E-commerce 추천 시스템 API</h1>
            <p>클릭스트림 데이터 기반 상품 추천 시스템</p>
            <div class="info">
                <h3>📚 문서 및 링크</h3>
                <ul>
                    <li><a href="/docs">📖 API 문서 (Swagger UI)</a></li>
                    <li><a href="/redoc">📄 API 문서 (ReDoc)</a></li>
                    <li><a href="http://localhost:3002" target="_blank">🎨 프론트엔드 대시보드</a></li>
                </ul>
            </div>
        </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스 체크"""
    return HealthResponse(
        status="healthy",
        model_loaded=model is not None and model.trained,
        db_connected=db_conn is not None and not db_conn.closed,
        timestamp=datetime.now().isoformat()
    )


@app.post("/recommend", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    """
    단일 사용자 추천

    Args:
        user_id: 사용자 ID
        n_recommendations: 추천 개수 (기본 10)

    Returns:
        추천 상품 ID 리스트
    """
    try:
        if model is None or not model.trained:
            # 모델이 없으면 인기 상품 반환
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT itemid, COUNT(*) as cnt
                    FROM clickstream_events
                    GROUP BY itemid
                    ORDER BY cnt DESC
                    LIMIT %s
                """, (request.n_recommendations,))
                recommendations = [row[0] for row in cur.fetchall()]

            if not recommendations:
                recommendations = list(range(1, request.n_recommendations + 1))
        else:
            recommendations = model.predict(request.user_id, request.n_recommendations)

        return RecommendationResponse(
            user_id=request.user_id,
            recommendations=recommendations,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend/batch")
async def get_batch_recommendations(request: BatchRecommendationRequest):
    """
    배치 사용자 추천

    Args:
        user_ids: 사용자 ID 리스트
        n_recommendations: 추천 개수 (기본 10)

    Returns:
        사용자별 추천 상품 ID 딕셔너리
    """
    try:
        results = model.batch_predict(request.user_ids, request.n_recommendations)

        return {
            "results": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user/{user_id}/profile")
async def get_user_profile(user_id: int):
    """
    사용자 프로필 조회

    Args:
        user_id: 사용자 ID

    Returns:
        사용자 프로필 정보
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 사용자 통계
            cur.execute("""
                SELECT
                    COUNT(*) as total_events,
                    SUM(CASE WHEN event = 'addtocart' THEN 1 ELSE 0 END) as cart_events,
                    SUM(CASE WHEN event = 'transaction' THEN 1 ELSE 0 END) as purchase_events
                FROM clickstream_events
                WHERE visitorid = %s
            """, (user_id,))

            row = cur.fetchone()

            if row[0] == 0:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

            return {
                "user_id": user_id,
                "total_events": row[0],
                "cart_events": row[1],
                "purchase_events": row[2]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user/{user_id}/history")
async def get_user_history(user_id: int, limit: int = 20):
    """
    사용자 이벤트 히스토리 조회

    Args:
        user_id: 사용자 ID
        limit: 조회 개수 (기본 20)

    Returns:
        사용자의 최근 이벤트 리스트
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT timestamp, event, itemid, transactionid
                FROM clickstream_events
                WHERE visitorid = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (user_id, limit))

            rows = cur.fetchall()

            history = []
            for row in rows:
                # timestamp가 int (unix timestamp) 또는 datetime일 수 있음
                timestamp = row[0]
                if timestamp:
                    if isinstance(timestamp, int):
                        # Unix timestamp인 경우 그대로 사용
                        timestamp_str = str(timestamp)
                    else:
                        # datetime 객체인 경우 isoformat 사용
                        timestamp_str = timestamp.isoformat()
                else:
                    timestamp_str = None

                history.append({
                    "timestamp": timestamp_str,
                    "event": row[1],
                    "itemid": row[2],
                    "transactionid": row[3]
                })

            return {
                "user_id": user_id,
                "history": history,
                "count": len(history)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/item/{item_id}/stats")
async def get_item_stats(item_id: int):
    """
    상품 통계 조회

    Args:
        item_id: 상품 ID

    Returns:
        상품 통계 정보
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_events,
                    COUNT(DISTINCT visitorid) as unique_visitors,
                    SUM(CASE WHEN event = 'view' THEN 1 ELSE 0 END) as views,
                    SUM(CASE WHEN event = 'addtocart' THEN 1 ELSE 0 END) as addtocarts,
                    SUM(CASE WHEN event = 'transaction' THEN 1 ELSE 0 END) as purchases
                FROM clickstream_events
                WHERE itemid = %s
            """, (item_id,))

            row = cur.fetchone()

            if row[0] == 0:
                raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

            return {
                "item_id": item_id,
                "total_events": row[0],
                "unique_visitors": row[1],
                "views": row[2],
                "addtocarts": row[3],
                "purchases": row[4],
                "conversion_rate": row[4] / row[0] if row[0] > 0 else 0
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/summary")
async def get_summary_stats():
    """전체 통계 요약"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 전체 통계
            cur.execute("SELECT * FROM event_summary")
            events = cur.fetchall()

            event_stats = []
            for row in events:
                event_stats.append({
                    "event": row[0],
                    "count": row[1],
                    "unique_visitors": row[2],
                    "unique_items": row[3]
                })

            # 총 레코드 수
            cur.execute("SELECT COUNT(*) FROM clickstream_events")
            total_records = cur.fetchone()[0]

            return {
                "total_records": total_records,
                "event_stats": event_stats,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/top-products")
async def get_top_products(limit: int = 10):
    """인기 상품 Top N (클릭 수 기준)"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    itemid,
                    COUNT(*) as total_clicks,
                    COUNT(DISTINCT visitorid) as unique_visitors,
                    SUM(CASE WHEN event = 'view' THEN 1 ELSE 0 END) as views,
                    SUM(CASE WHEN event = 'addtocart' THEN 1 ELSE 0 END) as addtocarts,
                    SUM(CASE WHEN event = 'transaction' THEN 1 ELSE 0 END) as purchases
                FROM clickstream_events
                GROUP BY itemid
                ORDER BY total_clicks DESC
                LIMIT %s
            """, (limit,))

            rows = cur.fetchall()
            products = []
            for idx, row in enumerate(rows):
                products.append({
                    "rank": idx + 1,
                    "item_id": row[0],
                    "total_clicks": row[1],
                    "unique_visitors": row[2],
                    "views": row[3],
                    "addtocarts": row[4],
                    "purchases": row[5],
                    "ctr": round((row[5] / row[1] * 100) if row[1] > 0 else 0, 2)
                })

            return {
                "products": products,
                "count": len(products)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/ctr")
async def get_ctr_stats():
    """실시간 CTR (Click-Through Rate) 지표"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 전체 CTR
            cur.execute("""
                SELECT
                    COUNT(*) as total_events,
                    SUM(CASE WHEN event = 'view' THEN 1 ELSE 0 END) as views,
                    SUM(CASE WHEN event = 'addtocart' THEN 1 ELSE 0 END) as addtocarts,
                    SUM(CASE WHEN event = 'transaction' THEN 1 ELSE 0 END) as purchases
                FROM clickstream_events
            """)
            row = cur.fetchone()

            total_events = row[0]
            views = row[1]
            addtocarts = row[2]
            purchases = row[3]

            return {
                "total_events": total_events,
                "views": views,
                "addtocarts": addtocarts,
                "purchases": purchases,
                "view_to_cart_rate": round((addtocarts / views * 100) if views > 0 else 0, 2),
                "cart_to_purchase_rate": round((purchases / addtocarts * 100) if addtocarts > 0 else 0, 2),
                "overall_conversion_rate": round((purchases / views * 100) if views > 0 else 0, 2)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/hourly-ctr")
async def get_hourly_ctr():
    """시간대별 CTR 변화"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    EXTRACT(HOUR FROM to_timestamp(timestamp/1000)) as hour,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN event = 'view' THEN 1 ELSE 0 END) as views,
                    SUM(CASE WHEN event = 'addtocart' THEN 1 ELSE 0 END) as addtocarts,
                    SUM(CASE WHEN event = 'transaction' THEN 1 ELSE 0 END) as purchases
                FROM clickstream_events
                GROUP BY hour
                ORDER BY hour
            """)

            rows = cur.fetchall()
            hourly_data = []
            for row in rows:
                hour = int(row[0]) if row[0] is not None else 0
                views = row[2]
                purchases = row[4]

                hourly_data.append({
                    "hour": f"{hour:02d}:00",
                    "total_events": row[1],
                    "views": views,
                    "addtocarts": row[3],
                    "purchases": purchases,
                    "ctr": round((purchases / views * 100) if views > 0 else 0, 2)
                })

            return {
                "hourly_data": hourly_data,
                "count": len(hourly_data)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/category-distribution")
async def get_category_distribution():
    """카테고리별 클릭 비율 (가상 카테고리)"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT itemid, COUNT(*) as clicks
                FROM clickstream_events
                GROUP BY itemid
                ORDER BY clicks DESC
                LIMIT 100
            """)

            rows = cur.fetchall()

            # 가상 카테고리 매핑
            categories = [
                '스마트폰', '노트북', '태블릿', '이어폰', '스마트워치',
                '카메라', '의류', '신발', '가방', '시계',
                '안경', '화장품', '식품', '가전', '가구',
                '책', '완구', '스포츠', '악기', '자동차'
            ]

            category_counts = {}
            for row in rows:
                item_id = row[0]
                clicks = row[1]
                category = categories[item_id % len(categories)]

                if category not in category_counts:
                    category_counts[category] = 0
                category_counts[category] += clicks

            # 비율 계산
            total_clicks = sum(category_counts.values())
            category_data = []
            for category, clicks in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                category_data.append({
                    "category": category,
                    "clicks": clicks,
                    "percentage": round((clicks / total_clicks * 100) if total_clicks > 0 else 0, 2)
                })

            return {
                "categories": category_data,
                "total_clicks": total_clicks,
                "count": len(category_data)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
