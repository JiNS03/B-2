"""
Firebase Firestore 연동
- 서비스 계정 키는 코드에 하드코딩하지 않고 환경 변수(FIREBASE_SERVICE_ACCOUNT_JSON)로 관리한다.
- FIREBASE_SERVICE_ACCOUNT_JSON에는 서비스 계정 키 JSON "문자열 전체"를 넣는다.
  (Render 등 배포 환경의 환경변수 값으로 JSON 한 줄 문자열을 그대로 붙여넣으면 된다)
"""
import json
import os
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore


@lru_cache()
def get_firestore_client():
    """
    Firestore 클라이언트를 1회만 초기화해서 재사용한다.
    동시에 여러 요청이 들어와 initialize_app()이 두 번 불릴 수 있는
    경쟁 상태(race condition)에 대비해, 이미 초기화된 경우의 예외는 무시한다.
    """
    if not firebase_admin._apps:
        service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if not service_account_json:
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않았습니다. "
                ".env 파일 또는 배포 환경변수를 확인하세요."
            )
        cred_dict = json.loads(service_account_json)
        cred = credentials.Certificate(cred_dict)
        try:
            firebase_admin.initialize_app(cred)
        except ValueError:
            # 다른 요청이 그 사이에 먼저 초기화를 마친 경우 -> 정상 상황이므로 무시
            pass

    return firestore.client()


# 컬렉션 이름 상수화 (오타 방지)
DATA_COLLECTION = "data"
CONVERSATIONS_COLLECTION = "conversations"
IMPORT_BATCHES_COLLECTION = "import_batches"
