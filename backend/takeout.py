"""
Google Takeout HTML 형식 유튜브/유튜브 뮤직 시청 기록을 CSV로 변환하는 스크립트
(실제 한국어 Takeout 내보내기 구조에 맞춰 작성됨)

------------------------------------------------------------------
사전 준비
------------------------------------------------------------------
pip install beautifulsoup4

------------------------------------------------------------------
사용법
------------------------------------------------------------------
1) Takeout에서 받은 "시청 기록" 폴더 안의 html 파일을
   이 스크립트와 같은 폴더에 복사하고, 아래 INPUT_FILE 값을
   실제 파일명으로 맞춰주세요.
2) 실행: python parse_youtube_takeout_html.py
3) 결과: my_watch_history.csv

------------------------------------------------------------------
주의 / 가정
------------------------------------------------------------------
- 실제 Takeout 데이터에서는 쇼츠 영상도 URL이 일반 /watch?v=... 형태로
  기록되는 경우가 대부분이라, URL만으로는 쇼츠 여부를 구분할 수 없습니다.
  대신 영상 제목에 "쇼츠", "#shorts", "shorts" 가 포함되어 있는지로
  판별합니다. 제목 텍스트는 이 판별에만 사용하고 최종 CSV에는
  저장하지 않습니다 (memo에는 개수만 들어갑니다).
- "OO을(를) 시청했습니다"가 아니라 "목록을 확인함"(커뮤니티 게시물 확인),
  "게시물을 조회함" 등은 실제 영상 시청이 아니므로 건수 집계에서 제외합니다.
- "Products/제품" 항목에 "YouTube Music"이 포함되어 있으면 유튜브 뮤직,
  아니면 일반 유튜브로 분류합니다.
"""
import re
import csv
from datetime import datetime
from collections import defaultdict
from bs4 import BeautifulSoup

INPUT_FILE = "시청 기록.html"
OUTPUT_FILE = "my_watch_history.csv"

# 이 날짜 이전 기록은 제외합니다 (계정 초창기의 듬성듬성한 데이터,
# 즉 "가끔 한 번씩 보던 시기"를 빼고 최근 연속된 습관 구간만 사용하기 위함).
# 본인 CSV를 열어보고 데이터가 촘촘해지기 시작하는 날짜로 맞추세요.
FILTER_START_DATE = "2026-06-16"

# 영상 1개당 평균 시청 시간(분) 가정치.
# 주의: 하루에 수십~수백 개를 "시청함"으로 기록하는 경우, 대부분 짧게
# 훑어보거나 자동재생으로 스킵한 영상입니다. 8분처럼 큰 값을 쓰면
# "하루 500개 * 8분 = 66시간 시청"처럼 물리적으로 불가능한 값이 나옵니다.
# 본인의 실제 시청 패턴에 맞게 낮춰서 조정하세요 (예: 2~3분).
AVG_MINUTES_YOUTUBE_LONGFORM = 3
AVG_MINUTES_YOUTUBE_SHORTFORM = 1
AVG_MINUTES_MUSIC = 4

# 연속된 두 시청 사이의 간격이 이 값보다 짧게 잘리지 않도록 하는 최소값(분).
# 너무 0에 가깝게 잘리면 "봤다"는 사실 자체가 무의미해지는 걸 막기 위함입니다.
MIN_MINUTES_PER_ENTRY = 0.2

# 실제 시청 이벤트로 인정하지 않는 활동 문구 (제목이 없는 라인에서 확인)
NON_WATCH_MARKERS = ["목록을 확인함", "게시물을 조회함", "댓글을 남김"]

SHORTS_KEYWORDS = ["쇼츠", "shorts", "Shorts", "#Shorts"]


def try_parse_date(raw_text: str):
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


def is_shortform_by_title(title_text: str) -> bool:
    if not title_text:
        return False
    return any(kw.lower() in title_text.lower() for kw in SHORTS_KEYWORDS)


def parse_html(path: str):
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    entries = soup.find_all("div", class_="outer-cell")
    records = []
    failed_dates = []
    skipped_non_watch = 0

    for entry in entries:
        content_cells = entry.find_all("div", class_="content-cell")
        if not content_cells:
            continue

        # 헤더(맨 위 제목)에 "YouTube Music"이라고 표시되는 경우가 있어
        # 유튜브 뮤직 여부를 여기서 우선 판별합니다.
        # (반면 "제품:" 항목은 두 경우 모두 그냥 "YouTube"로만 표기되어
        #  구분이 안 될 수 있음)
        header_cell = entry.find("div", class_="header-cell")
        header_text = header_cell.get_text() if header_cell else ""
        is_music = "YouTube Music" in header_text or "유튜브 뮤직" in header_text

        main_cell = content_cells[0]
        full_text = main_cell.get_text(separator="\n").strip()

        # 실제 시청이 아닌 활동(게시물 확인 등)은 건너뜀
        if any(marker in full_text for marker in NON_WATCH_MARKERS):
            skipped_non_watch += 1
            continue

        link_tag = main_cell.find("a")
        title_text = link_tag.get_text() if link_tag else ""

        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        if not lines:
            continue
        time_line = lines[-1]

        dt = try_parse_date(time_line)
        if dt is None:
            failed_dates.append(time_line)
            continue

        # 지정한 시작일 이전 기록은 제외 (듬성듬성한 초창기 데이터 제거)
        if FILTER_START_DATE and dt.date().isoformat() < FILTER_START_DATE:
            continue

        # 헤더에서 못 찾았다면 "제품:" 항목도 보조로 확인 (혹시 모를 다른 형식 대비)
        if not is_music and len(content_cells) > 1:
            products_text = content_cells[1].get_text()
            if "YouTube Music" in products_text or "유튜브 뮤직" in products_text:
                is_music = True

        platform = "youtube_music" if is_music else "youtube"
        content_type = "long_form" if is_music else ("short_form" if is_shortform_by_title(title_text) else "long_form")

        # 날짜만이 아니라 시각(시:분:초)까지 전체 datetime을 그대로 보관합니다.
        # (다음 단계에서 "연속된 두 시청 사이의 실제 간격"을 계산하는 데 필요)
        records.append({"datetime": dt, "platform": platform, "content_type": content_type})

    return records, failed_dates, skipped_non_watch


