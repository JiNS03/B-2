# WATCH LOG 프로젝트 개발 보고서

-b-2-pi.vercel.app

**내 시청 습관을 아는 AI 비서** — 시계열 데이터 분석 + 컨텍스트 주입 AI 챗봇 서비스

작성일: 2026-09

---

## 1. 프로젝트 개요

일반적인 AI 챗봇은 사용자의 개인 데이터를 모른 채 답변한다는 한계가 있다. 본 프로젝트는 사용자의 **OTT/유튜브/유튜브 뮤직 시청 기록**을 수집·분석하고, 그 요약 정보를 AI의 시스템 프롬프트에 주입함으로써 "내 상황을 아는" 개인화된 AI 비서를 구현하는 것을 목표로 했다.

핵심 학습 목표는 다음과 같다.

- 시계열 데이터 분석 및 요약 정보 생성
- FastAPI 기반 백엔드를 라우터/서비스 계층으로 분리
- Firestore를 이용한 CRUD 구현
- "데이터 요약을 시스템 프롬프트에 주입"하는 컨텍스트 주입 방식 이해
- 실제 배포 환경(Render, Vercel)에서의 CORS/환경변수/장애 대응

---

## 2. 기술 스택

| 구분 | 기술 |
|---|---|
| 백엔드 | FastAPI (Python 3.11) |
| 데이터베이스 | Firebase Firestore |
| AI | Google Gemini (1차) → Llama 3.3 70B via Groq (자동 폴백) |
| 프론트엔드 | HTML / CSS / Vanilla JavaScript (프레임워크 미사용) |
| 시각화 | Chart.js (CDN) |
| 배포 | Render(백엔드), Vercel(프론트엔드) |
| HTML 파싱 | BeautifulSoup4 + lxml |

---

## 3. 아키텍처

```
[프론트엔드 - Vercel]
  채팅(플로팅 위젯) / 인사이트 / 데이터 관리 / 가져오기 / 대화 기록
        │  fetch (REST)
        ▼
[백엔드 - Render, FastAPI]
  routers/  ─ data.py, conversations.py, chat.py, imports.py
  services/ ─ firebase_service, summary_service, batch_service,
              youtube_import_service, ai_prompt, gemini_service, llama_service
        │
        ▼
[Firestore]
  data (시청 기록) / conversations (대화 기록) / import_batches (업로드 배치)
```

### 3-1. 컨텍스트 주입 흐름

```
POST /api/chat
  1) summary_service.build_summary() 로 최신 요약(기간/평균/추세/플랫폼별 비중) 계산
  2) ai_prompt.build_system_prompt() 로 시스템 프롬프트에 요약 삽입
  3) Gemini 호출 시도 → 실패 시 Llama(Groq)로 자동 폴백
  4) 질문/답변을 conversations 컬렉션에 자동 저장
```

### 3-2. 데이터 소스 이원화

- **수동 입력**: 데이터 관리 탭 폼으로 추가 (`batch_id` 없음 → 항상 화면에 표시)
- **자동 가져오기**: Google Takeout HTML 업로드 → 서버가 파싱·집계 → "가져오기 배치"로 저장 (`batch_id` 있음 → 활성 배치일 때만 표시)

---

## 4. 개발 과정 요약

### 4-1. 초기 구축
- 미션 요구사항(4대 기능: AI 채팅, 데이터 CRUD, 대화 기록, 배포)에 맞춰 FastAPI 백엔드와 바닐라 JS 프론트엔드 뼈대를 구성
- 주제를 "OTT/유튜브/쇼츠 시청 습관"으로 선정
- 시네마 티켓 콘셉트의 다크 테마 디자인 적용

### 4-2. 실제 데이터 연동 (Google Takeout)
- 처음에는 더미 데이터로 시작했으나, 실제 유튜브 시청 기록(Google Takeout)을 반영하기로 결정
- Takeout 데이터가 HTML 형식으로 제공됨에 따라 파싱 로직을 여러 차례 개선:
  - 헤더 텍스트("YouTube" vs "YouTube Music")로 플랫폼 구분
  - 영상 제목의 "#쇼츠" 키워드로 롱폼/숏폼 구분 (제목 자체는 저장하지 않음 — 개인정보 보호)
  - "목록을 확인함" 등 실제 시청이 아닌 활동 필터링
  - **시간 간격 기반 시청시간 추정**: 연속된 두 시청 기록 사이의 실제 시간 간격을 상한선으로 사용해, 몰아보기 시 비현실적으로 큰 시청시간이 계산되는 문제를 해결

