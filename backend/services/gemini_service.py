"""
Google Gemini(제미나이) API 호출
- 데이터 요약을 시스템 프롬프트에 주입하는 컨텍스트 주입 로직의 핵심
- API 키는 Google AI Studio(aistudio.google.com/apikey)에서 무료로 발급받을 수 있다.
"""
import os
from google import genai
from google.genai import types
from typing import Dict, Any, List

from services.ai_prompt import build_system_prompt, length_instruction_and_max_tokens

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        _client = genai.Client(api_key=api_key)
    return _client


def ask_gemini(user_message: str, summary: Dict[str, Any], history: List[Dict[str, str]] = None) -> str:
    """
    시스템 프롬프트(데이터 요약 주입) + 대화 히스토리 + 새 질문을 Gemini에 전달하고 답변을 받는다.
    history: [{"role": "user"/"assistant", "content": "..."}]
    """
    client = _get_client()
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

    system_prompt = build_system_prompt(user_message, summary)
    _, max_tokens = length_instruction_and_max_tokens(user_message)

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
            max_output_tokens=max_tokens,
            temperature=0.7,
        ),
    )

    if not response.text:
        # 토큰 한도 초과, 안전 필터 등으로 텍스트가 비어 응답이 오는 경우에 대한 안전장치
        raise RuntimeError("Gemini로부터 빈 응답을 받았습니다.")

    return response.text
