"""
'가져오기 배치(import batch)' 관리 서비스.

Takeout HTML을 업로드할 때마다 하나의 배치로 묶어서 저장하고,
항상 그 중 하나만 '활성(active)' 상태로 둔다.
화면(요약/차트/테이블/챗봇)은 항상 활성 배치 + 수동 추가 데이터만 보여준다.

data 컬렉션의 각 문서는 batch_id 필드를 가진다.
  - batch_id가 없거나 None  -> 수동으로 추가한 데이터 (항상 표시됨)
  - batch_id가 있음         -> 그 배치가 활성 상태일 때만 표시됨
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from services.firebase_service import (
    get_firestore_client,
    DATA_COLLECTION,
    IMPORT_BATCHES_COLLECTION,
)


def list_batches() -> List[Dict[str, Any]]:
    db = get_firestore_client()
    docs = db.collection(IMPORT_BATCHES_COLLECTION).stream()
    batches = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        batches.append(d)
    batches.sort(key=lambda b: b.get("uploaded_at", ""), reverse=True)
    return batches


def get_active_batch_id() -> Optional[str]:
    db = get_firestore_client()
    docs = db.collection(IMPORT_BATCHES_COLLECTION).where("is_active", "==", True).limit(1).stream()
    for doc in docs:
        return doc.id
    return None


def create_batch(filename: str, count: int, period: str, settings: Dict[str, Any]) -> str:
    """새 배치 문서를 만들고 활성 배치로 지정한다. 기존 배치는 전부 비활성화."""
    db = get_firestore_client()

    # 기존 배치 전부 비활성화
    existing = db.collection(IMPORT_BATCHES_COLLECTION).where("is_active", "==", True).stream()
    for doc in existing:
        doc.reference.update({"is_active": False})

    payload = {
        "filename": filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "record_count": count,
        "period": period,
        "settings": settings,
        "is_active": True,
    }
    _, ref = db.collection(IMPORT_BATCHES_COLLECTION).add(payload)
    return ref.id


def activate_batch(batch_id: str) -> None:
    db = get_firestore_client()
    doc_ref = db.collection(IMPORT_BATCHES_COLLECTION).document(batch_id)
    if not doc_ref.get().exists:
        raise ValueError("해당 배치를 찾을 수 없습니다.")

    existing = db.collection(IMPORT_BATCHES_COLLECTION).where("is_active", "==", True).stream()
    for doc in existing:
        doc.reference.update({"is_active": False})

    doc_ref.update({"is_active": True})


def delete_batch(batch_id: str) -> None:
    """배치 문서와 그 배치에 속한 data 레코드를 전부 삭제한다."""
    db = get_firestore_client()

    batch_ref = db.collection(IMPORT_BATCHES_COLLECTION).document(batch_id)
    if not batch_ref.get().exists:
        raise ValueError("해당 배치를 찾을 수 없습니다.")

    docs = db.collection(DATA_COLLECTION).where("batch_id", "==", batch_id).stream()
    batch_write = db.batch()
    count = 0
    for doc in docs:
        batch_write.delete(doc.reference)
        count += 1
        if count % 400 == 0:
            batch_write.commit()
            batch_write = db.batch()
    batch_write.commit()

    batch_ref.delete()
