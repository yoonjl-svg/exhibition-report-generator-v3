"""탭 W: 전시 워크스페이스 — KB 전시 목록 + 신규 생성 + 가져오기.

v5.1 디자인 패스: GPT v4.1의 metric strip + 카드 패턴 차용.
- 상단: 미술관 전체 KPI metric strip
- 액션 바: 신규 만들기 / 가져오기 / 새로고침
- 필터 영역: 유형·정렬·검색
- 목록: 미술관 톤 카드형 (eyebrow + 제목 + chips + 핵심 수치 + 편집)
"""

import json
from datetime import date

import streamlit as st

import kb_store
import kb_session
from ui_helpers import (
    eyebrow, section_header, chip, chip_row,
    metric_strip, status_chip, type_chip,
    STATUS_LABELS, TYPE_LABELS,
)


def render(tab, load_reference_data):
    with tab:
        section_header(
            "EXHIBITION WORKSPACE",
            "전시 워크스페이스",
            "일민미술관의 전시 데이터를 누적·관리하는 공간입니다. "
            "저장된 전시를 선택해 편집하거나 새 전시를 생성하세요.",
        )

        records = _safe_list()
        if records is None:
            return

        # 미술관 전체 KPI metric strip (목록 위에)
        if records:
            _render_metric_strip(records)

        _render_action_bar()
        _render_import_dialog()

        if not records:
            st.info("📭 저장된 전시가 없습니다. 위에서 '신규 전시 만들기'를 클릭하세요.")
            return

        st.divider()
        eyebrow(f"DATA · {len(records)}개 전시 · KB 모드: {kb_store.get_mode()}")

        filtered = _apply_filters(records)
        if not filtered:
            st.info("필터 조건에 해당하는 전시가 없습니다.")
            return

        _render_list(filtered)


# ──────────────────────────────────────────────
# Metric Strip — 미술관 전체 KPI
# ──────────────────────────────────────────────

def _render_metric_strip(records):
    """미술관 누적 데이터에서 핵심 KPI 계산하여 metric strip 렌더."""
    # 분석 제외(type=0) 제외
    analyzable = [r for r in records if r.get("type") != 0]

    total = len(records)
    analyzable_count = len(analyzable)

    # 올해 전시 수
    this_year = date.today().year
    this_year_count = sum(
        1 for r in analyzable
        if (r.get("data", {}).get("period_start") or "").startswith(str(this_year))
    )

    # 평균 관객
    visitor_vals = [r["data"].get("total_visitors") or 0 for r in analyzable]
    visitor_vals = [v for v in visitor_vals if v > 0]
    avg_visitors = int(sum(visitor_vals) / len(visitor_vals)) if visitor_vals else 0

    # 평균 예산 (억 단위)
    budget_vals = [r["data"].get("total_budget") or 0 for r in analyzable]
    budget_vals = [v for v in budget_vals if v > 0]
    avg_budget = int(sum(budget_vals) / len(budget_vals)) if budget_vals else 0

    # 평균 일수
    days_vals = []
    for r in analyzable:
        ps, pe = r["data"].get("period_start"), r["data"].get("period_end")
        if ps and pe:
            try:
                s = date.fromisoformat(ps)
                e = date.fromisoformat(pe)
                days_vals.append((e - s).days + 1)
            except (ValueError, TypeError):
                pass
    avg_days = int(sum(days_vals) / len(days_vals)) if days_vals else 0

    # 평균 보도건수
    press_vals = [r["data"].get("press_count") or 0 for r in analyzable]
    press_vals = [v for v in press_vals if v > 0]
    avg_press = int(sum(press_vals) / len(press_vals)) if press_vals else 0

    metrics = [
        {
            "label": "누적 전시",
            "value": f"{total}건",
            "context": f"분석 대상 {analyzable_count}건",
        },
        {
            "label": f"{this_year}년 진행",
            "value": f"{this_year_count}건",
            "context": "올해 시작 전시" if this_year_count else "없음",
        },
        {
            "label": "평균 관객",
            "value": f"{avg_visitors:,}명" if avg_visitors else "—",
            "context": f"표본 {len(visitor_vals)}건",
        },
        {
            "label": "평균 예산",
            "value": f"{avg_budget / 100_000_000:.2f}억" if avg_budget else "—",
            "context": f"표본 {len(budget_vals)}건",
        },
        {
            "label": "평균 운영일수",
            "value": f"{avg_days}일" if avg_days else "—",
            "context": f"표본 {len(days_vals)}건",
        },
        {
            "label": "평균 보도건수",
            "value": f"{avg_press}건" if avg_press else "—",
            "context": f"표본 {len(press_vals)}건",
        },
    ]
    metric_strip(metrics)


# ──────────────────────────────────────────────
# 액션 바 + 가져오기
# ──────────────────────────────────────────────

def _render_action_bar():
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button("➕ 신규 전시 만들기", type="primary", use_container_width=True,
                     key="ws_new_exhibition"):
            kb_session.enter_detail_mode(record=None)
            st.rerun()
    with col2:
        if st.button("📥 JSON 파일 가져오기", use_container_width=True,
                     key="ws_open_import",
                     help="이전에 저장한 v3 또는 v5 JSON 파일에서 데이터를 복원합니다."):
            st.session_state["ws_show_import"] = not st.session_state.get("ws_show_import", False)
    with col3:
        if st.button("🔄 새로고침", use_container_width=True, key="ws_refresh",
                     help="KB 캐시를 비우고 다시 로드합니다."):
            kb_store._cache_clear()
            st.rerun()


