"""
KB 레코드 ↔ Streamlit session_state 변환 헬퍼.

핵심 함수:
  - load_record_to_session(record): KB 레코드 → 세션 (편집 모드 진입)
  - new_exhibition_session(): 빈 폼으로 신규 전시 모드 진입
  - get_current_session_data(): 세션 → KB 레코드 data 블록
  - save_current_to_kb(commit_message): 현재 세션을 KB에 저장 (업데이트/신규)
"""

from typing import Optional
import streamlit as st

import kb_store
from schema import new_record, SOURCE_FORM


# session_state에서 KB data 블록으로 옮길 키 목록
DATA_KEYS = [
    # 기본 정보 (B)
    "exhibition_title", "period_start", "period_end", "artists",
    "chief_curator", "curators", "coordinators", "curatorial_team",
    "pr_person", "sponsors",

    # 주제·구성·프로그램·인쇄물·보도·후기
    "theme_text", "rooms", "related_programs", "printed_materials",
    "press_print", "press_online", "visitor_reviews", "membership_text",

    # 홍보 서술
    "promo_advertising", "promo_press_release", "promo_web_invitation",
    "promo_newsletter", "promo_sns", "promo_other",

    # 정량: 예산
    "total_budget", "budget_exhibition", "budget_supplementary",
    "budget_planned", "total_revenue", "ticket_revenue", "other_revenue",

    # 정량: 관객
    "total_visitors", "visitor_general", "visitor_student",
    "visitor_invitation", "visitor_artpass", "visitor_discover",
    "visitor_discount", "visitor_group", "opening_attendance",
    "weekly_visitors",

    # 정량: 작품
    "artwork_total", "artwork_painting", "artwork_sculpture",
    "artwork_photo", "artwork_installation", "artwork_media",
    "artwork_other",

    # 정량: 프로그램·도슨트
    "program_count", "program_sessions", "program_participants",
    "docent_total", "docent_regular", "docent_special",

    # 정량: 인력
    "staff_total", "staff_paid", "staff_volunteer",

    # 정량: 홍보
    "press_count", "sns_posts", "sns_feedback",
    "web_invitation_count", "newsletter_open_rate", "membership_count",
]


def load_record_to_session(record: dict) -> None:
    """KB 레코드를 session_state에 로드. 편집 모드 진입을 의미.

    위젯이 이미 렌더링된 상태이므로 직접 대입 불가 → _pending_json 메커니즘 사용.
    app.py init_session이 다음 rerun에서 적용함.

    레코드에 없는 키는 pop하여 default 재초기화 (이전 작업 데이터 잔존 방지).
    """
    data = record.get("data", {})
    # 레코드에 없는 키는 pop (default로 재초기화될 수 있도록)
    for key in DATA_KEYS:
        if key not in data:
            st.session_state.pop(key, None)
    st.session_state["_pending_json"] = dict(data)

    # 메타 정보 별도 키
    st.session_state["current_exhibition_id"] = record.get("id")
    st.session_state["current_exhibition_status"] = record.get("status", "draft")
    st.session_state["current_exhibition_type"] = record.get("type")
    st.session_state["current_exhibition_meta"] = {
        "version": record.get("version"),
        "source": record.get("source"),
        "created_at": record.get("created_at"),
        "modified_at": record.get("modified_at"),
        "finalized_at": record.get("finalized_at"),
    }

    # 이전 작업의 분석/보고서 미리보기 무효화
    st.session_state.pop("analysis_result", None)
    st.session_state.pop("report_state", None)
    for _sec in ("composition", "results", "promotion", "evaluation", "audience_response"):
        st.session_state.pop(f"preview_edit_{_sec}", None)


