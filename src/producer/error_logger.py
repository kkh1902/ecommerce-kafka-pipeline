"""
Error Logger
실패한 메시지를 로컬 파일에 저장
"""

import json
import logging
from datetime import datetime
from pathlib import Path
import traceback

# 로그 디렉토리 설정
LOG_DIR = Path("logs/failed_messages")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def log_failed_message(message, error, index, partition_key):
    """
    실패한 메시지를 날짜별 파일에 저장

    Args:
        message (dict): 원본 메시지
        error (Exception): 발생한 에러
        index (int): 메시지 인덱스
        partition_key (str): 파티션 키

    파일명: logs/failed_messages/2025-11-15.jsonl
    """

    # 날짜별 파일
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{date_str}.jsonl"

    # 저장할 데이터
    error_record = {
        'timestamp': datetime.now().isoformat(),
        'index': index,
        'partition_key': partition_key,
        'message': message,
        'error': {
            'type': type(error).__name__,
            'message': str(error),
            'traceback': traceback.format_exc()
        }
    }

    try:
        # JSONL 형식으로 추가 (한 줄씩)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_record, ensure_ascii=False) + '\n')

        logger.warning(f"에러 로그 저장: {log_file} (index={index})")
        return True

    except Exception as e:
        # 파일 저장도 실패한 경우
        logger.critical(f"로그 저장 실패!!! {e}")
        logger.critical(f"데이터 손실 위험: {error_record}")
        return False


def get_failed_message_count(date_str=None):
    """
    특정 날짜의 실패 메시지 개수 조회

    Args:
        date_str (str): 날짜 (YYYY-MM-DD), None이면 오늘

    Returns:
        int: 실패 메시지 개수
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    log_file = LOG_DIR / f"{date_str}.jsonl"

    if not log_file.exists():
        return 0

    count = 0
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                count += 1

    return count
