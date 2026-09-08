"""
FastAPI 앱 진입점
로컬 실행: uvicorn main:app --reload
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
    
load_dotenv()

from routers import data, conversations, chat  # noqa: E402  (load_dotenv 이후 import)

app = FastAPI(
    title="시청 습관 AI 비서 API",
    description="OTT/유튜브/쇼츠 시청 기록을 분석하고, 그 데이터를 기반으로 대화하는 AI 비서 API",
    version="1.0.0",
)

# CORS 설정: ALLOWED_ORIGINS 환경변수(쉼표 구분)로 관리, 미설정 시 전체 허용(개발용)
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
allowed_origins = (
    ["*"] if allowed_origins_env.strip() == "*" else [o.strip() for o in allowed_origins_env.split(",")]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.get("/")
def root():
    return {"message": "시청 습관 AI 비서 API가 정상 동작 중입니다. /docs 에서 API 문서를 확인하세요."}


@app.get("/health")
def health_check():
    """Render 콜드스타트 방지용 헬스체크 엔드포인트"""
    return {"status": "ok"}