def _render_import_dialog():
    if not st.session_state.get("ws_show_import"):
        return
    with st.expander("📥 JSON 가져오기", expanded=True):
        uploaded = st.file_uploader(
            "JSON 파일 선택", type=["json"], key="ws_json_upload",
            help="v3 형식(평면 data) 또는 v5 형식({data: {...}}) 모두 인식",
        )
        if uploaded is None:
            return
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("📂 불러와서 편집 시작", type="primary", use_container_width=True,
                         key="ws_do_import"):
                try:
                    raw = json.loads(uploaded.read())
                    record = _normalize_imported(raw)
                    kb_session.enter_detail_mode(record=record)
                    st.session_state["current_exhibition_id"] = None  # 신규로 처리
                    st.session_state["ws_show_import"] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"가져오기 실패: {e}")
        with col2:
            if st.button("취소", use_container_width=True, key="ws_cancel_import"):
                st.session_state["ws_show_import"] = False
                st.rerun()


def _normalize_imported(raw: dict) -> dict:
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        return raw
    return {"id": None, "data": raw, "status": "draft", "type": None, "source": "form"}


def _safe_list():
    try:
        return kb_store.list_exhibitions()
    except Exception as e:
        st.error(f"전시 목록 로드 실패: {e}")
        st.caption("KB 모드 확인 필요. 로컬 개발은 ../exhibition-report-generator-v5 클론 위치를 확인하세요.")
        return None


# ──────────────────────────────────────────────
# 필터·정렬
# ──────────────────────────────────────────────

def _apply_filters(records):
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        type_options = ["전체"] + [TYPE_LABELS[k] for k in (1, 2, 3, 0)]
        type_choice = st.selectbox("유형 필터", type_options, key="ws_type_filter")
    with col2:
        sort_options = ["최신순", "오래된순", "제목순", "관객 많은 순"]
        sort_by = st.selectbox("정렬", sort_options, key="ws_sort")
    with col3:
        search = st.text_input("검색", key="ws_search", placeholder="제목 또는 작가...")

    # 유형 매핑
    type_to_num = {v: k for k, v in TYPE_LABELS.items()}
    if type_choice in type_to_num:
        target = type_to_num[type_choice]
        records = [r for r in records if r.get("type") == target]

    if search and search.strip():
        s = search.strip().lower()
        records = [
            r for r in records
            if s in (r.get("data", {}).get("exhibition_title") or "").lower()
            or s in (r.get("data", {}).get("artists") or "").lower()
        ]

    if sort_by == "최신순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("period_start") or "", reverse=True)
    elif sort_by == "오래된순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("period_start") or "")
    elif sort_by == "제목순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("exhibition_title", ""))
    elif sort_by == "관객 많은 순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("total_visitors") or 0, reverse=True)

    return records


# ──────────────────────────────────────────────
# 카드 목록
# ──────────────────────────────────────────────

def _render_list(records):
    for rec in records:
        _render_card(rec)


def _render_card(rec):
    """미술관 톤 전시 카드. eyebrow + 제목 + chips + 핵심 수치 + 편집 버튼."""
    data = rec.get("data", {})
    title = data.get("exhibition_title") or "(제목없음)"
    ps = data.get("period_start") or "—"
    pe = data.get("period_end") or "—"

    # eyebrow: 연도 · 상태 라벨
    year = (ps or "")[:4] or "—"
    status = rec.get("status", "draft")
    status_label = STATUS_LABELS.get(status, status)

    # 핵심 수치
    tv = data.get("total_visitors") or 0
    tb = data.get("total_budget") or 0
    pc = data.get("press_count") or 0
    pp = data.get("program_participants") or 0

    visitor_str = f"{tv:,}명" if tv else "—"
    if tb >= 100_000_000:
        budget_str = f"{tb / 100_000_000:.2f}억"
    elif tb >= 10_000_000:
        budget_str = f"{tb / 10_000:,.0f}만"
    elif tb > 0:
        budget_str = f"{tb:,}원"
    else:
        budget_str = "—"
    press_str = f"{pc}건" if pc else "—"
    program_str = f"{pp:,}명" if pp else "—"

    artists = data.get("artists") or ""
    artists_short = artists[:60] + "…" if len(artists) > 60 else artists

    chips_html = status_chip(status) + " " + type_chip(rec.get("type"))

    metrics_html = (
        f'<div class="exhibition-card-metrics">'
        f'<span class="metric-item">👥 <strong>{visitor_str}</strong></span>'
        f'<span class="metric-item">💰 <strong>{budget_str}</strong></span>'
        f'<span class="metric-item">📰 <strong>{press_str}</strong></span>'
        f'<span class="metric-item">🎯 <strong>{program_str}</strong></span>'
        f'</div>'
    )

    with st.container(border=True):
        col_main, col_action = st.columns([6, 1])
        with col_main:
            st.markdown(
                f'<div class="eyebrow">{year} · {status_label}</div>'
                f'<div class="exhibition-card-title">《{title}》</div>'
                f'<div class="exhibition-card-meta">{ps} ~ {pe}'
                + (f' · {artists_short}' if artists_short else '')
                + f'</div>'
                f'<div style="margin: 6px 0;">{chips_html}</div>'
                f'{metrics_html}',
                unsafe_allow_html=True,
            )
        with col_action:
            st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
            if st.button("편집 →", key=f"ws_edit_{rec['id']}", use_container_width=True):
                kb_session.enter_detail_mode(record=rec)
                st.rerun()