def default_avg_minutes(platform: str, content_type: str) -> float:
    if platform == "youtube_music":
        return AVG_MINUTES_MUSIC
    if content_type == "short_form":
        return AVG_MINUTES_YOUTUBE_SHORTFORM
    return AVG_MINUTES_YOUTUBE_LONGFORM


def compute_durations(records):
    """
    같은 날짜 안에서 시각순으로 정렬한 뒤,
    '이 영상을 본 시각'과 '바로 다음 영상을 본 시각' 사이의 간격을
    실제 시청 시간의 상한선으로 사용합니다.

    예) 평균 가정치가 3분이어도 다음 영상까지 20초밖에 안 걸렸다면
        실제로는 20초 이상 볼 수 없었을 것이므로 20초로 계산합니다.
    하루의 마지막 기록은 비교할 다음 시각이 없으므로 평균 가정치를 그대로 씁니다.
    """
    by_date = defaultdict(list)
    for r in records:
        by_date[r["datetime"].date()].append(r)

    computed = []
    for day, day_records in by_date.items():
        day_records.sort(key=lambda r: r["datetime"])
        for i, r in enumerate(day_records):
            avg = default_avg_minutes(r["platform"], r["content_type"])

            if i + 1 < len(day_records):
                gap_minutes = (day_records[i + 1]["datetime"] - r["datetime"]).total_seconds() / 60
                duration = min(avg, gap_minutes) if gap_minutes > 0 else avg
            else:
                duration = avg

            # 너무 짧게(0에 가깝게) 잘리는 것을 막기 위한 최소값
            duration = max(duration, MIN_MINUTES_PER_ENTRY)

            computed.append(
                {
                    "date": day.isoformat(),
                    "platform": r["platform"],
                    "content_type": r["content_type"],
                    "duration": duration,
                }
            )

    return computed


def aggregate(computed):
    """
    (날짜, 플랫폼, 콘텐츠형태) 기준으로 실제 계산된 duration(분)을 합산합니다.
    """
    sums = defaultdict(float)
    counts = defaultdict(int)
    for c in computed:
        key = (c["date"], c["platform"], c["content_type"])
        sums[key] += c["duration"]
        counts[key] += 1

    rows = []
    for key, total_minutes in sums.items():
        date_str, platform, content_type = key
        count = counts[key]
        unit_label = "곡 재생" if platform == "youtube_music" else "개 시청"
        rows.append(
            {
                "date": date_str,
                "value": round(total_minutes),
                "memo": f"{count}{unit_label} (시간 간격 기반 추정)",
                "platform": platform,
                "content_type": content_type,
            }
        )

    rows.sort(key=lambda r: (r["date"], r["platform"]))
    return rows


def main():
    records, failed_dates, skipped = parse_html(INPUT_FILE)
    print(f"{len(records)}개 시청 기록 파싱 완료 (게시물 확인 등 {skipped}건 제외)")

    if failed_dates:
        print(f"\n[주의] 날짜를 인식하지 못한 {len(failed_dates)}건이 있습니다. 예시 5개:")
        for s in failed_dates[:5]:
            print(f"  - {s}")

    if not records:
        print("파싱된 기록이 없습니다. INPUT_FILE 경로/파일명을 확인하세요.")
        return

    computed = compute_durations(records)
    rows = aggregate(computed)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value", "memo", "platform", "content_type"])
        writer.writeheader()
        writer.writerows(rows)

    shortform_count = sum(1 for r in records if r["content_type"] == "short_form")
    max_daily = max((r["value"] for r in rows), default=0)
    print(f"총 {len(rows)}개 행을 {OUTPUT_FILE} 에 저장했습니다.")
    print(f"(날짜 수: {len(set(r['date'] for r in rows))}일, 쇼츠로 판별된 기록: {shortform_count}건)")
    print(f"단일 (날짜,플랫폼,형태) 조합 최대값: {max_daily}분 (하루 최대 1440분을 넘으면 여러 조합의 합산이라 그럴 수 있습니다)")


if __name__ == "__main__":
    main()