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

---

## 서비스 관리

### 서비스 시작/중지

```bash
# 모든 서비스 시작
cd docker
docker-compose up -d

# 특정 서비스만 시작 (인프라만)
docker-compose up -d zookeeper kafka postgres

# 특정 서비스만 시작 (애플리케이션만)
docker-compose up -d producer consumer-postgres spark-streaming

# 서비스 중지
docker-compose down

# 서비스 중지 + 데이터 삭제
docker-compose down -v

# 서비스 재시작
docker-compose restart producer
docker-compose restart consumer-postgres
docker-compose restart spark-streaming
```

### 서비스 재빌드

코드를 수정한 경우 이미지를 재빌드해야 합니다:

```bash
# 모든 서비스 재빌드
docker-compose up -d --build

# 특정 서비스만 재빌드
docker-compose up -d --build producer
docker-compose up -d --build consumer-postgres
docker-compose up -d --build spark-streaming
```

---

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

## 트러블슈팅

### 1. 서비스가 시작되지 않는 경우

```bash
# 모든 컨테이너 상태 확인
cd docker
docker-compose ps

# 특정 서비스 로그 확인
docker-compose logs kafka
docker-compose logs postgres
docker-compose logs producer

# 모든 로그 확인
docker-compose logs
```

### 2. Kafka 연결 실패

**증상**: Producer/Consumer가 "Kafka 연결 실패" 메시지 표시

**해결 방법**:
```bash
# Kafka와 Zookeeper 상태 확인
docker-compose ps zookeeper kafka

# Kafka가 healthy 상태가 될 때까지 대기
docker-compose up -d kafka
docker-compose ps kafka

# Kafka 로그 확인
docker-compose logs kafka

# Kafka 재시작
docker-compose restart kafka
```

### 3. PostgreSQL 연결 실패

**증상**: Consumer/Spark가 "PostgreSQL 연결 실패" 메시지 표시

**해결 방법**:
```bash
# PostgreSQL 상태 확인
docker-compose ps postgres

# PostgreSQL 로그 확인
docker-compose logs postgres

# PostgreSQL 재시작
docker-compose restart postgres

# 직접 연결 테스트
docker exec -it postgres psql -U admin -d ecommerce -c "SELECT 1;"
```

### 4. Producer가 데이터를 보내지 않는 경우

**증상**: Producer 로그에 아무 메시지도 표시되지 않음

**해결 방법**:
```bash
# Producer 재시작
docker-compose restart producer

# Producer 로그 확인
docker-compose logs -f producer

# 데이터 파일 확인
docker exec producer ls -lh /app/data/raw/events.csv
```

### 5. Spark Streaming 에러 (Windows)

**증상**: `winutils.exe` 호환성 에러

**해결 방법**:
```bash
# Spark 컨테이너는 Linux 환경에서 실행되므로 winutils 문제 없음
# 만약 Windows에서 직접 실행하는 경우:
# 1. 올바른 winutils.exe 다운로드
# 2. HADOOP_HOME 환경변수 설정
# 3. 또는 Docker로 실행 (권장)
docker-compose up -d spark-streaming
```

### 6. 데이터가 PostgreSQL에 저장되지 않는 경우

**해결 방법**:
```bash
# Consumer 상태 확인
docker-compose ps consumer-postgres spark-streaming

# Consumer 로그 확인
docker-compose logs consumer-postgres
docker-compose logs spark-streaming

# PostgreSQL에서 테이블 확인
docker exec -it postgres psql -U admin -d ecommerce -c "\dt"

# 데이터 확인
docker exec -it postgres psql -U admin -d ecommerce -c "SELECT COUNT(*) FROM clickstream_events;"
docker exec -it postgres psql -U admin -d ecommerce -c "SELECT COUNT(*) FROM live_clickstream_events;"
```

### 7. 포트 충돌

**증상**: "port already allocated" 에러

**해결 방법**:
```bash
# 포트 사용 중인 프로세스 확인 (Windows)
netstat -ano | findstr :9092   # Kafka
netstat -ano | findstr :5432   # PostgreSQL

# 포트 사용 중인 프로세스 확인 (Mac/Linux)
lsof -i :9092   # Kafka
lsof -i :5432   # PostgreSQL

# 기존 컨테이너 완전히 제거 후 재시작
docker-compose down
docker-compose up -d
```

### 8. 디스크 공간 부족

**해결 방법**:
```bash
# Docker 디스크 사용량 확인
docker system df

# 사용하지 않는 이미지/컨테이너 정리
docker system prune -a

# 볼륨까지 삭제 (주의: 데이터 삭제됨)
docker system prune -a --volumes
```

### 9. 모든 서비스 완전히 초기화

```bash
# 모든 컨테이너와 데이터 삭제
cd docker
docker-compose down -v

# 이미지 재빌드
docker-compose build --no-cache

# 서비스 재시작
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

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

## 프로젝트 중단

```bash
# 모든 서비스 중지
cd docker
docker-compose down

# 데이터까지 삭제 (주의: PostgreSQL 데이터도 삭제됨)
docker-compose down -v

