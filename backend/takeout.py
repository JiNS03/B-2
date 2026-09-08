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

AVG_MINUTES_YOUTUBE_LONGFORM = 8
AVG_MINUTES_YOUTUBE_SHORTFORM = 1
AVG_MINUTES_MUSIC = 4

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

        # Products("제품") 항목으로 유튜브 뮤직 여부 판별
        is_music = False
        if len(content_cells) > 1:
            products_text = content_cells[1].get_text()
            if "YouTube Music" in products_text or "유튜브 뮤직" in products_text:
                is_music = True

        platform = "youtube_music" if is_music else "youtube"
        content_type = "long_form" if is_music else ("short_form" if is_shortform_by_title(title_text) else "long_form")

        records.append({"date": dt.date().isoformat(), "platform": platform, "content_type": content_type})

    return records, failed_dates, skipped_non_watch


def aggregate(records):
    counts = defaultdict(int)
    for r in records:
        key = (r["date"], r["platform"], r["content_type"])
        counts[key] += 1

    rows = []
    for (date_str, platform, content_type), count in counts.items():
        if platform == "youtube_music":
            avg = AVG_MINUTES_MUSIC
            unit_label = "곡 재생"
        elif content_type == "short_form":
            avg = AVG_MINUTES_YOUTUBE_SHORTFORM
            unit_label = "개 시청"
        else:
            avg = AVG_MINUTES_YOUTUBE_LONGFORM
            unit_label = "개 시청"

        rows.append(
            {
                "date": date_str,
                "value": count * avg,
                "memo": f"{count}{unit_label} (평균 {avg}분 가정)",
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

    rows = aggregate(records)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value", "memo", "platform", "content_type"])
        writer.writeheader()
        writer.writerows(rows)

    shortform_count = sum(1 for r in records if r["content_type"] == "short_form")
    print(f"총 {len(rows)}개 행을 {OUTPUT_FILE} 에 저장했습니다.")
    print(f"(날짜 수: {len(set(r['date'] for r in rows))}일, 쇼츠로 판별된 기록: {shortform_count}건)")


if __name__ == "__main__":
    main()