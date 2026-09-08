"""
대화 기록 저장/조회/삭제 라우터
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from typing import List

from models.schemas import (
    ConversationCreate,
    ConversationSummaryOut,
    ConversationDetailOut,
    ChatMessage,
)
from services.firebase_service import get_firestore_client, CONVERSATIONS_COLLECTION

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationDetailOut, status_code=201)
def create_conversation(conv: ConversationCreate):
    """새 대화 저장 (chat 라우터에서 자동 저장 시에도 사용)"""
    db = get_firestore_client()

    title = conv.title
    if not title:
        first_user_msg = next((m.content for m in conv.messages if m.role == "user"), "새 대화")
        title = first_user_msg[:30]

    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "title": title,
        "created_at": created_at,
        "messages": [m.model_dump() for m in conv.messages],
    }
    _, doc_ref = db.collection(CONVERSATIONS_COLLECTION).add(payload)

    return ConversationDetailOut(
        id=doc_ref.id,
        title=title,
        created_at=created_at,
        messages=conv.messages,
    )


@router.get("", response_model=List[ConversationSummaryOut])
def list_conversations():
    """대화 목록 조회 (messages는 미포함, 개수만 반환)"""
    db = get_firestore_client()
    docs = db.collection(CONVERSATIONS_COLLECTION).stream()
    results = []
    for doc in docs:
        d = doc.to_dict()
        results.append(
            ConversationSummaryOut(
                id=doc.id,
                title=d.get("title", "제목 없음"),
                created_at=d.get("created_at", ""),
                message_count=len(d.get("messages", [])),
            )
        )
    results.sort(key=lambda c: c.created_at, reverse=True)
    return results


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(conversation_id: str):
    """특정 대화의 전체 메시지 조회 (대화 불러오기)"""
    db = get_firestore_client()
    doc = db.collection(CONVERSATIONS_COLLECTION).document(conversation_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 id의 대화를 찾을 수 없습니다.")

    d = doc.to_dict()
    messages = [ChatMessage(**m) for m in d.get("messages", [])]
    return ConversationDetailOut(
        id=doc.id,
        title=d.get("title", "제목 없음"),
        created_at=d.get("created_at", ""),
        messages=messages,
    )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str):
    """대화 삭제"""
    db = get_firestore_client()
    doc_ref = db.collection(CONVERSATIONS_COLLECTION).document(conversation_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="해당 id의 대화를 찾을 수 없습니다.")
    doc_ref.delete()
    return None
