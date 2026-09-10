"""
AI 챗봇의 시스템 프롬프트 생성 + 질문 유형(분석/잡담) 분류 로직.
gemini_service.py와 llama_service.py가 이 모듈을 공통으로 사용해서,
어느 쪽 AI를 쓰든 동일한 프롬프트와 답변 길이 정책을 적용받게 한다.
"""
from typing import Dict, Any

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
데이터에 없는 내용은 추측하지 말고 모른다고 답하세요.

[답변 형식 주의사항]
- 화면이 마크다운을 지원하지 않으므로 **굵게**, # 제목, - 목록 같은 마크다운 문법을 쓰지 말고 평범한 문장으로만 답하세요."""

# 이 키워드들이 포함되면 "데이터 분석 질문"으로 판단해서 더 길게(더 많은 토큰으로) 답하게 한다.
# 그 외(인사말, 잡담 등)는 짧게 답하도록 해서 토큰 제한에 걸려 답변이 끊기는 일을 방지한다.
ANALYSIS_KEYWORDS = [
    "분석", "시청", "데이터", "통계", "트렌드", "추이", "평균", "비교", "패턴", "습관",
    "얼마나", "숏폼", "롱폼", "유튜브", "넷플릭스", "플랫폼", "기간", "요약", "비중", "추세",
    "많이", "적게", "얼마", "몇 분", "몇분", "몇 시간", "몇시간",
]

PLATFORM_LABELS = {
    "youtube": "유튜브",
    "youtube_music": "유튜브 뮤직",
    "instagram_reels": "인스타 릴스",
    "netflix": "넷플릭스",
    "disney_plus": "디즈니+",
    "watcha": "왓챠",
    "tiktok": "틱톡",
}


def looks_like_analysis_question(message: str) -> bool:
    return any(kw in message for kw in ANALYSIS_KEYWORDS)


def length_instruction_and_max_tokens(user_message: str):
    """질문 유형에 따라 (답변 길이 지침 문장, 토큰 한도)를 반환한다."""
    if looks_like_analysis_question(user_message):
        instruction = "이번 질문은 데이터 분석/통계 질문으로 보입니다. 필요한 만큼 구체적인 숫자를 들어 설명하되, 8문장을 넘기지 마세요."
        max_tokens = 2000
    else:
        instruction = "이번 질문은 간단한 인사말이나 잡담으로 보입니다. 데이터를 억지로 언급하지 말고 1~2문장으로 짧고 자연스럽게 답하세요."
        max_tokens = 400
    return instruction, max_tokens


def _format_platform_summary(platform_breakdown: Dict[str, Any]) -> str:
    """platform_breakdown 딕셔너리를 프롬프트에 넣기 좋은 한 줄 문자열로 변환"""
    if not platform_breakdown:
        return "데이터 없음"

    parts = []
    for platform, stats in platform_breakdown.items():
        label = PLATFORM_LABELS.get(platform, platform)
        ratio_pct = round(stats["ratio"] * 100)
        parts.append(f"{label} {stats['total_minutes']}분({ratio_pct}%)")

    return ", ".join(parts)


def build_base_system_prompt(summary: Dict[str, Any]) -> str:
    """데이터 요약이 주입된 기본 시스템 프롬프트 (답변 길이 지침은 별도로 붙임)"""
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


def build_system_prompt(user_message: str, summary: Dict[str, Any]) -> str:
    """기본 프롬프트 + 이번 질문 유형에 맞는 답변 길이 지침을 합친 최종 시스템 프롬프트"""
    base = build_base_system_prompt(summary)
    instruction, _ = length_instruction_and_max_tokens(user_message)
    return f"{base}\n\n{instruction}"
