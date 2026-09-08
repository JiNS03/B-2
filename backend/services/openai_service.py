"""
OpenAI Chat Completions 호출
- 데이터 요약을 시스템 프롬프트에 주입하는 컨텍스트 주입 로직의 핵심
"""
import os
from openai import OpenAI
from typing import Dict, Any, List

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        _client = OpenAI(api_key=api_key)
    return _client


SYSTEM_PROMPT_TEMPLATE = """당신은 사용자의 미디어 시청 습관(OTT, 유튜브, 쇼츠, 릴스 등)을 분석하는 AI 비서입니다.

[사용자 시청 데이터 요약]
- 기록 기간: {period}
- 총 기록 일수: {count}일
- 일 평균 시청 시간: {average_minutes_per_day}분
- 최대/최소 일 시청 시간: {max_minutes}분 / {min_minutes}분
- 숏폼(쇼츠/릴스) 비중: {shortform_ratio}
- 롱폼(OTT/일반영상) 비중: {longform_ratio}
- 주말 평균: {weekend_avg}분 / 평일 평균: {weekday_avg}분
- 최근 트렌드: {trend}

위 데이터를 근거로, 사용자의 질문에 구체적인 숫자를 활용해 답변하세요.
과도한 훈계나 비판은 하지 말고, 객관적인 정보 제공과 친근한 톤을 유지하세요.
데이터에 없는 내용은 추측하지 말고 모른다고 답하세요."""


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
        trend=summary["trend"],
    )


def ask_gpt(user_message: str, summary: Dict[str, Any], history: List[Dict[str, str]] = None) -> str:
    """
    시스템 프롬프트(데이터 요약 주입) + 대화 히스토리 + 새 질문을 GPT에 전달하고 답변을 받는다.
    history: [{"role": "user"/"assistant", "content": "..."}]
    """
    client = _get_client()
    system_prompt = build_system_prompt(summary)

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=500,
        temperature=0.7,
    )
    return response.choices[0].message.content
