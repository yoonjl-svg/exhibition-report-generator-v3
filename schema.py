"""
일민미술관 전시 워크스페이스 v5 — 데이터 스키마

각 전시는 data/exhibitions/{slug}.json 파일 하나로 표현됨.

JSON 구조:
{
    "id": "2025-하이퍼-옐로우",   # 파일명과 동일
    "version": "1.0.0",           # 스키마 버전
    "status": "completed",        # draft | in_progress | completed | archived
    "type": 1,                    # 0(분석제외) | 1(정기기획전) | 2(특별전) | 3(기타)
    "source": "migration",        # migration | form | excel | duplicate
    "created_at": "2026-05-13T12:00:00",
    "modified_at": "2026-05-13T12:00:00",
    "finalized_at": null,         # null이면 진행 중

    "data": {
        # 현재 session_state 평면 구조 그대로
        # (역사적 마이그레이션 레코드는 narrative 필드가 비어 있음)
        "exhibition_title": str,
        "period_start": "YYYY-MM-DD",
        "period_end": "YYYY-MM-DD",
        # ... 정량/서술 모든 필드
    },

    "analysis_cache": null | {     # 첫 분석 실행 시 채워짐
        "generated_at": "ISO",
        "model": "claude-opus-4-8",
        "llm_sections": dict,
        "summary_metrics": list
    }
}
"""

import re
from datetime import date, datetime
from typing import Optional


SCHEMA_VERSION = "1.0.0"

# 상태값
STATUS_DRAFT = "draft"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_ARCHIVED = "archived"
VALID_STATUSES = {STATUS_DRAFT, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_ARCHIVED}

# 입력 출처
SOURCE_MIGRATION = "migration"
SOURCE_FORM = "form"
SOURCE_EXCEL = "excel"
SOURCE_DUPLICATE = "duplicate"

# 전시 유형
TYPE_EXCLUDED = 0
TYPE_REGULAR = 1   # 정기 기획전
TYPE_SPECIAL = 2   # 특별전
TYPE_OTHER = 3     # 기타


def make_slug(title: str, period_start=None) -> str:
    """전시 제목 → 파일명 slug.

    형식: {year}-{slugified-title}
    예: "하이퍼 옐로우" + "2025-06-13" → "2025-하이퍼-옐로우"
    """
    # 연도 prefix
    year = ""
    if period_start:
        if isinstance(period_start, str):
            # "2025-06-13" 또는 "2025.06.13" 형식 처리
            year = period_start[:4]
        elif isinstance(period_start, (date, datetime)):
            year = str(period_start.year)

    # 제목 slugify
    slug = (title or "").strip()
    # 한국·영문 따옴표·괄호·구두점 제거
    slug = re.sub(r"[《》「」『』\"'\(\)\[\]【】〈〉<>,.:;!?]", "", slug)
    # 공백 → 하이픈
    slug = re.sub(r"\s+", "-", slug)
    # 연속 하이픈 압축
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")

    if not slug:
        slug = "untitled"

    if year:
        return f"{year}-{slug}"
    return slug


def now_iso() -> str:
    """현재 시간 ISO 8601 문자열."""
    return datetime.now().isoformat(timespec="seconds")


def normalize_date(v) -> Optional[str]:
    """다양한 날짜 표현 → 'YYYY-MM-DD' 또는 None.

    허용:
      - "2025-06-13"
      - "2025.06.13"
      - "2025/06/13"
      - datetime, date 객체
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    # 점/슬래시 구분자를 하이픈으로
    s = re.sub(r"[./]", "-", s)
    # YYYY-MM-DD 형태 검증
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return None


def new_record(
    title: str,
    period_start=None,
    exhibition_type: Optional[int] = None,
    source: str = SOURCE_FORM,
    data: Optional[dict] = None,
) -> dict:
    """빈 또는 부분 채워진 전시 레코드 생성."""
    ts = now_iso()
    record_data = dict(_empty_data())
    if data:
        record_data.update(data)
    record_data["exhibition_title"] = title
    if period_start:
        record_data["period_start"] = normalize_date(period_start)

    return {
        "id": make_slug(title, period_start),
        "version": SCHEMA_VERSION,
        "status": STATUS_DRAFT,
        "type": exhibition_type,
        "source": source,
        "created_at": ts,
        "modified_at": ts,
        "finalized_at": None,
        "data": record_data,
        "analysis_cache": None,
    }


def _empty_data() -> dict:
    """레코드 data 블록의 기본값 (narrative + quantitative 모두 빈 상태)."""
    return {
        # 기본 정보 (B)
        "exhibition_title": "",
        "period_start": None,
        "period_end": None,
        "artists": "",
        "chief_curator": "",
        "curators": "",
        "coordinators": "",
        "curatorial_team": "",
        "pr_person": "",
        "sponsors": "",

        # 주제·구성·프로그램·인쇄물·보도·후기
        "theme_text": "",
        "rooms": [],
        "related_programs": [],
        "printed_materials": [],
        "press_print": [],
        "press_online": [],
        "visitor_reviews": [],
        "membership_text": "",

        # 홍보 서술
        "promo_advertising": "",
        "promo_press_release": "",
        "promo_web_invitation": "",
        "promo_newsletter": "",
        "promo_sns": "",
        "promo_other": "",

        # 정량: 예산
        "total_budget": 0,
        "budget_exhibition": 0,
        "budget_supplementary": 0,
        "budget_planned": 0,
        "total_revenue": 0,
        "ticket_revenue": 0,
        "other_revenue": 0,

        # 정량: 관객
        "total_visitors": 0,
        "visitor_general": 0,
        "visitor_student": 0,
        "visitor_invitation": 0,
        "visitor_artpass": 0,
        "visitor_discover": 0,
        "visitor_discount": 0,
        "visitor_group": 0,
        "opening_attendance": 0,
        "weekly_visitors": {},

        # 정량: 작품
        "artwork_total": 0,
        "artwork_painting": 0,
        "artwork_sculpture": 0,
        "artwork_photo": 0,
        "artwork_installation": 0,
        "artwork_media": 0,
        "artwork_other": 0,

        # 정량: 프로그램·도슨트
        "program_count": 0,
        "program_sessions": 0,
        "program_participants": 0,
        "docent_total": 0,
        "docent_regular": 0,
        "docent_special": 0,

        # 정량: 인력
        "staff_total": 0,
        "staff_paid": 0,
        "staff_volunteer": 0,

        # 정량: 홍보
        "press_count": 0,
        "sns_posts": 0,
        "sns_feedback": 0,
        "web_invitation_count": 0,
        "newsletter_open_rate": 0.0,
        "membership_count": 0,
    }


def validate(record: dict) -> list[str]:
    """레코드 무결성 검사. 문제점 리스트 반환 (빈 리스트면 OK)."""
    issues = []
    required_top = ["id", "version", "status", "source", "created_at", "modified_at", "data"]
    for k in required_top:
        if k not in record:
            issues.append(f"필수 키 누락: {k}")
    if record.get("status") not in VALID_STATUSES:
        issues.append(f"잘못된 status: {record.get('status')}")
    if not isinstance(record.get("data"), dict):
        issues.append("data가 dict가 아님")
    return issues
