# E-commerce Kafka Producer/Consumer with PostgreSQL

E-commerce 클릭스트림 데이터를 Kafka로 실시간 스트리밍하고 PostgreSQL에 저장하는 프로젝트입니다.

## 프로젝트 개요

270만 개의 E-commerce 이벤트 데이터를 Kafka를 통해 실시간으로 처리하고 PostgreSQL 데이터베이스에 저장하는 Producer/Consumer 시스템입니다.

### 주요 기능
- CSV 파일을 읽어서 Kafka로 전송 (Producer)
- Spark Streaming을 통한 실시간 데이터 처리 및 통계
- ML 기반 상품 추천 시스템
- 실시간 대시보드 및 모니터링
- 에러 처리 및 Slack 알림
- 확장 가능한 아키텍처 (수백만 건 이상 처리 가능)

---

## 프로젝트 구조

```
comerce-kafka/
├── airflow/                      # Airflow DAGs 및 스케줄링
│   ├── dags/
│   │   ├── daily_model_training.py    # ML 모델 일일 재학습
│   │   └── data_validation.py         # 데이터 검증
│   ├── logs/                          # Airflow 로그
│   └── plugins/                       # Airflow 플러그인
│
├── api/                          # FastAPI 추천 API
│   ├── __init__.py
│   └── main.py                        # API 엔드포인트
│
├── config/                       # 설정 파일
│   ├── __init__.py
│   └── settings.py                    # 환경변수 및 설정
│
├── data/                         # 데이터 디렉토리
│   └── raw/
│       ├── events.csv                 # 원본 이벤트 데이터 (2.7M rows)
│       ├── category_tree.csv          # 카테고리 계층 구조
│       ├── item_properties_part1.csv  # 상품 속성 1
│       └── item_properties_part2.csv  # 상품 속성 2
│
├── docker/                       # Docker 설정
│   ├── docker-compose.yml             # 전체 서비스 오케스트레이션
│   ├── Dockerfile.producer            # Producer 이미지
│   ├── Dockerfile.consumer            # Consumer 이미지
│   └── Dockerfile.spark               # Spark Streaming 이미지
│
├── docs/                         # 문서
│   └── architecture/                  # 아키텍처 문서
│
├── frontend/                     # Next.js 프론트엔드
│   ├── src/
│   ├── public/
│   └── package.json
│
├── models/                       # ML 모델 저장소
│   └── *.pkl                          # 학습된 추천 모델
│
├── sql/                          # SQL 스키마 및 스크립트
│   └── schema.sql                     # PostgreSQL 테이블 정의
│
├── src/                          # 소스 코드
│   ├── __init__.py
│   │
│   ├── producer/                      # Kafka Producer
│   │   ├── __init__.py
│   │   └── producer.py                # 이벤트 스트리밍
│   │
│   ├── consumer/                      # Kafka Consumer
│   │   ├── __init__.py
│   │   └── consumer_postgres.py       # PostgreSQL 저장
│   │
│   ├── spark/                         # Spark Streaming
│   │   ├── __init__.py
│   │   ├── streaming_consumer.py      # 메인 스트리밍 처리
│   │   ├── ml_data_processor.py       # ML 데이터 처리
│   │   ├── stats_processor.py         # 통계 계산
│   │   └── error_handler.py           # 에러 처리 및 알림
│   │
│   ├── ml/                            # ML 파이프라인
│   │   ├── __init__.py
│   │   ├── recommendation_model.py    # 추천 모델
│   │   └── data_preparation.py        # 학습 데이터 준비
│   │
│   └── rawdata_postgres_upload/       # 원본 데이터 업로드
│       ├── load_category_tree.py
│       └── load_item_properties.py
│
├── .dockerignore                 # Docker 빌드 제외 파일
├── .env                          # 환경변수 (미포함)
├── .gitignore                    # Git 제외 파일
├── README.md                     # 프로젝트 문서
└── requirements.txt              # Python 패키지 의존성
```

---

## 설치 및 실행

### 1. 환경 설정

#### 필수 요구사항
- Docker Desktop
- Git

---

### 2. Docker로 모든 서비스 실행

```bash
# Docker Compose로 모든 서비스 시작
cd docker
docker-compose up -d

# 실행 확인
docker-compose ps
```

