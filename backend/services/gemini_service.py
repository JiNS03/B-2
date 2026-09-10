"""
Google Gemini(제미나이) API 호출
- 데이터 요약을 시스템 프롬프트에 주입하는 컨텍스트 주입 로직의 핵심
- API 키는 Google AI Studio(aistudio.google.com/apikey)에서 무료로 발급받을 수 있다.
"""
import os
from google import genai
from google.genai import types
from typing import Dict, Any, List

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        _client = genai.Client(api_key=api_key)
    return _client


SYSTEM_PROMPT_TEMPLATE = """당신은 사용자의 미디어 시청 습관(OTT, 유튜브, 유튜브 뮤직, 쇼츠, 릴스 등)을 분석하는 AI 비서입니다.

[사용자 시청 데이터 요약]
- 기록 기간: {period}
- 총 기록 일수: {count}일
- 일 평균 시청 시간: {average_minutes_per_day}분
- 최대/최소 일 시청 시간: {max_minutes}분 / {min_minutes}분
- 숏폼(쇼츠/릴스) 비중: {shortform_ratio}
- 롱폼(OTT/일반영상) 비중: {longform_ratio}
- 주말 평균: {weekend_avg}분 / 평일 평균: {weekday_avg}분
- 플랫폼별 비중: {platform_summary}
- 최근 트렌드: {trend}

위 데이터를 근거로, 사용자의 질문에 구체적인 숫자를 활용해 답변하세요.
사용자가 "유튜브"와 "유튜브 뮤직"을 구분해서 물어보면 플랫폼별 비중 정보를 활용해 따로 답하세요.
과도한 훈계나 비판은 하지 말고, 객관적인 정보 제공과 친근한 톤을 유지하세요.
데이터에 없는 내용은 추측하지 말고 모른다고 답하세요."""


def _format_platform_summary(platform_breakdown: Dict[str, Any]) -> str:
    """platform_breakdown 딕셔너리를 프롬프트에 넣기 좋은 한 줄 문자열로 변환"""
    if not platform_breakdown:
        return "데이터 없음"

    label_map = {
        "youtube": "유튜브",
        "youtube_music": "유튜브 뮤직",
        "instagram_reels": "인스타 릴스",
        "netflix": "넷플릭스",
        "disney_plus": "디즈니+",
        "watcha": "왓챠",
        "tiktok": "틱톡",
    }

    parts = []
    for platform, stats in platform_breakdown.items():
        label = label_map.get(platform, platform)
        ratio_pct = round(stats["ratio"] * 100)
        parts.append(f"{label} {stats['total_minutes']}분({ratio_pct}%)")

    return ", ".join(parts)


def build_system_prompt(summary: Dict[str, Any]) -> str:
    metrics = summary["metrics"]
    return SYSTEM_PROMPT_TEMPLATE.format(
        period=summary["period"],
        count=summary["count"],
        average_minutes_per_day=metrics["average_minutes_per_day"],
        max_minutes=metrics["max_minutes"],
        min_minutes=metrics["min_minutes"],
        shortform_ratio=metrics["shortform_ratio"],
        longform_ratio=metrics["longform_ratio"],
        weekend_avg=metrics["weekend_avg"],
        weekday_avg=metrics["weekday_avg"],
        platform_summary=_format_platform_summary(summary.get("platform_breakdown", {})),
        trend=summary["trend"],
    )


def ask_gpt(user_message: str, summary: Dict[str, Any], history: List[Dict[str, str]] = None) -> str:
    """
    시스템 프롬프트(데이터 요약 주입) + 대화 히스토리 + 새 질문을 Gemini에 전달하고 답변을 받는다.
    history: [{"role": "user"/"assistant", "content": "..."}]

    함수 이름은 기존 코드(routers/chat.py)와의 호환을 위해 ask_gpt로 유지했다.
    """
    client = _get_client()
    system_prompt = build_system_prompt(summary)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

    # Gemini는 role을 "user"/"model"로 구분한다 (OpenAI의 "assistant"에 해당하는 게 "model")
    contents = []
    if history:
        for h in history:
            role = "model" if h["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=h["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=500,
            temperature=0.7,
        ),
    )
    return response.text