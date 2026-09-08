"""
샘플 시청 기록 CSV 생성 스크립트

실제 Google Takeout / Kaggle 등에서 받은 CSV가 있다면 이 스크립트는 건너뛰고,
해당 CSV를 date, value, memo, platform, content_type 컬럼 형태로
직접 가공(pandas)한 뒤 seed_data.py로 업로드하면 됩니다.

이 스크립트는 그런 원본 CSV가 없을 때 데모/테스트용으로
현실적인 패턴(주말 증가, 숏폼 비중 점진적 증가)을 섞은
더미 데이터를 생성합니다.

실행: python generate_sample_csv.py
결과: sample_data.csv (기본 150일치)
"""
import csv
import random
from datetime import date, timedelta

OUTPUT_FILE = "sample_data.csv"
DAYS = 150
START_DATE = date(2026, 4, 1)

PLATFORMS_LONG = ["netflix", "youtube", "disney_plus", "watcha"]
PLATFORMS_SHORT = ["youtube_shorts", "instagram_reels", "tiktok"]


def generate_row(i: int, d: date):
    is_weekend = d.weekday() >= 5

    # 기본 시청 시간: 주말이 평일보다 김
    base_minutes = 190 if is_weekend else 95

    # 최근으로 갈수록 전체 시청 시간이 완만하게 증가하는 추세
    trend_boost = int(i * 0.4)

    total_minutes = max(0, int(random.gauss(base_minutes + trend_boost, 35)))

    # 가끔 시청 안 한 날 (휴식일)
    if random.random() < 0.06:
        total_minutes = 0

    # 최근으로 갈수록 숏폼(쇼츠/릴스) 비중이 점점 늘어나는 추세
    shortform_ratio = min(0.75, 0.15 + i * 0.0035)
    short_minutes = int(total_minutes * shortform_ratio)
    long_minutes = total_minutes - short_minutes

    if total_minutes == 0:
        content_type = "long_form"
        platform = "none"
        memo = "시청 기록 없음 (휴식일)"
    elif short_minutes >= long_minutes:
        content_type = "short_form"
        platform = random.choice(PLATFORMS_SHORT)
        memo = f"롱폼 {long_minutes}분 / 숏폼 {short_minutes}분"
    else:
        content_type = "long_form"
        platform = random.choice(PLATFORMS_LONG)
        memo = f"롱폼 {long_minutes}분 / 숏폼 {short_minutes}분"

    return {
        "date": d.isoformat(),
        "value": total_minutes,
        "memo": memo,
        "platform": platform,
        "content_type": content_type,
    }


def main():
    rows = []
    for i in range(DAYS):
        d = START_DATE + timedelta(days=i)
        rows.append(generate_row(i, d))

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value", "memo", "platform", "content_type"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)}개 샘플 데이터를 {OUTPUT_FILE} 에 생성했습니다.")


if __name__ == "__main__":
    main()