def new_exhibition_session() -> None:
    """빈 신규 전시 작업 모드 진입. 이전 데이터를 모두 클리어.

    DATA_KEYS를 모두 pop → 다음 rerun의 init_session이 default로 재초기화.
    _pending_json={}로 메커니즘 트리거 (빈 오버라이드).
    """
    # 모든 입력 필드 강제 제거 → init_session이 다음 frame에서 default 재주입
    for key in DATA_KEYS:
        st.session_state.pop(key, None)
    # 기타 위젯 관련 키도 클리어 (분석/미리보기)
    st.session_state.pop("analysis_result", None)
    st.session_state.pop("insight_selections", None)
    st.session_state.pop("insight_texts", None)
    st.session_state.pop("eval_positive_drafts", None)
    st.session_state.pop("eval_negative_drafts", None)
    st.session_state.pop("eval_improvement_drafts", None)
    st.session_state.pop("report_state", None)
    for _sec in ("composition", "results", "promotion", "evaluation", "audience_response"):
        st.session_state.pop(f"preview_edit_{_sec}", None)

    # _pending_json 트리거 (빈 오버라이드, 메커니즘 활성화용)
    st.session_state["_pending_json"] = {}

    st.session_state["current_exhibition_id"] = None
    st.session_state["current_exhibition_status"] = "draft"
    st.session_state["current_exhibition_type"] = None
    st.session_state["current_exhibition_meta"] = {}


def get_current_session_data() -> dict:
    """현재 session_state에서 KB data 블록 dict 빌드.

    date 객체는 ISO 문자열로 직렬화.
    """
    s = st.session_state
    data = {}
    for key in DATA_KEYS:
        v = s.get(key)
        # date / datetime → ISO 문자열
        if hasattr(v, "isoformat") and not isinstance(v, str):
            try:
                v = v.isoformat()
            except (TypeError, ValueError):
                pass
        # 리스트 내 date 정리
        if isinstance(v, list):
            v = [_normalize_listitem(item) for item in v]
        data[key] = v
    return data


def _normalize_listitem(item):
    """리스트 항목 내 date → ISO 문자열 정규화."""
    if not isinstance(item, dict):
        return item
    out = {}
    for k, v in item.items():
        if hasattr(v, "isoformat") and not isinstance(v, str):
            try:
                v = v.isoformat()
            except (TypeError, ValueError):
                pass
        out[k] = v
    return out


def save_current_to_kb(commit_message: Optional[str] = None) -> dict:
    """현재 세션을 KB에 저장.

    current_exhibition_id가 있으면 업데이트, 없으면 신규 생성.
    Returns 저장된 레코드.
    """
    s = st.session_state
    data = get_current_session_data()
    current_id = s.get("current_exhibition_id")

    if current_id:
        existing = kb_store.get_exhibition(current_id, use_cache=False)
        if existing is None:
            # 메모리에는 있는데 KB에 없으면 신규로 저장
            record = _build_new_record(data, s)
        else:
            existing["data"] = data
            existing["type"] = s.get("current_exhibition_type")
            existing["status"] = s.get("current_exhibition_status", existing.get("status", "draft"))
            record = existing
    else:
        record = _build_new_record(data, s)

    saved = kb_store.save_exhibition(record, commit_message)

    # 신규였다면 id를 세션에 반영 (다음 저장은 업데이트)
    if not current_id:
        s["current_exhibition_id"] = saved["id"]
        s["current_exhibition_status"] = saved["status"]
        s["current_exhibition_type"] = saved["type"]
        s["current_exhibition_meta"] = {
            "version": saved.get("version"),
            "source": saved.get("source"),
            "created_at": saved.get("created_at"),
            "modified_at": saved.get("modified_at"),
            "finalized_at": saved.get("finalized_at"),
        }

    return saved


def _build_new_record(data: dict, s) -> dict:
    """신규 레코드 생성 (KB에 처음 저장)."""
    title = (data.get("exhibition_title") or "").strip() or "(제목없음)"
    period_start = data.get("period_start")
    exhibition_type = s.get("current_exhibition_type")

    record = new_record(
        title=title,
        period_start=period_start,
        exhibition_type=exhibition_type,
        source=SOURCE_FORM,
    )
    record["data"] = data
    record["status"] = s.get("current_exhibition_status", record["status"])
    return record


# ──────────────────────────────────────────────
# 모드 (workspace / detail) 전환 헬퍼
# ──────────────────────────────────────────────

def enter_detail_mode(record: Optional[dict] = None) -> None:
    """편집 모드 진입. record가 있으면 그 레코드 로드, 없으면 빈 신규."""
    if record:
        load_record_to_session(record)
    else:
        new_exhibition_session()
    st.session_state["app_mode"] = "detail"


def enter_workspace_mode() -> None:
    """워크스페이스 목록 모드로 복귀."""
    st.session_state["app_mode"] = "workspace"
