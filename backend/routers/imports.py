"""
'가져오기 배치' 라우터.
Takeout HTML 파일을 업로드하면 서버가 파싱 + 집계해서 Firestore에 저장하고,
그 묶음을 하나의 배치로 관리한다. 사용자는 이전에 올렸던 배치들 중
하나를 선택해서 화면에 보이는 데이터를 전환하거나, 필요 없는 배치를 지울 수 있다.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from models.schemas import ImportBatchOut, ImportResultOut
from services.firebase_service import get_firestore_client, DATA_COLLECTION
from services.youtube_import_service import parse_takeout_html
from services import batch_service

router = APIRouter(prefix="/api/imports", tags=["imports"])

MAX_UPLOAD_BYTES = 60 * 1024 * 1024  # 60MB — Takeout HTML은 커질 수 있어 여유 있게 설정


@router.get("", response_model=list[ImportBatchOut])
def list_import_batches():
    """지금까지 업로드한 배치 목록 (최신순)"""
    batches = batch_service.list_batches()
    return [
        ImportBatchOut(
            id=b["id"],
            filename=b.get("filename", "unknown.html"),
            uploaded_at=b.get("uploaded_at", ""),
            record_count=b.get("record_count", 0),
            period=b.get("period", ""),
            is_active=b.get("is_active", False),
        )
        for b in batches
    ]


@router.post("/{batch_id}/activate", response_model=ImportBatchOut)
def activate_import_batch(batch_id: str):
    """이 배치를 화면에 보이는 활성 데이터로 전환"""
    try:
        batch_service.activate_batch(batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="해당 배치를 찾을 수 없습니다.")

    batches = {b["id"]: b for b in batch_service.list_batches()}
    b = batches[batch_id]
    return ImportBatchOut(
        id=batch_id,
        filename=b.get("filename", "unknown.html"),
        uploaded_at=b.get("uploaded_at", ""),
        record_count=b.get("record_count", 0),
        period=b.get("period", ""),
        is_active=True,
    )


@router.delete("/{batch_id}", status_code=204)
def delete_import_batch(batch_id: str):
    """배치와 그 안의 시청 기록을 전부 삭제"""
    try:
        batch_service.delete_batch(batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="해당 배치를 찾을 수 없습니다.")
    return None


@router.post("/youtube-html", response_model=ImportResultOut, status_code=201)
async def import_youtube_html(
    file: UploadFile = File(..., description="Google Takeout 유튜브 시청 기록 HTML 파일"),
    filter_start_date: str = Form("", description="이 날짜(YYYY-MM-DD) 이전 기록은 제외. 비우면 전체 사용"),
    avg_long_minutes: float = Form(3, description="롱폼 영상 1개당 평균 시청 시간(분) 가정치"),
    avg_short_minutes: float = Form(1, description="숏폼(쇼츠) 1개당 평균 시청 시간(분) 가정치"),
    avg_music_minutes: float = Form(4, description="유튜브 뮤직 1곡당 평균 재생 시간(분) 가정치"),
):
    """
    Takeout HTML을 업로드하면:
      1) 파싱 + 시간 간격 기반 시청시간 추정
      2) 새 '가져오기 배치'를 만들어 활성 배치로 지정 (기존 배치는 비활성화됨)
      3) 집계된 행들을 batch_id와 함께 Firestore data 컬렉션에 저장
    """
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다. 60MB 이하 파일만 업로드할 수 있습니다.")

    try:
        html_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일 인코딩을 읽을 수 없습니다. UTF-8로 저장된 HTML 파일인지 확인하세요.")

    rows, stats = parse_takeout_html(
        html_text,
        filter_start_date=filter_start_date.strip(),
        avg_long=avg_long_minutes,
        avg_short=avg_short_minutes,
        avg_music=avg_music_minutes,
    )

    if not rows:
        raise HTTPException(
            status_code=422,
            detail="파싱된 시청 기록이 없습니다. 올바른 Takeout HTML 파일인지, 시작일 필터가 너무 최근으로 설정되지 않았는지 확인하세요.",
        )

    settings = {
        "filter_start_date": filter_start_date,
        "avg_long_minutes": avg_long_minutes,
        "avg_short_minutes": avg_short_minutes,
        "avg_music_minutes": avg_music_minutes,
    }
    batch_id = batch_service.create_batch(
        filename=file.filename or "takeout.html",
        count=len(rows),
        period=stats["period"],
        settings=settings,
    )

    db = get_firestore_client()
    collection_ref = db.collection(DATA_COLLECTION)
    fs_batch = db.batch()
    for i, row in enumerate(rows):
        doc_ref = collection_ref.document()
        fs_batch.set(doc_ref, {**row, "batch_id": batch_id})
        if (i + 1) % 400 == 0:
            fs_batch.commit()
            fs_batch = db.batch()
    fs_batch.commit()

    return ImportResultOut(
        batch_id=batch_id,
        filename=file.filename or "takeout.html",
        parsed_count=stats["parsed_count"],
        skipped_non_watch=stats["skipped_non_watch"],
        saved_row_count=len(rows),
        period=stats["period"],
        failed_dates_sample=stats["failed_dates_sample"],
    )
