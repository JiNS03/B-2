"""
시청 기록 데이터 CRUD + 요약(summary) 라우터
"""
from fastapi import APIRouter, HTTPException
from typing import List

from models.schemas import WatchRecordCreate, WatchRecordUpdate, WatchRecordOut, SummaryOut
from services.firebase_service import get_firestore_client, DATA_COLLECTION
from services.summary_service import build_summary, fetch_all_records

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("", response_model=WatchRecordOut, status_code=201)
def create_record(record: WatchRecordCreate):
    """새 시청 기록 추가 (수동 추가는 batch_id 없이 저장되어 항상 화면에 보임)"""
    db = get_firestore_client()
    payload = record.model_dump()
    payload["date"] = str(payload["date"])  # date -> str 직렬화

    _, doc_ref = db.collection(DATA_COLLECTION).add(payload)
    return WatchRecordOut(id=doc_ref.id, **payload)


@router.get("", response_model=List[WatchRecordOut])
def list_records():
    """
    시청 기록 목록 조회 (날짜순 정렬).
    가져오기 배치로 업로드된 데이터는 현재 활성 배치의 것만,
    수동 추가 데이터는 항상 포함한다.
    """
    records = fetch_all_records()
    return [
        WatchRecordOut(
            id=r["id"],
            date=r.get("date", ""),
            value=r.get("value", 0),
            memo=r.get("memo", ""),
            platform=r.get("platform", "unknown"),
            content_type=r.get("content_type", "long_form"),
        )
        for r in records
    ]


@router.get("/summary", response_model=SummaryOut)
def get_summary():
    """데이터 요약 (프롬프트 주입용)"""
    return build_summary()


@router.put("/{record_id}", response_model=WatchRecordOut)
def update_record(record_id: str, record: WatchRecordUpdate):
    """시청 기록 수정 (부분 수정 지원)"""
    db = get_firestore_client()
    doc_ref = db.collection(DATA_COLLECTION).document(record_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 id의 기록을 찾을 수 없습니다.")

    update_data = {k: v for k, v in record.model_dump(exclude_unset=True).items() if v is not None}
    if "date" in update_data:
        update_data["date"] = str(update_data["date"])

    if update_data:
        doc_ref.update(update_data)

    updated = doc_ref.get().to_dict()
    return WatchRecordOut(
        id=record_id,
        date=updated.get("date", ""),
        value=updated.get("value", 0),
        memo=updated.get("memo", ""),
        platform=updated.get("platform", "unknown"),
        content_type=updated.get("content_type", "long_form"),
    )


@router.delete("/{record_id}", status_code=204)
def delete_record(record_id: str):
    """시청 기록 삭제"""
    db = get_firestore_client()
    doc_ref = db.collection(DATA_COLLECTION).document(record_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="해당 id의 기록을 찾을 수 없습니다.")
    doc_ref.delete()
    return None