# 특정 서비스만 중지
docker-compose stop producer
docker-compose stop consumer-postgres
docker-compose stop spark-streaming
```

---

## TODO 및 개선 사항

### 1. ML 학습 파이프라인 구축 🔴 (우선순위: 높음)

**목표**: 클릭스트림 데이터를 기반으로 상품 추천 모델 학습

**작업 내용**:
- [ ] 협업 필터링 기반 추천 모델 구현
  - User-based Collaborative Filtering
  - Item-based Collaborative Filtering
- [ ] 모델 평가 메트릭 구현 (Precision, Recall, F1-Score)
- [ ] 모델 학습 스크립트 작성 (`src/ml/train_model.py`)
- [ ] 학습된 모델 저장 (`models/*.pkl`)
- [ ] Airflow DAG 연동 (일일 재학습 자동화)

**관련 파일**:
- `src/ml/recommendation_model.py`
- `src/ml/data_preparation.py`
- `airflow/dags/daily_model_training.py`

**예상 소요 시간**: 2-3일

---

### 2. ML 데이터 준비 및 전처리 🟡 (우선순위: 중간)

**목표**: 학습에 필요한 데이터 준비 및 특징 엔지니어링

**작업 내용**:
- [ ] PostgreSQL에서 학습 데이터 추출
  - `clickstream_events` 테이블에서 view, addtocart, transaction 이벤트 추출
  - 사용자-상품 상호작용 매트릭스 생성
- [ ] 데이터 전처리
  - 결측치 처리
  - 이상치 제거
  - 데이터 정규화
- [ ] 특징 엔지니어링
  - 사용자 행동 패턴 특징 추출
  - 상품 인기도 특징 추출
  - 시간대별 특징 추출
- [ ] 학습/검증/테스트 데이터 분리 (70/15/15)

**관련 파일**:
- `src/ml/data_preparation.py`
- `sql/ml_queries.sql` (생성 필요)

**예상 소요 시간**: 1-2일

---

### 3. Producer 전송 속도 최적화 🟡 (우선순위: 중간)

**목표**: 초당 메시지 처리량 제한 및 안정적인 스트리밍

**현재 상태**:
- 4초 간격으로 1개씩 전송 (초당 0.25개)
- 배치 모드: 지연 없이 빠른 전송

**개선 사항**:
- [ ] 초당 메시지 처리량 설정 옵션 추가
  - `--messages-per-second` 옵션 추가
  - 예: `--messages-per-second 100` → 초당 100개 전송
- [ ] 배치 크기 조절 기능
  - `--batch-size` 옵션 추가
  - 예: `--batch-size 1000` → 1000개씩 묶어서 전송
- [ ] 백프레셔(Backpressure) 처리
  - Kafka 브로커 부하 모니터링
  - 자동 전송 속도 조절
- [ ] 프로메테우스 메트릭 추가
  - 전송 속도 (messages/sec)
  - 전송 실패율
  - 평균 레이턴시

**관련 파일**:
- `src/producer/producer.py`

**예상 코드 예시**:
```bash
# 초당 1000개 전송 (안정적인 스트리밍)
python src/producer/producer.py --messages-per-second 1000

# 초당 100개씩 1000개 배치로 전송
python src/producer/producer.py --messages-per-second 100 --batch-size 1000
```

**예상 소요 시간**: 1일

---

### 4. 실시간 대시보드 구현 🟢 (우선순위: 낮음)

**작업 내용**:
- [ ] Streamlit 대시보드 구현
- [ ] 실시간 메트릭 시각화
  - 이벤트 타입별 발생 빈도
  - 시간대별 트래픽 패턴
  - 인기 상품 Top 10
- [ ] Docker Compose에 대시보드 서비스 추가

**예상 소요 시간**: 2-3일

---

### 5. API 서버 구현 🟢 (우선순위: 낮음)

**작업 내용**:
- [ ] FastAPI 추천 엔드포인트 구현
  - `GET /recommendations/{user_id}`: 사용자 맞춤 추천
  - `GET /similar-items/{item_id}`: 유사 상품 추천
- [ ] API 문서 자동 생성 (Swagger)
- [ ] Docker Compose에 API 서비스 추가

**예상 소요 시간**: 2일

---

### 6. 모니터링 및 알림 🟡 (우선순위: 중간)

**작업 내용**:
- [ ] Slack 알림 연동 (에러 발생 시)
- [ ] Prometheus + Grafana 모니터링
- [ ] 로그 수집 (ELK Stack)

**예상 소요 시간**: 2-3일

---

## 우선순위 요약

| 순위 | 작업 | 우선순위 | 예상 기간 |
|------|------|----------|-----------|
| 1 | ML 학습 파이프라인 구축 | 🔴 높음 | 2-3일 |
| 2 | ML 데이터 준비 및 전처리 | 🟡 중간 | 1-2일 |
| 3 | Producer 전송 속도 최적화 | 🟡 중간 | 1일 |
| 4 | 모니터링 및 알림 | 🟡 중간 | 2-3일 |
| 5 | 실시간 대시보드 구현 | 🟢 낮음 | 2-3일 |
| 6 | API 서버 구현 | 🟢 낮음 | 2일 |

**권장 작업 순서**: 2 → 1 → 3 → 6 → 4 → 5

---

## 라이센스

MIT License

---

## 문의

프로젝트 관련 문의사항은 이슈를 등록해주세요.
