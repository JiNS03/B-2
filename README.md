# WATCH LOG — 내 시청 습관을 아는 AI 비서

## 1. 서비스 소개

일반적인 ChatGPT는 "이번 달 유튜브 얼마나 봤어?" 라고 물어도 내 데이터를 모르기 때문에 답할 수 없습니다.

**WATCH LOG**는 사용자의 OTT(넷플릭스 등) / 유튜브 / 쇼츠 / 릴스 시청 기록을 저장하고, 그 데이터를 요약해 AI의 시스템 프롬프트에 주입함으로써 **"내 시청 습관을 실제로 아는" AI 비서**와 대화할 수 있는 서비스입니다.

- 시청 기록을 CRUD로 관리
- 기간 / 평균 / 숏폼 비중 / 최근 추세를 자동 계산
- 계산된 요약을 GPT에 전달해 데이터 기반 답변 생성
- 모든 대화를 저장하고 다시 불러와 이어갈 수 있음

## 2. 기술 스택

| 구분 | 기술 |
|---|---|
| 백엔드 | FastAPI, Python 3.10+ |
| 데이터베이스 | Firebase Firestore |
| AI | OpenAI API (gpt-4o-mini) |
| 프론트엔드 | HTML / CSS / Vanilla JavaScript (프레임워크 미사용) |
| 배포 | Render(백엔드), Vercel(프론트엔드) |

## 3. 배포 URL

| 항목 | URL |
|---|---|
| 프론트엔드 | (Vercel 배포 후 URL 입력) |
| 백엔드 API | (Render 배포 후 URL 입력) |
| Swagger 문서 | (백엔드 URL)/docs |

## 4. 로컬 실행 방법

### 4-1. 백엔드

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY, FIREBASE_SERVICE_ACCOUNT_JSON을 채워넣는다

# (최초 1회) 샘플 데이터 생성 + Firestore 업로드
python generate_sample_csv.py
python seed_data.py sample_data.csv

uvicorn main:app --reload
# http://localhost:8000/docs 에서 Swagger UI 확인
```

### 4-2. 프론트엔드

```bash
cd frontend
# config.js의 API_BASE_URL이 http://localhost:8000 인지 확인
# VSCode Live Server 등으로 index.html 실행, 또는:
python -m http.server 5500
# http://localhost:5500 접속
```

## 5. 환경 변수 (최소 세트)

`backend/.env.example` 참고

| 변수명 | 설명 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase 서비스 계정 키 JSON 전체(한 줄 문자열) |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 (쉼표 구분, 배포 시 프론트 도메인으로 제한) |

프론트엔드(`frontend/config.js`)

| 변수명 | 설명 |
|---|---|
| `API_BASE_URL` | 백엔드 배포 URL |

## 6. 데이터 준비 방법

1. `generate_sample_csv.py`로 현실적인 패턴(주말 증가, 숏폼 비중 점진적 증가)을 반영한 150일치 더미 CSV를 생성하거나,
2. 본인의 실제 시청 기록(Google Takeout의 YouTube 시청 기록, Netflix 시청 활동 다운로드 등)을 `date, value, memo, platform, content_type` 컬럼으로 가공해 CSV로 준비합니다.
3. `python seed_data.py <csv파일명>` 으로 Firestore에 일괄 업로드합니다.

## 7. API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/data` | 시청 기록 추가 |
| GET | `/api/data` | 시청 기록 목록 조회 |
| PUT | `/api/data/{id}` | 시청 기록 수정 |
| DELETE | `/api/data/{id}` | 시청 기록 삭제 |
| GET | `/api/data/summary` | 데이터 요약 (프롬프트 주입용) |
| POST | `/api/conversations` | 대화 저장 |
| GET | `/api/conversations` | 대화 목록 조회 |
| GET | `/api/conversations/{id}` | 특정 대화 전체 조회 (불러오기) |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| POST | `/api/chat` | AI 챗봇 (요약 조회 → 프롬프트 주입 → GPT 호출 → 대화 자동 저장) |

## 8. 컨텍스트 주입 흐름

```
POST /api/chat
   │
   ├─ 1) summary_service.build_summary() 로 최신 요약 계산
   │
   ├─ 2) openai_service.build_system_prompt(summary) 로
   │      시스템 프롬프트에 요약값 삽입
   │
   ├─ 3) OpenAI Chat Completions 호출 (gpt-4o-mini)
   │
   └─ 4) 질문/답변을 conversations 컬렉션에 자동 저장
```

## 9. 배포 시 주의사항

- Render 무료 티어는 15분간 요청이 없으면 슬립 상태가 되어 첫 요청이 최대 1분 정도 걸릴 수 있습니다. 프론트엔드는 이를 감안해 로딩 스피너와 안내 문구를 표시합니다.
- `FIREBASE_SERVICE_ACCOUNT_JSON`, `OPENAI_API_KEY`는 절대 코드/깃허브에 커밋하지 않고 Render 환경변수 설정 화면에서 등록합니다.
- 배포 후 `ALLOWED_ORIGINS`를 Vercel 프론트 도메인으로 좁혀 CORS를 제한하는 것을 권장합니다.

## 10. 제출 스크린샷 체크리스트

- [ ] 데이터 요약이 보이는 채팅 화면 (질문 + 답변 포함)
- [ ] 데이터 관리 화면 (추가/수정/삭제 중 최소 1개 동작)
- [ ] 대화 기록 화면 (불러오기 동작 포함)
