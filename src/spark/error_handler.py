"""
Spark Consumer 에러 처리 모듈
- 에러 분류
- PostgreSQL error_events 저장
- Slack 알림
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Slack Webhook URL
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


class ErrorHandler:
    """에러 처리 클래스"""

    def __init__(self, postgres_host, postgres_port, postgres_db, postgres_user, postgres_password):
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_db = postgres_db
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password

    @staticmethod
    def classify_error(error_msg):
        """
        에러 메시지로 타입과 심각도 분류

        Returns:
            tuple: (error_type, severity)
        """
        error_msg_lower = error_msg.lower()

        if 'json' in error_msg_lower or 'parse' in error_msg_lower:
            return 'json_parse', 'INFO'
        elif 'connection' in error_msg_lower or 'connect' in error_msg_lower:
            return 'db_connection', 'CRITICAL'
        elif 'timeout' in error_msg_lower:
            return 'timeout', 'WARNING'
        elif 'constraint' in error_msg_lower or 'duplicate' in error_msg_lower:
            return 'constraint_violation', 'ERROR'
        else:
            return 'unknown', 'ERROR'

    @staticmethod
    def send_slack_alert(error_type, severity, error_message, batch_id=None):
        """
        Slack Webhook으로 알림 전송 (CRITICAL, ERROR만)

        Args:
            error_type: 에러 타입
            severity: 심각도 (INFO/WARNING/ERROR/CRITICAL)
            error_message: 에러 메시지
            batch_id: 배치 ID (옵션)
        """
        # INFO, WARNING은 알림 안 함
        if severity not in ['CRITICAL', 'ERROR']:
            return

        if not SLACK_WEBHOOK_URL:
            print(f"[WARNING] SLACK_WEBHOOK_URL 설정되지 않음 - 알림 건너뜀")
            return

        try:
            # 심각도에 따른 색상 및 이모지
            color_map = {
                'CRITICAL': 'danger',      # 빨간색
                'ERROR': 'warning',        # 주황색
            }
            emoji_map = {
                'CRITICAL': ':rotating_light:',
                'ERROR': ':warning:',
            }

            # Slack 메시지 생성
            message = {
                "username": "E-commerce Spark Error Alert",
                "attachments": [{
                    "color": color_map.get(severity, 'danger'),
                    "title": f"{emoji_map.get(severity, ':x:')} {severity} - {error_type}",
                    "text": error_message[:500],  # 최대 500자
                    "fields": [
                        {
                            "title": "Batch ID",
                            "value": str(batch_id) if batch_id else "N/A",
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True
                        }
                    ],
                    "footer": "Spark Streaming Consumer",
                    "ts": int(datetime.now().timestamp())
                }]
            }

            response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=5)
            if response.status_code == 200:
                print(f"[Slack] {severity} 알림 전송 완료")
            else:
                print(f"[Slack] 알림 전송 실패: {response.status_code}")

        except Exception as e:
            print(f"[Slack] 알림 전송 에러: {e}")

    def save_error_to_db(self, error_type, severity, error_message, batch_id=None, raw_data=None):
        """
        PostgreSQL error_events 테이블에 에러 저장

        Args:
            error_type: 에러 타입
            severity: 심각도
            error_message: 에러 메시지
            batch_id: 배치 ID (옵션)
            raw_data: 원본 데이터 (옵션)
        """
        try:
            import psycopg2
            import json

            conn = psycopg2.connect(
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
                user=self.postgres_user,
                password=self.postgres_password
            )
            cur = conn.cursor()

            # raw_data를 JSON으로 변환
            raw_data_json = json.dumps(raw_data) if raw_data else None

            cur.execute("""
                INSERT INTO error_events
                (error_type, error_message, severity, raw_data, batch_id, error_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                error_type,
                error_message[:1000],  # 최대 1000자
                severity,
                raw_data_json,
                batch_id,
                datetime.now()
            ))

            conn.commit()
            cur.close()
            conn.close()

            print(f"[DB] error_events 저장 완료 (Type: {error_type}, Severity: {severity})")

        except Exception as e:
            print(f"[DB] error_events 저장 실패: {e}")

    def handle_error(self, error_message, batch_id=None, raw_data=None):
        """
        통합 에러 처리: 분류 → DB 저장 → Slack 알림

        Args:
            error_message: 에러 메시지
            batch_id: 배치 ID (옵션)
            raw_data: 원본 데이터 (옵션)
        """
        # 1. 에러 분류
        error_type, severity = self.classify_error(error_message)

        # 2. DB 저장
        self.save_error_to_db(error_type, severity, error_message, batch_id, raw_data)

        # 3. Slack 알림 (CRITICAL, ERROR만)
        self.send_slack_alert(error_type, severity, error_message, batch_id)
