"""
CSV 파일을 읽어 Firestore 'data' 컬렉션에 일괄 업로드하는 스크립트

사용법:
  1) .env 파일에 FIREBASE_SERVICE_ACCOUNT_JSON이 설정되어 있어야 합니다.
  2) CSV는 date, value, memo, platform, content_type 컬럼을 가져야 합니다.
     (memo, platform, content_type은 없어도 기본값으로 채워집니다)
  3) 실행: python seed_data.py sample_data.csv
     (파일명을 생략하면 기본값 sample_data.csv를 사용합니다)

주의: 이미 존재하는 데이터를 중복 업로드하지 않으려면,
      Firestore 콘솔에서 'data' 컬렉션을 먼저 비우고 실행하세요.
"""
import sys
import csv
from dotenv import load_dotenv

load_dotenv()

from services.firebase_service import get_firestore_client, DATA_COLLECTION  # noqa: E402


def seed_from_csv(csv_path: str):
    db = get_firestore_client()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("CSV에 데이터가 없습니다.")
        return

    batch = db.batch()
    collection_ref = db.collection(DATA_COLLECTION)
    count = 0

    for row in rows:
        doc_ref = collection_ref.document()
        payload = {
            "date": row["date"],
            "value": int(row["value"]),
            "memo": row.get("memo", ""),
            "platform": row.get("platform", "unknown"),
            "content_type": row.get("content_type", "long_form"),
        }
        batch.set(doc_ref, payload)
        count += 1

        # Firestore batch는 최대 500건 제한이 있어 500건마다 commit
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()

    batch.commit()
    print(f"총 {count}개의 데이터를 '{DATA_COLLECTION}' 컬렉션에 업로드했습니다.")


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "sample_data.csv"
    seed_from_csv(csv_file)