#### 예상 결과
```
NAME                IMAGE                             COMMAND                   SERVICE             STATUS
consumer-postgres   docker-consumer-postgres          "python -u src/consu…"   consumer-postgres   Up
kafka               confluentinc/cp-kafka:7.5.0       "/etc/confluent/dock…"   kafka               Up (healthy)
postgres            postgres:16                       "docker-entrypoint.s…"   postgres            Up (healthy)
producer            docker-producer                   "python -u src/produ…"   producer            Up
spark-streaming     docker-spark-streaming            "python -u src/spark…"   spark-streaming     Up
zookeeper           confluentinc/cp-zookeeper:7.5.0   "/etc/confluent/dock…"   zookeeper           Up (healthy)
```

---

### 3. 서비스 로그 확인

```bash
# Producer 로그 확인
docker-compose logs -f producer

# Consumer PostgreSQL 로그 확인
docker-compose logs -f consumer-postgres

# Spark Streaming 로그 확인
docker-compose logs -f spark-streaming

# 모든 서비스 로그 확인
docker-compose logs -f
```

#### Producer 예상 로그
```
============================================================
Kafka Producer 시작
============================================================
Kafka 연결 성공: ['kafka:9093']
데이터 로드 완료: 2756101개

토픽 'clickstream'로 2756101개 메시지 전송 시작
일반 모드: 4초 간격 전송
```

#### Consumer PostgreSQL 예상 로그
```
============================================================
Kafka Consumer (PostgreSQL) 시작
============================================================
PostgreSQL 연결 성공: postgres:5432/ecommerce
Kafka 연결 성공: ['kafka:9093']
토픽 구독: clickstream

메시지 대기 중...
종료하려면 Ctrl+C 누르세요
```

#### Spark Streaming 예상 로그
```
배치 1 저장 중... (레코드: 1개)
[실시간 통계] 배치 1 저장 중... (1개)
[실시간 통계] 배치 1 저장 완료
배치 1 저장 완료
```

---

### 4. 데이터 확인

```bash
# PostgreSQL 접속
docker exec -it postgres psql -U admin -d ecommerce

# 테이블 목록 확인
\dt

# 데이터 조회
SELECT COUNT(*) FROM clickstream_events;
SELECT COUNT(*) FROM live_clickstream_events;
SELECT COUNT(*) FROM windowed_stats;

# 이벤트 타입별 통계
SELECT event, COUNT(*) as count
FROM live_clickstream_events
GROUP BY event
ORDER BY count DESC;

# 최근 5분 윈도우 통계
SELECT window_start, window_end, event, event_count, unique_users
FROM windowed_stats
ORDER BY window_start DESC
LIMIT 5;

# 종료
\q
```

#### 예상 결과
```
 count
-------
   321
(1 row)

    event    | count
-------------+-------
 view        |   344
 addtocart   |    15
 transaction |     1
(3 rows)
```


## 데이터베이스 스키마

### 주요 테이블

#### 1. clickstream_events
Consumer PostgreSQL이 저장하는 원본 이벤트 데이터

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | SERIAL | 자동 증가 ID (Primary Key) |
| timestamp | BIGINT | 이벤트 타임스탬프 |
| visitorid | INTEGER | 방문자 ID |
| event | VARCHAR(50) | 이벤트 타입 (view, addtocart, transaction) |
| itemid | INTEGER | 상품 ID |
| transactionid | INTEGER | 거래 ID (nullable) |
| created_at | TIMESTAMP | 레코드 생성 시간 |

#### 2. live_clickstream_events
Spark Streaming이 저장하는 실시간 이벤트 데이터

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| timestamp | BIGINT | 이벤트 타임스탬프 |
| visitorid | INTEGER | 방문자 ID |
| event | VARCHAR(50) | 이벤트 타입 |
| itemid | INTEGER | 상품 ID |
| transactionid | INTEGER | 거래 ID (nullable) |

#### 3. windowed_stats
Spark Streaming이 계산하는 5분 윈도우 집계 통계

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| window_start | TIMESTAMP | 윈도우 시작 시간 |
| window_end | TIMESTAMP | 윈도우 종료 시간 |
| event | VARCHAR(50) | 이벤트 타입 |
| event_count | BIGINT | 이벤트 발생 횟수 |
| unique_users | BIGINT | 고유 사용자 수 |
| unique_items | BIGINT | 고유 상품 수 |

