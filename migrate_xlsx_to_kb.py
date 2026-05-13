"""xlsx 18개 전시 → v5 KB JSON 파일 일괄 마이그레이션.

실행: python migrate_xlsx_to_kb.py

출력: ../exhibition-report-generator-v5/data/exhibitions/*.json
일회성 스크립트. 마이그레이션 후 v5 저장소에 커밋 필요.
"""

import json
import os
import sys
import pandas as pd

from reference_data import load_reference
from schema import (
    SCHEMA_VERSION, STATUS_COMPLETED, SOURCE_MIGRATION,
    make_slug, now_iso, normalize_date, _empty_data,
)


V5_DATA_DIR = os.path.join("..", "exhibition-report-generator-v5", "data", "exhibitions")

# xlsx 컬럼 → session_state 필드 매핑 (정량 위주)
XLSX_TO_FIELD = {
    "총 사용 예산": "total_budget",
    "전시 사용 예산": "budget_exhibition",
    "부대 사용 예산": "budget_supplementary",
    "예산 계획액": "budget_planned",
    "총수입": "total_revenue",
    "입장 수입": "ticket_revenue",
    "총 관객수": "total_visitors",
    "무료/초대 관객수": "visitor_invitation",
    "학생 관객수(만 24세 이하)": "visitor_student",
    "단체 관객수": "visitor_group",
    "디스커버서울패스 관객수": "visitor_discover",
    "예술인패스 관객수": "visitor_artpass",
    "운영 인력_총": "staff_total",
    "스태프 수": "staff_paid",
    "봉사자 수": "staff_volunteer",
    "프로그램 총 수": "program_count",
    "프로그램 총 회차": "program_sessions",
    "프로그램 참여 인원": "program_participants",
    "도슨트 참여 인원": "docent_total",
    "정기 도슨트 참여 인원": "docent_regular",
    "특별 도슨트 참여 인원": "docent_special",
    "오프닝 참석 인원": "opening_attendance",
    "출품 작품 수_총": "artwork_total",
    "출품 작품 수_회화": "artwork_painting",
    "출품 작품 수_조각": "artwork_sculpture",
    "출품 작품 수_사진": "artwork_photo",
    "출품 작품 수_설치": "artwork_installation",
    "출품 작품 수_미디어": "artwork_media",
    "출품 작품 수_기타": "artwork_other",
    "언론 보도 건수": "press_count",
    "웹 초청장 발송 수": "web_invitation_count",
    "뉴스레터 오픈율": "newsletter_open_rate",
    "SNS 게시 건수": "sns_posts",
    "SNS 피드백 합계": "sns_feedback",
    "멤버십 회원수": "membership_count",
}


def _to_num(v):
    """셀 값 → 숫자(또는 0). NaN/None/문자열은 0."""
    if v is None or pd.isna(v):
        return 0
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return float(v) if isinstance(v, float) else int(v)
    try:
        f = float(str(v).replace(",", ""))
        return int(f) if f.is_integer() else f
    except (ValueError, TypeError):
        return 0


def migrate_row(row, idx):
    """xlsx 한 행 → v5 레코드 dict. 실패 시 None."""
    title = row.get("전시 제목")
    if pd.isna(title) or not str(title).strip():
        return None
    title = str(title).strip()

    period_start = normalize_date(row.get("전시 기간_시작"))
    period_end = normalize_date(row.get("전시 기간_종료"))

    type_raw = row.get("전시 유형")
    exhibition_type = None
    if not pd.isna(type_raw):
        try:
            exhibition_type = int(type_raw)
        except (ValueError, TypeError):
            exhibition_type = None

    # 기본 빈 data 시작
    data = _empty_data()
    data["exhibition_title"] = title
    data["period_start"] = period_start
    data["period_end"] = period_end

    # 정량 컬럼 매핑
    for xlsx_col, field in XLSX_TO_FIELD.items():
        if xlsx_col not in row.index:
            continue
        data[field] = _to_num(row.get(xlsx_col))

    # 뉴스레터 오픈율: xlsx는 0~1 소수, session_state는 0~100 percent
    if isinstance(data.get("newsletter_open_rate"), (int, float)):
        v = data["newsletter_open_rate"]
        if 0 < v < 1:
            data["newsletter_open_rate"] = round(v * 100, 1)

    # 슬러그 충돌 방지: 동일 슬러그 발생 시 인덱스 접미
    slug = make_slug(title, period_start)

    ts = now_iso()
    finalized = f"{period_end}T00:00:00" if period_end else None

    return {
        "id": slug,
        "version": SCHEMA_VERSION,
        "status": STATUS_COMPLETED,
        "type": exhibition_type,
        "source": SOURCE_MIGRATION,
        "created_at": ts,
        "modified_at": ts,
        "finalized_at": finalized,
        "data": data,
        "analysis_cache": None,
    }


def main():
    df = load_reference("exhibition_reference_data.xlsx")
    print(f"마이그레이션 시작: {len(df)}개 전시")
    print()

    os.makedirs(V5_DATA_DIR, exist_ok=True)

    used_slugs = set()
    saved = 0
    skipped = 0

    for idx, row in df.iterrows():
        record = migrate_row(row, idx)
        if record is None:
            skipped += 1
            continue

        # 슬러그 충돌 시 -2, -3 ... 접미
        base_slug = record["id"]
        slug = base_slug
        counter = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        record["id"] = slug
        used_slugs.add(slug)

        filename = f"{slug}.json"
        filepath = os.path.join(V5_DATA_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        print(f"  ✓ {filename}")
        saved += 1

    print()
    print(f"완료: {saved}개 저장, {skipped}개 스킵")
    print(f"위치: {V5_DATA_DIR}")


if __name__ == "__main__":
    main()
