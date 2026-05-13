"""탭 W: 전시 워크스페이스 — KB 전시 목록 + 신규 생성 + 가져오기."""

import json
import streamlit as st

import kb_store
import kb_session


def render(tab, load_reference_data):
    with tab:
        st.markdown('<div class="section-header">📚 전시 워크스페이스</div>', unsafe_allow_html=True)
        st.caption(
            "일민미술관의 전시 데이터 저장소(KB)입니다. 저장된 전시를 선택해 편집하거나 "
            "새 전시를 생성하세요. 작업한 내용은 워크스페이스에 영구 보관됩니다."
        )

        _render_action_bar()
        _render_import_dialog()

        st.divider()

        records = _safe_list()
        if records is None:
            return

        if not records:
            st.info("📭 저장된 전시가 없습니다. '➕ 신규 전시 만들기' 버튼을 클릭하세요.")
            return

        st.caption(f"📊 총 {len(records)}개 전시 — KB 모드: `{kb_store.get_mode()}`")

        filtered = _apply_filters(records)
        if not filtered:
            st.info("필터 조건에 해당하는 전시가 없습니다.")
            return

        _render_list(filtered)


# ──────────────────────────────────────────────
# UI 헬퍼
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
                    # 신규로 처리하기 위해 id 제거 (저장 시 새 슬러그 생성)
                    st.session_state["current_exhibition_id"] = None
                    st.session_state["ws_show_import"] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"가져오기 실패: {e}")
        with col2:
            if st.button("취소", use_container_width=True, key="ws_cancel_import"):
                st.session_state["ws_show_import"] = False
                st.rerun()


def _normalize_imported(raw: dict) -> dict:
    """v3(평면) 또는 v5(래핑) JSON → 일관된 record 형식."""
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        # v5 형식
        return raw
    # v3 평면 형식: 전체를 data로 감싸기
    return {
        "id": None,
        "data": raw,
        "status": "draft",
        "type": None,
        "source": "form",
    }


def _safe_list():
    """전시 목록 로드. 오류 시 None 반환 (UI 표시 후 종료)."""
    try:
        return kb_store.list_exhibitions()
    except Exception as e:
        st.error(f"전시 목록 로드 실패: {e}")
        st.caption("KB 모드 확인 필요. 로컬 개발은 ../exhibition-report-generator-v5 클론 위치를 확인하세요.")
        return None


def _apply_filters(records):
    """유형 필터 + 정렬."""
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        type_options = ["전체", "정기 기획전", "특별전", "기타", "분석 제외"]
        type_choice = st.selectbox("유형 필터", type_options, key="ws_type_filter")
    with col2:
        sort_options = ["최신순", "오래된순", "제목순", "관객 많은 순"]
        sort_by = st.selectbox("정렬", sort_options, key="ws_sort")
    with col3:
        search = st.text_input("검색", key="ws_search", placeholder="제목/작가...")

    # 유형 매핑
    type_map = {"정기 기획전": 1, "특별전": 2, "기타": 3, "분석 제외": 0}
    if type_choice in type_map:
        records = [r for r in records if r.get("type") == type_map[type_choice]]

    # 검색
    if search and search.strip():
        s = search.strip().lower()
        records = [
            r for r in records
            if s in (r.get("data", {}).get("exhibition_title") or "").lower()
            or s in (r.get("data", {}).get("artists") or "").lower()
        ]

    # 정렬
    if sort_by == "최신순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("period_start") or "", reverse=True)
    elif sort_by == "오래된순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("period_start") or "")
    elif sort_by == "제목순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("exhibition_title", ""))
    elif sort_by == "관객 많은 순":
        records = sorted(records, key=lambda r: r.get("data", {}).get("total_visitors") or 0, reverse=True)

    return records


def _render_list(records):
    """전시 카드 리스트 렌더."""
    type_label_map = {1: "정기 기획전", 2: "특별전", 3: "기타", 0: "분석 제외"}
    status_emoji = {
        "draft": "✏️",
        "in_progress": "🔄",
        "completed": "✅",
        "archived": "📦",
    }

    for rec in records:
        data = rec.get("data", {})
        with st.container():
            col_info, col_metric, col_action = st.columns([5, 2, 1])

            with col_info:
                title = data.get("exhibition_title") or "(제목없음)"
                ps = data.get("period_start") or "—"
                pe = data.get("period_end") or "—"
                type_label = type_label_map.get(rec.get("type"), "미분류")
                status = rec.get("status", "draft")
                emoji = status_emoji.get(status, "•")
                st.markdown(f"**《{title}》**")
                st.caption(
                    f"{emoji} `{status}` · {type_label} · 기간 {ps} ~ {pe}"
                )

            with col_metric:
                tv = data.get("total_visitors") or 0
                tb = data.get("total_budget") or 0
                visitor_str = f"👥 {tv:,}명" if tv else "👥 —"
                if tb >= 100_000_000:
                    budget_str = f"💰 {tb / 100_000_000:.2f}억"
                elif tb >= 10_000_000:
                    budget_str = f"💰 {tb / 10_000:,.0f}만"
                elif tb > 0:
                    budget_str = f"💰 {tb:,}원"
                else:
                    budget_str = "💰 —"
                st.markdown(f"{visitor_str}<br>{budget_str}", unsafe_allow_html=True)

            with col_action:
                if st.button("편집", key=f"ws_edit_{rec['id']}", use_container_width=True):
                    kb_session.enter_detail_mode(record=rec)
                    st.rerun()

            st.divider()
