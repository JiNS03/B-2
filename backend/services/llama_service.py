"""
Llama 모델 호출 (Groq API 사용).
Gemini 호출이 실패했을 때(할당량 초과 등) 자동으로 넘어가는 폴백(fallback) 용도.

Groq는 Llama 등 오픈소스 모델을 OpenAI와 동일한 요청/응답 형식으로 제공하는
무료 티어가 있는 서비스라서, 별도 SDK 없이 requests로 직접 호출한다.
API 키는 https://console.groq.com/keys 에서 무료로 발급받을 수 있다.
"""
import os
import requests
from typing import Dict, Any, List

from services.ai_prompt import build_system_prompt, length_instruction_and_max_tokens

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def ask_llama(user_message: str, summary: Dict[str, Any], history: List[Dict[str, str]] = None) -> str:
    """
    시스템 프롬프트(데이터 요약 주입) + 대화 히스토리 + 새 질문을 Llama(Groq)에 전달하고 답변을 받는다.
    history: [{"role": "user"/"assistant", "content": "..."}]
    """
    api_key = os.environ.get("LLAMA_API_KEY")
    if not api_key:
        raise RuntimeError("LLAMA_API_KEY 환경변수가 설정되지 않았습니다.")

    base_url = os.environ.get("LLAMA_BASE_URL", DEFAULT_BASE_URL)
    model_name = os.environ.get("LLAMA_MODEL", DEFAULT_MODEL)

    system_prompt = build_system_prompt(user_message, summary)
    _, max_tokens = length_instruction_and_max_tokens(user_message)

    # OpenAI 호환 형식: role은 system/user/assistant를 그대로 사용
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend({"role": h["role"], "content": h["content"]} for h in history)
    messages.append({"role": "user", "content": user_message})

    try:
        res = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Llama API 호출 중 네트워크 오류: {e}")

    if res.status_code != 200:
        raise RuntimeError(f"Llama API 오류 (상태 코드 {res.status_code}): {res.text[:300]}")

    data = res.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError("Llama API 응답 형식을 해석할 수 없습니다.")

    if not content:
        raise RuntimeError("Llama로부터 빈 응답을 받았습니다.")

    return content
