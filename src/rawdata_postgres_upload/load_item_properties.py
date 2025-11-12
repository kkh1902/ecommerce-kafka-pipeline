"""
Item Properties 데이터를 PostgreSQL에 로드  데이터가 많아서 copy 로 업로드
"""

import psycopg2
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
)


# ============== 테이블 생성 ==============
def create_table(cursor):

    # 있으면 제거
    cursor.execute("DROP TABLE IF EXISTS item_properties CASCADE")
    cursor.execute("""
        CREATE TABLE item_properties (
            id SERIAL PRIMARY KEY,
            timestamp BIGINT,
            itemid BIGINT NOT NULL,
            property VARCHAR(100),
            value TEXT
        )
    """)
    cursor.execute("CREATE INDEX idx_item_itemid ON item_properties(itemid)")
    cursor.execute("CREATE INDEX idx_item_property ON item_properties(property)")
    print("테이블 생성 완료")


# ============== CSV 파일 로드  copy 로 업로드 ==============
def load_csv(conn, csv_path):

    cursor = conn.cursor()

    print(f"로드 시작: {csv_path}")

    # COPY 명령으로 빠르게 로드
    with open(csv_path, 'r', encoding='utf-8') as f:
        cursor.copy_expert("""
            COPY item_properties (timestamp, itemid, property, value)
            FROM STDIN WITH CSV HEADER
        """, f)

    conn.commit()

    # 삽입된 개수 확인
    cursor.execute("SELECT COUNT(*) FROM item_properties")
    total = cursor.fetchone()[0]

    print(f"로드 완료")

    return total


# ============== 메인 실행 ==============
def main():

    print("Item Properties 로드 시작...\n")

    # PostgreSQL 연결
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    cursor = conn.cursor()

    # 테이블 생성
    create_table(cursor)
    conn.commit()

    # Part1 로드
    if os.path.exists("data/raw/item_properties_part1.csv"):
        print("\nPart 1 로드")
        load_csv(conn, "data/raw/item_properties_part1.csv")

    # Part2 로드
    if os.path.exists("data/raw/item_properties_part2.csv"):
        print("\nPart 2 로드")
        load_csv(conn, "data/raw/item_properties_part2.csv")

    # 최종 개수 확인
    cursor.execute("SELECT COUNT(*) FROM item_properties")
    total = cursor.fetchone()[0]
    print(f"\n완료: 총 {total:,}개 삽입")

    conn.close()


if __name__ == '__main__':
    main()
