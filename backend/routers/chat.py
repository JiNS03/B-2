"""
AI 챗봇 라우터
동작 흐름:
  1) 데이터 요약 조회 (summary_service.build_summary)
  2) 요약을 시스템 프롬프트에 삽입
  3) AI 호출 — 먼저 Gemini를 시도하고, 실패하면(할당량 초과 등) 자동으로 Llama(Groq)로 폴백
  4) 대화 내용을 conversations에 자동 저장
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse, SummaryOut
from services.summary_service import build_summary
from services.gemini_service import ask_gemini
from services.llama_service import ask_llama
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

    # 3) AI 호출: Gemini를 먼저 시도하고, 실패하면(할당량 초과 등) Llama(Groq)로 자동 전환
    reply = None
    last_error = None

    try:
        reply = ask_gemini(user_message=req.message, summary=summary, history=history)
    except Exception as gemini_error:  # noqa: BLE001 - 폴백을 위해 어떤 예외든 일단 잡아서 다음 단계로
        last_error = gemini_error
        try:
            reply = ask_llama(user_message=req.message, summary=summary, history=history)
        except Exception as llama_error:  # noqa: BLE001
            last_error = llama_error

    if reply is None:
        raise HTTPException(
            status_code=500,
            detail=f"AI 응답 생성에 실패했습니다 (Gemini/Llama 둘 다 실패). 마지막 오류: {last_error}",
        )

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
