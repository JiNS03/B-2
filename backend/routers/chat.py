"""
AI 챗봇 라우터
동작 흐름:
  1) 데이터 요약 조회 (summary_service.build_summary)
  2) 요약을 시스템 프롬프트에 삽입 (gemini_service.build_system_prompt)
  3) Gemini API 호출 (gemini_service.ask_gpt)
  4) 대화 내용을 conversations에 자동 저장
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse, SummaryOut
from services.summary_service import build_summary
from services.gemini_service import ask_gpt
from services.firebase_service import get_firestore_client, CONVERSATIONS_COLLECTION

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    db = get_firestore_client()

    # 1) 기존 대화 이어가기라면 히스토리 로드
    history = []
    conversation_ref = None
    existing_messages = []

    if req.conversation_id:
        conversation_ref = db.collection(CONVERSATIONS_COLLECTION).document(req.conversation_id)
        doc = conversation_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="해당 id의 대화를 찾을 수 없습니다.")
        data = doc.to_dict()
        existing_messages = data.get("messages", [])
        # GPT에 넘길 히스토리 형태로 변환 (role, content만)
        history = [{"role": m["role"], "content": m["content"]} for m in existing_messages]

    # 2) 데이터 요약 조회
    summary = build_summary()

    # 3) GPT 호출 (시스템 프롬프트에 요약 자동 삽입)
    try:
        reply = ask_gpt(user_message=req.message, summary=summary, history=history)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 4) 대화 저장 (자동)
    new_messages = existing_messages + [
        {"role": "user", "content": req.message},
        {"role": "assistant", "content": reply},
    ]

    if conversation_ref:
        conversation_ref.update({"messages": new_messages})
        conversation_id = req.conversation_id
    else:
        title = req.message[:30]
        created_at = datetime.now(timezone.utc).isoformat()
        _, new_ref = db.collection(CONVERSATIONS_COLLECTION).add(
            {"title": title, "created_at": created_at, "messages": new_messages}
        )
        conversation_id = new_ref.id

    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        summary_used=SummaryOut(**summary),
    )