#### 4. event_statistics
Spark Streaming이 계산하는 실시간 통계

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| event | VARCHAR(50) | 이벤트 타입 |
| event_count | BIGINT | 이벤트 발생 횟수 |
| unique_users | BIGINT | 고유 사용자 수 |
| unique_items | BIGINT | 고유 상품 수 |

---


---

## 기술 스택

### 인프라
- **Docker & Docker Compose**: 컨테이너 오케스트레이션
- **Apache Kafka 7.5.0**: 메시지 브로커
- **Apache Zookeeper**: Kafka 코디네이션
- **PostgreSQL 16**: 데이터 저장소

### 애플리케이션
- **Python 3.10**: 프로그래밍 언어
- **Apache Spark 3.5.0**: 분산 스트림 처리
- **PySpark**: Spark Python API

### 주요 라이브러리
- `kafka-python 2.0.2`: Kafka 클라이언트
- `pyspark 3.5.0`: Spark 스트리밍
- `pandas 2.1.0`: 데이터 처리
- `psycopg2-binary 2.9.9`: PostgreSQL 드라이버
- `python-dotenv 1.0.0`: 환경변수 관리



---

## TODO 및 개선 사항

### 1. ML 학습 파이프라인 구축 

**목표**: 클릭스트림 데이터를 기반으로 상품 추천 모델 학습

**작업 내용**:
- [ ]  추천 모델 구현
- [ ] 모델 평가 구현
- [ ] 모델 학습 스크립트 작성 (`src/ml/train_model.py`)
- [ ] 학습된 모델 저장 (`models/*.pkl`)
- [ ] Airflow DAG 연동 (일일 재학습 자동화)



---

### 2. ML 데이터 준비 및 전처리 

**목표**: 학습에 필요한 데이터 준비 및 특징 엔지니어링

**작업 내용**:
- [ ] PostgreSQL에서 학습 데이터 추출
  - `clickstream_events` 테이블에서 view, addtocart, transaction 이벤트 추출
- [ ] 데이터 전처리

- [ ] 특징 엔지니어링
  - 사용자 행동 패턴 특징 추출
  - 상품 인기도 특징 추출
  - 시간대별 특징 추출
- [ ] 학습/검증/테스트 데이터 분리 (70/15/15)


---

### 3. Producer 전송 속도 최적화 

**목표**: 초당 메시지 처리량 제한 및 안정적인 스트리밍

**현재 상태**:
- 지금 엄청 느리게 들어감

**개선 사항**:
- [ ] 속도 증가
- [ ] 배치 설계
- [ ] 에러 처리



---

### 4. 실시간 대시보드 구현  

**작업 내용**:
- [ ] Streamlit 대시보드 구현
- [ ] 실시간 메트릭 시각화
  - 이벤트 타입별 발생 빈도
  - 시간대별 트래픽 패턴
  - 인기 상품 Top 10
- [ ] Docker Compose에 대시보드 서비스 추가


---

### 5. API 서버 구현 

**작업 내용**:
- [ ] FastAPI 추천 엔드포인트 구현
  - `GET /recommendations/{user_id}`: 사용자 맞춤 추천
  - `GET /similar-items/{item_id}`: 유사 상품 추천
- [ ] API 문서 자동 생성 (Swagger)
- [ ] Docker Compose에 API 서비스 추가


---

### 6. 모니터링 및 알림 

**작업 내용**:
- [ ] Slack 알림 연동 (에러 발생 시)
- [ ] Prometheus + Grafana 모니터링
- [ ] 로그 수집 (ELK Stack)


---

## 우선순위 요약

| 순위 | 작업 | 우선순위 | 예상 기간 |
|------|------|----------|-----------|
| 1 | ML 학습 파이프라인 구축 | 높음 | 2-3일 |
| 2 | ML 데이터 준비 및 전처리 | 중간 | 1-2일 |
| 3 | Producer 전송 속도 최적화 | 중간 | 1일 |
| 4 | 모니터링 및 알림 |  중간 | 2-3일 |
| 5 | 실시간 대시보드 구현 | 낮음 | 2-3일 |
| 6 | API 서버 구현 | 낮음 | 2일 |


