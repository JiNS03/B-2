"""
시청 기록 데이터를 기반으로 요약 정보(기간/통계/트렌드)를 계산한다.
data 라우터(GET /api/data/summary)와 chat 라우터(컨텍스트 주입)가
동일한 로직을 공유하도록 별도 서비스로 분리했다.
"""
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

from services.firebase_service import get_firestore_client, DATA_COLLECTION
from services.batch_service import get_active_batch_id


def _to_dict(doc) -> Dict[str, Any]:
    d = doc.to_dict()
    d["id"] = doc.id
    return d


def fetch_all_records() -> List[Dict[str, Any]]:
    """
    Firestore에서 시청 기록을 가져온다.
    단, '가져오기 배치'로 업로드된 데이터는 현재 활성 배치의 것만 포함하고,
    수동으로 추가한 데이터(batch_id 없음)는 항상 포함한다.
    """
    db = get_firestore_client()
    active_batch_id = get_active_batch_id()

    docs = db.collection(DATA_COLLECTION).stream()
    records = []
    for doc in docs:
        d = _to_dict(doc)
        batch_id = d.get("batch_id")
        if batch_id and batch_id != active_batch_id:
            continue  # 비활성 배치의 데이터는 제외
        records.append(d)

    records.sort(key=lambda r: r.get("date", ""))
    return records


def _calc_trend(values: List[int], window: int = 14) -> str:
    """최근 window일 평균 vs 이전 window일 평균을 비교해 추세 문구를 만든다."""
    if len(values) < window * 2:
        # 데이터가 충분하지 않으면 전체 절반씩 비교
        half = max(1, len(values) // 2)
        recent = values[-half:]
        previous = values[:half] if len(values) > half else values
    else:
        recent = values[-window:]
        previous = values[-window * 2 : -window]

    if not previous or sum(previous) == 0:
        return "데이터가 더 쌓이면 추세를 계산할 수 있어요"

    recent_avg = sum(recent) / len(recent)
    previous_avg = sum(previous) / len(previous)
    change_pct = (recent_avg - previous_avg) / previous_avg * 100

    if change_pct > 5:
        return f"상승 (최근 구간 평균 대비 {change_pct:+.0f}%)"
    elif change_pct < -5:
        return f"하락 (최근 구간 평균 대비 {change_pct:+.0f}%)"
    else:
        return f"유지 (최근 구간 평균 대비 {change_pct:+.0f}%)"


def build_summary() -> Dict[str, Any]:
    """
    GET /api/data/summary 응답 및 /api/chat 시스템 프롬프트 주입에
    공통으로 사용되는 요약 정보를 계산한다.
    """
    records = fetch_all_records()

    if not records:
        return {
            "period": "데이터 없음",
            "count": 0,
            "metrics": {
                "total_minutes": 0,
                "average_minutes_per_day": 0,
                "max_minutes": 0,
                "min_minutes": 0,
                "shortform_ratio": 0,
                "longform_ratio": 0,
                "weekend_avg": 0,
                "weekday_avg": 0,
            },
            "platform_breakdown": {},
            "trend": "데이터가 없어 추세를 계산할 수 없습니다",
        }

    values = [r.get("value", 0) for r in records]
    dates = [r.get("date", "") for r in records]

    total = sum(values)
    count = len(values)
    average = total / count
    max_v = max(values)
    min_v = min(values)

    short_minutes = 0
    long_minutes = 0
    weekend_values = []
    weekday_values = []

    # 플랫폼별(유튜브 / 유튜브 뮤직 / 기타) 집계용
    platform_minutes: Dict[str, int] = defaultdict(int)
    platform_counts: Dict[str, int] = defaultdict(int)

    for r in records:
        v = r.get("value", 0)
        if r.get("content_type") == "short_form":
            short_minutes += v
        else:
            long_minutes += v

        platform = r.get("platform", "unknown")
        platform_minutes[platform] += v
        platform_counts[platform] += 1

        try:
            d = datetime.strptime(r.get("date", ""), "%Y-%m-%d")
            if d.weekday() >= 5:  # 토(5)/일(6)
                weekend_values.append(v)
            else:
                weekday_values.append(v)
        except ValueError:
            continue

    total_typed = short_minutes + long_minutes
    shortform_ratio = round(short_minutes / total_typed, 2) if total_typed else 0
    longform_ratio = round(1 - shortform_ratio, 2) if total_typed else 0

    weekend_avg = round(sum(weekend_values) / len(weekend_values), 1) if weekend_values else 0
    weekday_avg = round(sum(weekday_values) / len(weekday_values), 1) if weekday_values else 0

    # 플랫폼별 breakdown: {"youtube": {"total_minutes": .., "count": .., "ratio": ..}, ...}
    platform_breakdown = {}
    for platform, minutes in platform_minutes.items():
        platform_breakdown[platform] = {
            "total_minutes": minutes,
            "count": platform_counts[platform],
            "ratio": round(minutes / total, 2) if total else 0,
        }

    return {
        "period": f"{dates[0]} ~ {dates[-1]}",
        "count": count,
        "metrics": {
            "total_minutes": total,
            "average_minutes_per_day": round(average, 1),
            "max_minutes": max_v,
            "min_minutes": min_v,
            "shortform_ratio": shortform_ratio,
            "longform_ratio": longform_ratio,
            "weekend_avg": weekend_avg,
            "weekday_avg": weekday_avg,
        },
        "platform_breakdown": platform_breakdown,
        "trend": _calc_trend(values),
    }