### 4-3. UI/UX 개선
- 캘린더 히트맵, 시청 추이 라인 차트, 플랫폼별/롱폼-숏폼 도넛 차트 추가
- 다크/라이트 테마 토글 구현 (localStorage 저장)
- 채팅을 별도 탭에서 **우측 하단 플로팅 버튼 + 팝업 패널**로 변경
- 인사이트 탭에 **기간 슬라이더**(듀얼 레인지) 추가로 원하는 기간만 필터링 가능
- 플랫폼 선택에 따라 콘텐츠 형태(롱폼/숏폼) 선택지를 동적으로 제한 (예: 유튜브 뮤직 선택 시 숏폼 옵션 숨김)

### 4-4. 데이터 가져오기 시스템 고도화
- 로컬 파이썬 스크립트로 처리하던 Takeout 파싱 로직을 **백엔드 API化**
- 웹 화면에서 HTML 파일을 직접 업로드하면 서버가 자동 파싱 후 Firestore에 저장하도록 개선
- **가져오기 배치(import batch)** 개념 도입: 업로드할 때마다 하나의 배치로 관리하고, 그중 하나만 "활성 배치"로 지정해 화면에 표시. 이전 배치는 목록에서 조회·전환·삭제 가능

### 4-5. AI 연동 트러블슈팅
프로젝트 진행 중 AI 모델 연동에서 다수의 문제를 겪고 해결함 (5절 참고).

### 4-6. 배포
- 백엔드: Render Web Service (GitHub 연동, 자동 배포)
- 프론트엔드: Vercel (Root Directory를 `frontend`로 지정)
- CORS: `ALLOWED_ORIGINS` 환경변수로 프론트엔드 도메인만 허용

---

## 5. 주요 트러블슈팅 기록

| 문제 | 원인 | 해결 |
|---|---|---|
| Render 배포 시 `pydantic-core` 빌드 실패 | Render 기본 Python 버전(3.13)과 구버전 pydantic 비호환 | `runtime.txt`로 Python 3.11 버전 고정 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` 관련 500 에러 | Render 환경변수 미등록 | Render Environment 탭에 직접 등록 |
| 로컬 `.env`에서 JSON 파싱 에러 | 여러 줄 JSON을 `.env`에 그대로 붙여넣어 파싱 실패 | `json.dumps()`로 한 줄로 압축 후 저장 |
| 유튜브 뮤직이 전혀 구분되지 않음 | "제품:" 항목이 아니라 항목 상단 제목(header-cell)에 "YouTube Music" 표기가 있었음 | 헤더 텍스트 기준으로 우선 판별하도록 수정 |
| 하루 시청시간이 비현실적으로 큼 (500개 영상 × 8분 = 66시간) | 영상 개수 × 고정 평균시간 단순 곱셈 방식의 한계 | 연속 시청 간 실제 시간 간격을 상한으로 쓰는 방식으로 재계산 |
| `openai.NotFoundError: model_not_found` | Codyssey 공개 API의 모델명이 요청과 불일치 | `/v1/models`로 실제 지원 모델 확인 후 반영 |
| `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'` | `openai` 라이브러리와 최신 `httpx` 버전 비호환 | `httpx` 버전 고정 (이후 Gemini 전환으로 해당 없음) |
| Firestore `ValueError: default app already exists` | 동시 요청 시 `initialize_app()` 중복 호출 경쟁 상태 | `try/except ValueError`로 방어 코드 추가 |
| Gemini 모델 단종 (404) | `gemini-2.0-flash` → `gemini-3.6-flash`로 모델 교체 필요 | 환경변수 `GEMINI_MODEL` 값 및 기본값 변경 |
| Gemini 답변이 중간에 계속 끊김 | (1) 토큰 한도 부족 (2) "생각(thinking)" 모델이 추론에도 토큰 소모 | 질문 유형(분석/잡담)에 따라 토큰 한도를 차등 적용 |
| `google-genai`와 `pydantic==2.9.2` 설치 충돌 | `google-genai`가 `pydantic>=2.12.5` 요구 | `pydantic==2.12.5`로 버전 상향 |
| Gemini 할당량 소진 대비 | 단일 AI 제공자 의존 시 서비스 중단 위험 | Llama(Groq) 자동 폴백 로직 추가 |
| 대용량 Takeout 파일(38MB) 업로드 시 서버 다운 | Render 무료 티어(512MB 메모리) 한도 초과로 OOM 강제 종료 | `lxml` 파서로 속도는 개선했으나 **메모리 문제는 미해결** (6절 참고) |

