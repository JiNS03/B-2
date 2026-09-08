"""
Google Takeout으로 받은 유튜브(+유튜브 뮤직) 시청 기록 JSON을
프로젝트의 data 스키마(date, value, memo, platform, content_type)에 맞는
CSV로 변환하는 스크립트.

------------------------------------------------------------------
사용법
------------------------------------------------------------------
1) Takeout 압축을 풀면 보통 아래 경로에 JSON이 있습니다.
     Takeout/YouTube 및 YouTube Music/기록/시청 기록.json

2) 이 스크립트와 같은 폴더에 그 파일을 복사해오거나,
   아래 INPUT_FILES 리스트에 실제 경로를 적어주세요.

3) 실행:
     python parse_youtube_takeout.py

4) 결과: my_watch_history.csv (프로젝트 seed_data.py가 바로 읽을 수 있는 형식)

------------------------------------------------------------------
플랫폼 분리 (유튜브 vs 유튜브 뮤직)
------------------------------------------------------------------
Takeout JSON의 각 기록에는 "header" 필드가 있어 어떤 서비스에서
발생한 기록인지 구분할 수 있습니다.
  - header == "YouTube"        -> 일반 유튜브 시청 (platform: youtube)
  - header == "YouTube Music"  -> 유튜브 뮤직 재생 (platform: youtube_music)
이 스크립트는 이 값을 그대로 platform 컬럼에 반영해서,
나중에 프론트/백엔드에서 유튜브와 유튜브 뮤직을 따로 필터링해
확인할 수 있게 합니다.

------------------------------------------------------------------
주의 / 가정
------------------------------------------------------------------
- Takeout JSON에는 "실제 시청 시간(분)"이 들어있지 않습니다.
  기록 1건당(영상 1개 또는 음악 1곡) 아래 AVG_MINUTES_* 상수로
  평균 시간을 가정해 분으로 환산합니다. 실제 습관과 다르다고
  느끼면 이 숫자를 조정하세요.
- 쇼츠(short_form)는 titleUrl에 "/shorts/"가 포함된 경우로 판별합니다.
  유튜브 뮤직 기록은 전부 long_form으로 처리합니다(쇼츠 개념이 없음).
- 영상 제목/곡 제목(title) 정보는 읽지도, 저장하지도 않습니다.
  memo 컬럼에는 "몇 개 시청/재생했는지" 개수만 들어갑니다.
- 하루에 발생한 기록들을 (날짜, 플랫폼, 콘텐츠 형태) 기준으로 합쳐서
  집계합니다. (기록 하나하나를 다 넣으면 Firestore 문서 수가
  너무 많아지기 때문)
"""
import json
import csv
from datetime import datetime
from collections import defaultdict

# ------------------ 설정값 (필요하면 수정) ------------------
INPUT_FILES = [
    "시청 기록.json",   # Takeout에서 복사해온 파일명 (유튜브+유튜브뮤직 기록이 함께 들어있음)
]
OUTPUT_FILE = "my_watch_history.csv"

AVG_MINUTES_YOUTUBE_LONGFORM = 8   # 유튜브 롱폼 1개당 평균 시청 시간(분) 가정치
AVG_MINUTES_YOUTUBE_SHORTFORM = 1  # 유튜브 쇼츠 1개당 평균 시청 시간(분) 가정치
AVG_MINUTES_MUSIC = 4              # 유튜브 뮤직 1곡당 평균 재생 시간(분) 가정치


def resolve_platform(header: str) -> str:
    """Takeout의 header 필드를 프로젝트 platform 값으로 매핑"""
    if header == "YouTube Music":
        return "youtube_music"
    return "youtube"  # header가 "YouTube"이거나 없는 경우 기본값


def is_shortform(title_url: str) -> bool:
    if not title_url:
        return False
    return "/shorts/" in title_url


def parse_takeout_json(path: str):
    """
    Takeout JSON 구조 예시:
    [
      {
        "header": "YouTube",
        "title": "Watched 영상 제목",
        "titleUrl": "https://www.youtube.com/watch?v=xxxx",
        "time": "2026-08-15T13:24:01.123Z",
        ...
      },
      ...
    ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for entry in data:
        time_str = entry.get("time")
        if not time_str:
            continue
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        date_str = dt.date().isoformat()
        title_url = entry.get("titleUrl", "")
        platform = resolve_platform(entry.get("header", ""))

        if platform == "youtube_music":
            content_type = "long_form"  # 뮤직은 쇼츠 개념 없음
        else:
            content_type = "short_form" if is_shortform(title_url) else "long_form"

        records.append({"date": date_str, "platform": platform, "content_type": content_type})

    return records


def aggregate(records):
    """
    (날짜, 플랫폼, 콘텐츠형태) 기준으로 기록 개수를 세고,
    평균 시청/재생 시간을 곱해 분 단위 value로 환산합니다.
    """
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

        value = count * avg
        rows.append(
            {
                "date": date_str,
                "value": value,
                "memo": f"{count}{unit_label} (평균 {avg}분 가정)",
                "platform": platform,
                "content_type": content_type,
            }
        )

    rows.sort(key=lambda r: (r["date"], r["platform"]))
    return rows


def main():
    all_records = []
    for path in INPUT_FILES:
        try:
            recs = parse_takeout_json(path)
            print(f"{path}: {len(recs)}개 기록 파싱 완료")
            all_records.extend(recs)
        except FileNotFoundError:
            print(f"[경고] {path} 파일을 찾을 수 없어 건너뜁니다.")

    if not all_records:
        print("파싱된 기록이 없습니다. INPUT_FILES 경로를 확인하세요.")
        return

    rows = aggregate(all_records)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value", "memo", "platform", "content_type"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"총 {len(rows)}개 행을 {OUTPUT_FILE} 에 저장했습니다. (날짜 수: {len(set(r['date'] for r in rows))}일)")


if __name__ == "__main__":
    main()
