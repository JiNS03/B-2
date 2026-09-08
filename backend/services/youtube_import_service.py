"""
Google Takeout 유튜브/유튜브 뮤직 시청 기록 HTML을 파싱해서
data 컬렉션 스키마(date, value, memo, platform, content_type)에 맞는
행(row) 목록으로 변환한다.

기존에 로컬에서 실행하던 parse_youtube_takeout_html_v2.py 스크립트의
로직을 그대로 옮기되, 파일 경로 대신 HTML 문자열을 받고,
평균 시청시간/시작일 필터를 하드코딩 대신 매개변수로 받도록 정리했다.
"""
import re
from datetime import datetime, date as date_cls
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from bs4 import BeautifulSoup

NON_WATCH_MARKERS = ["목록을 확인함", "게시물을 조회함", "댓글을 남김"]
SHORTS_KEYWORDS = ["쇼츠", "shorts", "Shorts", "#Shorts"]
MIN_MINUTES_PER_ENTRY = 0.2


def _try_parse_date(raw_text: str):
    cleaned = raw_text.strip()
    cleaned = re.sub(r"\s*(GMT[+\-]\d{2}:?\d{2}|[A-Z]{2,4})\s*$", "", cleaned).strip()

    m = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(오전|오후)\s*(\d{1,2}):(\d{2}):(\d{2})", cleaned)
    if m:
        year, month, day, ampm, hour, minute, second = m.groups()
        hour = int(hour)
        if ampm == "오후" and hour != 12:
            hour += 12
        if ampm == "오전" and hour == 12:
            hour = 0
        return datetime(int(year), int(month), int(day), hour, int(minute), int(second))

    for fmt in ["%b %d, %Y, %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _is_shortform_by_title(title_text: str) -> bool:
    if not title_text:
        return False
    return any(kw.lower() in title_text.lower() for kw in SHORTS_KEYWORDS)


def _default_avg_minutes(platform: str, content_type: str, avg_long: float, avg_short: float, avg_music: float) -> float:
    if platform == "youtube_music":
        return avg_music
    if content_type == "short_form":
        return avg_short
    return avg_long


def parse_takeout_html(
    html_text: str,
    filter_start_date: str = "",
    avg_long: float = 3,
    avg_short: float = 1,
    avg_music: float = 4,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    반환값: (rows, stats)
    rows: [{date, value, memo, platform, content_type}, ...] — Firestore에 그대로 저장 가능한 형태
    stats: {parsed_count, skipped_non_watch, failed_dates, period}
    """
    soup = BeautifulSoup(html_text, "html.parser")
    entries = soup.find_all("div", class_="outer-cell")

    records = []
    failed_dates = []
    skipped_non_watch = 0

    for entry in entries:
        content_cells = entry.find_all("div", class_="content-cell")
        if not content_cells:
            continue

        # 헤더(맨 위 제목)에 "YouTube Music"이라고 표시되는 경우가 있어
        # 유튜브 뮤직 여부를 여기서 우선 판별한다.
        header_cell = entry.find("div", class_="header-cell")
        header_text = header_cell.get_text() if header_cell else ""
        is_music = "YouTube Music" in header_text or "유튜브 뮤직" in header_text

        main_cell = content_cells[0]
        full_text = main_cell.get_text(separator="\n").strip()

        if any(marker in full_text for marker in NON_WATCH_MARKERS):
            skipped_non_watch += 1
            continue

        link_tag = main_cell.find("a")
        title_text = link_tag.get_text() if link_tag else ""

        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        if not lines:
            continue
        time_line = lines[-1]

        dt = _try_parse_date(time_line)
        if dt is None:
            failed_dates.append(time_line)
            continue

        if filter_start_date and dt.date().isoformat() < filter_start_date:
            continue

        if not is_music and len(content_cells) > 1:
            products_text = content_cells[1].get_text()
            if "YouTube Music" in products_text or "유튜브 뮤직" in products_text:
                is_music = True

        platform = "youtube_music" if is_music else "youtube"
        content_type = "long_form" if is_music else ("short_form" if _is_shortform_by_title(title_text) else "long_form")

        records.append({"datetime": dt, "platform": platform, "content_type": content_type})

    # 같은 날짜 안에서 시각순 정렬 후, 연속된 두 시청 사이 간격을
    # 실제 시청 시간의 상한선으로 사용 (자세한 설명은 기존 스크립트 주석 참고)
    by_date = defaultdict(list)
    for r in records:
        by_date[r["datetime"].date()].append(r)

    computed = []
    for day, day_records in by_date.items():
        day_records.sort(key=lambda r: r["datetime"])
        for i, r in enumerate(day_records):
            avg = _default_avg_minutes(r["platform"], r["content_type"], avg_long, avg_short, avg_music)
            if i + 1 < len(day_records):
                gap_minutes = (day_records[i + 1]["datetime"] - r["datetime"]).total_seconds() / 60
                duration = min(avg, gap_minutes) if gap_minutes > 0 else avg
            else:
                duration = avg
            duration = max(duration, MIN_MINUTES_PER_ENTRY)
            computed.append(
                {"date": day.isoformat(), "platform": r["platform"], "content_type": r["content_type"], "duration": duration}
            )

    sums = defaultdict(float)
    counts = defaultdict(int)
    for c in computed:
        key = (c["date"], c["platform"], c["content_type"])
        sums[key] += c["duration"]
        counts[key] += 1

    rows = []
    for key, total_minutes in sums.items():
        d, platform, content_type = key
        count = counts[key]
        unit_label = "곡 재생" if platform == "youtube_music" else "개 시청"
        rows.append(
            {
                "date": d,
                "value": round(total_minutes),
                "memo": f"{count}{unit_label} (시간 간격 기반 추정)",
                "platform": platform,
                "content_type": content_type,
            }
        )

    rows.sort(key=lambda r: (r["date"], r["platform"]))

    dates = sorted({r["date"] for r in rows})
    period = f"{dates[0]} ~ {dates[-1]}" if dates else "데이터 없음"

    stats = {
        "parsed_count": len(records),
        "skipped_non_watch": skipped_non_watch,
        "failed_dates_sample": failed_dates[:5],
        "period": period,
    }

    return rows, stats