---

## 6. 알려진 한계 및 향후 과제

### 6-1. 대용량 파일 업로드 시 서버 다운 (미해결)
- **현상**: 38MB 이상의 Takeout HTML을 업로드하면 Render 서버가 메모리 부족(OOM)으로 재시작됨
- **원인**: 현재 파싱 방식(BeautifulSoup)은 문서 전체를 한 번에 메모리 상의 트리 구조로 로드하는 방식이라, 원본 파일 크기의 5~10배에 달하는 메모리를 사용함. `lxml` 파서로 교체해 파싱 **속도**는 크게 개선했으나(45MB 기준 수 분 이상 → 36초), 메모리 사용량 자체는 구조적으로 줄어들지 않아 문제가 해결되지 않음
- **임시 대응**: 업로드 전 Takeout HTML 파일을 직접 편집해 최근 기간만 남기고 용량을 줄여서 업로드
- **근본 해결 방향**: `lxml.etree.iterparse` 등을 이용한 스트리밍 파싱으로 구조 변경 필요 (문서를 처음부터 순차적으로 읽으며 필요한 항목만 즉시 처리하고 메모리에서 해제하는 방식). 현재 시점에는 **미착수 상태**이며, 후속 작업으로 남겨둠

### 6-2. 쇼츠(숏폼) 판별의 한계
- Takeout 데이터의 URL만으로는 쇼츠 여부를 구분할 수 없어, 영상 제목에 포함된 "#쇼츠" 등의 키워드로 판별
- 제목에 해당 키워드가 없는 쇼츠 영상은 롱폼으로 오분류될 수 있음

### 6-3. 시청 시간 추정치의 한계
- Google Takeout은 실제 시청 지속시간을 제공하지 않으므로, "연속 시청 간격 기반 추정" 방식으로 근사치를 계산
- 실제 시청 행동과 정확히 일치하지 않을 수 있음 (사용자가 직접 평균 시청시간 가정치를 조정 가능하도록 UI 제공으로 일부 보완)

---

## 7. 최종 기능 목록

- **AI 채팅**: 플로팅 버튼 → 팝업 패널, Gemini/Llama 이중화, 질문 유형별 답변 길이 자동 조절
- **인사이트**: 캘린더 히트맵, 시청 추이 라인 차트, 플랫폼별/형태별 도넛 차트, 기간 슬라이더
- **데이터 관리**: CRUD, 플랫폼 필터, 플랫폼별 콘텐츠 형태 자동 제한
- **가져오기**: Takeout HTML 업로드(드래그앤드롭), 파싱 옵션(시작일/평균 시청시간) 사용자 설정, 배치 이력 관리(전환/삭제)
- **대화 기록**: 목록 조회, 불러오기(플로팅 패널에서 이어보기), 삭제
- **테마**: 다크/라이트 토글

---

## 8. 배포 정보

| 항목 | 내용 |
|---|---|
| 백엔드 | Render Web Service (`uvicorn main:app`) |
| 프론트엔드 | Vercel (Root Directory: `frontend`) |
| 데이터베이스 | Firebase Firestore |
| AI 제공자 | Google Gemini (1차), Groq Llama 3.3 70B (폴백) |

---

## 9. 백엔드 파일 구조

```
backend/
├── main.py
├── routers/
│   ├── data.py            # 시청 기록 CRUD + summary
│   ├── conversations.py   # 대화 저장/조회/삭제
│   ├── chat.py            # AI 챗봇 (Gemini → Llama 폴백)
│   └── imports.py         # Takeout 업로드 + 배치 관리
├── services/
│   ├── firebase_service.py
│   ├── summary_service.py       # 요약/통계/추세 계산, 활성 배치 필터링
│   ├── batch_service.py         # 가져오기 배치 생성/전환/삭제
│   ├── youtube_import_service.py # Takeout HTML 파싱 (lxml 기반)
│   ├── ai_prompt.py             # 공통 시스템 프롬프트 + 질문 분류
│   ├── gemini_service.py
│   └── llama_service.py
└── models/
    └── schemas.py
```
