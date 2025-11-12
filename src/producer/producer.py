"""
Kafka Producer
CSV 파일을 읽어서 Kafka로 전송
"""

from kafka import KafkaProducer
import pandas as pd
import json
import time
import argparse
from tqdm import tqdm
import sys
import os
import math

# 상위 디렉토리 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    KAFKA_BROKERS,
    KAFKA_TOPIC,
    CSV_FILE_PATH,
    PRODUCER_INTERVAL
)


def create_producer():
    """Kafka Producer 생성"""
    def safe_json_serializer(v):
        """NaN을 null로 변환하는 JSON serializer"""
        import math
        # NaN 값을 null로 변환
        def convert_nan(obj):
            if isinstance(obj, float) and math.isnan(obj):
                return None
            return obj

        # dict의 모든 값에 대해 NaN 체크
        if isinstance(v, dict):
            v = {k: convert_nan(val) for k, val in v.items()}

        return json.dumps(v, allow_nan=False).encode('utf-8')

    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKERS,
            value_serializer=safe_json_serializer,
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        print(f"Kafka 연결 성공: {KAFKA_BROKERS}")
        return producer
    except Exception as e:
        print(f"Kafka 연결 실패: {e}")
        raise


def load_csv(file_path, sample=0):
    """CSV 파일 읽기"""
    try:
        if sample > 0:
            df = pd.read_csv(file_path, nrows=sample)
            print(f"데이터 로드 완료: {len(df)}개 (샘플 모드)")
        else:
            df = pd.read_csv(file_path)
            print(f"데이터 로드 완료: {len(df)}개")
        return df
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {file_path}")
        raise
    except Exception as e:
        print(f"CSV 로드 실패: {e}")
        raise


def send_messages(producer, df, topic, interval=4, batch_mode=False):
    """메시지 전송"""
    success_count = 0
    send_error = 0

    print(f"\n토픽 '{topic}'로 {len(df)}개 메시지 전송 시작")
    if batch_mode:
        print("배치 모드: 빠른 전송")
    else:
        print(f"일반 모드: {interval}초 간격 전송\n")

    # 데이터 전송
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="전송 중"):
        try:
            # 딕셔너리로 변환 후 NaN을 None으로 변환
            message = {}
            for key, value in row.to_dict().items():
                if pd.isna(value):
                    message[key] = None
                else:
                    message[key] = value

            # 파티션 키 생성 (visitorid 기준)
            partition_key = str(message.get('visitorid', idx))

            # Kafka 전송
            future = producer.send(topic, key=partition_key, value=message)
            future.get(timeout=10)

            success_count += 1

            # 일반 모드일 때만 대기
            if not batch_mode and interval > 0:
                time.sleep(interval)

        except Exception as e:
            send_error += 1
            if send_error <= 3:
                print(f"\n[전송 실패 {idx}] {e}")
            continue

    # 결과 출력
    print(f"\n{'='*50}")
    print(f"전송 성공: {success_count}개")
    if send_error > 0:
        print(f"전송 실패: {send_error}개")
    print(f"전체: {len(df)}개")
    print(f"{'='*50}")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='Kafka Producer')
    parser.add_argument('--file', type=str, default=CSV_FILE_PATH,
                        help=f'CSV 파일 경로 (기본값: {CSV_FILE_PATH})')
    parser.add_argument('--topic', type=str, default=KAFKA_TOPIC,
                        help=f'Kafka 토픽 (기본값: {KAFKA_TOPIC})')
    parser.add_argument('--sample', type=int, default=0,
                        help='샘플 개수 (0=전체)')
    parser.add_argument('--interval', type=int, default=PRODUCER_INTERVAL,
                        help=f'전송 간격(초) (기본값: {PRODUCER_INTERVAL})')
    parser.add_argument('--batch', action='store_true',
                        help='배치 모드 (지연 없이 빠른 전송)')

    args = parser.parse_args()

    print("=" * 60)
    print("Kafka Producer 시작")
    print("=" * 60)

    try:
        # 1. Kafka Producer 생성
        producer = create_producer()

        # 2. CSV 파일 읽기
        df = load_csv(args.file, args.sample)

        # 3. 메시지 전송
        send_messages(
            producer=producer,
            df=df,
            topic=args.topic,
            interval=args.interval,
            batch_mode=args.batch
        )

        # 4. 종료 처리
        print("\nProducer 종료 중...")
        producer.flush()
        producer.close()

        print("\n전송 완료!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n사용자가 중단했습니다")
        producer.close()
    except Exception as e:
        print(f"\n에러 발생: {e}")
        raise


if __name__ == '__main__':
    main()
