"""
Pydantic 모델 정의
- 요청(Request) 바디 검증
- 응답(Response) 형태 명세
"""
from pydantic import BaseModel, Field, field_validator
from datetime import date as date_type
from typing import Optional, List


# ---------------------------------------------------------
# 시청 기록 데이터 (data 컬렉션)
# ---------------------------------------------------------
class WatchRecordCreate(BaseModel):
    """새 시청 기록 추가용 요청 바디"""
    date: date_type = Field(..., description="기록 날짜 (YYYY-MM-DD)")
    value: int = Field(..., description="총 시청 시간(분)")
    memo: str = Field(default="", description="자유 메모")
    platform: str = Field(default="unknown", description="netflix / youtube / youtube_shorts / instagram_reels 등")
    content_type: str = Field(default="long_form", description="long_form 또는 short_form")

    @field_validator("value")
    @classmethod
    def value_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("시청 시간(value)은 0 이상이어야 합니다.")
        return v

    @field_validator("content_type")
    @classmethod
    def content_type_must_be_valid(cls, v: str) -> str:
        allowed = {"long_form", "short_form"}
        if v not in allowed:
            raise ValueError(f"content_type은 {allowed} 중 하나여야 합니다.")
        return v


class WatchRecordUpdate(BaseModel):
    """시청 기록 수정용 요청 바디 (부분 수정 허용)"""
    date: Optional[date_type] = None
    value: Optional[int] = None
    memo: Optional[str] = None
    platform: Optional[str] = None
    content_type: Optional[str] = None

    @field_validator("value")
    @classmethod
    def value_must_be_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("시청 시간(value)은 0 이상이어야 합니다.")
        return v


class WatchRecordOut(BaseModel):
    """시청 기록 응답 형태"""
    id: str
    date: str
    value: int
    memo: str = ""
    platform: str = "unknown"
    content_type: str = "long_form"


class SummaryMetrics(BaseModel):
    total_minutes: int
    average_minutes_per_day: float
    max_minutes: int
    min_minutes: int
    shortform_ratio: float
    longform_ratio: float
    weekend_avg: float
    weekday_avg: float


class PlatformBreakdownItem(BaseModel):
    total_minutes: int
    count: int
    ratio: float


class SummaryOut(BaseModel):
    period: str
    count: int
    metrics: SummaryMetrics
    platform_breakdown: dict[str, PlatformBreakdownItem] = Field(default_factory=dict)
    trend: str


# ---------------------------------------------------------
# 대화 기록 (conversations 컬렉션)
# ---------------------------------------------------------
class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)


class ConversationSummaryOut(BaseModel):
    """목록 조회 시 사용 (messages 미포함, 가벼운 응답)"""
    id: str
    title: str
    created_at: str
    message_count: int


class ConversationDetailOut(BaseModel):
    """단건 조회 시 사용 (messages 전체 포함)"""
    id: str
    title: str
    created_at: str
    messages: List[ChatMessage]


# ---------------------------------------------------------
# 챗봇 (chat)
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="사용자 질문")
    conversation_id: Optional[str] = Field(
        default=None, description="이어서 대화할 기존 conversation id (없으면 새로 생성)"
    )


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    summary_used: SummaryOut
