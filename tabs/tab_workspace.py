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
import excel_template
from ui_helpers import (
    eyebrow, section_header, chip, chip_row,
    metric_strip, status_chip, type_chip,
    STATUS_LABELS, TYPE_LABELS,
)


# ──────────────────────────────────────────────
# 모달 다이얼로그 — 가져오기 (Excel + JSON 통합)
# ──────────────────────────────────────────────

@st.dialog("가져오기")
def _show_import_modal():
    """진짜 모달 오버레이로 띄우는 가져오기 다이얼로그.

    Excel 템플릿과 JSON 파일을 탭으로 분리.
    X 버튼 또는 외부 클릭으로 닫힘 (Streamlit이 자동 처리).
    """
    tabs = st.tabs(["Excel 템플릿", "JSON 파일"])
    with tabs[0]:
        _render_excel_section(excel_template)
    with tabs[1]:
        _render_json_section()


def render(tab, load_reference_data):
    with tab:
        # 상단 eyebrow + H1 제거. 부제만 남김 (사용자 요청)
        st.markdown(
            '<p class="main-subtitle">'
            '일민미술관의 전시 데이터를 누적·관리하는 공간입니다. '
            '저장된 전시를 선택해 편집하거나 새 전시를 생성하세요.'
            '</p>',
            unsafe_allow_html=True,
        )

        records = _safe_list()
        if records is None:
            return

        # 미술관 전체 KPI metric strip (목록 위에)
        if records:
            _render_metric_strip(records)

        _render_action_bar()

        if not records:
            st.info("📭 저장된 전시가 없습니다. 위에서 '신규 전시 만들기'를 클릭하세요.")
            return

        # ── 트렌드·비교 (확장 가능) ──
        with st.expander("누적 흐름 & 다중 전시 비교", expanded=False):
            from tabs import tab_trend
            tab_trend.render(records)

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

    # 평균 수입
    revenue_vals = [r["data"].get("total_revenue") or 0 for r in analyzable]
    revenue_vals = [v for v in revenue_vals if v > 0]
    avg_revenue = int(sum(revenue_vals) / len(revenue_vals)) if revenue_vals else 0

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

    def _fmt_money_compact(v):
        if not v:
            return "—"
        if v >= 100_000_000:
            return f"{v / 100_000_000:.2f}억"
        if v >= 10_000_000:
            return f"{v / 10_000:,.0f}만"
        return f"{v:,}원"

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
            "value": _fmt_money_compact(avg_budget),
            "context": f"표본 {len(budget_vals)}건",
        },
        {
            "label": "평균 수입",
            "value": _fmt_money_compact(avg_revenue),
            "context": f"표본 {len(revenue_vals)}건",
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
    # 3개 버튼 (이모지 제거, Excel·JSON 통합)
    # [1.5, 1, 1, 7.5] = 신규 13.6% / 가져오기 9.1% / 새로고침 9.1% / 빈 68.2%
    col1, col2, col3, _col4 = st.columns([1.5, 1, 1, 7.5])
    with col1:
        if st.button("새 전시 데이터 생성", type="primary", use_container_width=True,
                     key="ws_new_exhibition"):
            kb_session.enter_detail_mode(record=None)
            st.rerun()
    with col2:
        if st.button("가져오기", use_container_width=True,
                     key="ws_open_import",
                     help="Excel 템플릿 또는 JSON 파일로 데이터를 가져옵니다."):
            _show_import_modal()
    with col3:
        if st.button("새로고침", use_container_width=True, key="ws_refresh",
                     help="KB 캐시를 비우고 다시 로드합니다."):
            kb_store._cache_clear()
            st.rerun()


def _render_excel_section(excel_template):
    """Excel 템플릿 다운로드 + 업로드 (통합 다이얼로그의 1탭)."""
    st.markdown(
        "큐레이터가 외부에서 데이터를 정리한 뒤 한 번에 업로드할 수 있는 표준 템플릿입니다. "
        "폼 입력의 대체가 아니라 **보조 경로**이며, 업로드 후에도 검수·수정이 가능합니다."
    )

    col_dl, col_ul = st.columns([1, 2])
    with col_dl:
        try:
            tpl_bytes = excel_template.generate_template_xlsx()
            st.download_button(
                "템플릿 다운로드",
                data=tpl_bytes,
                file_name="ilmin_exhibition_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ws_dl_template",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"템플릿 생성 실패: {e}")

    with col_ul:
        uploaded = st.file_uploader(
            "작성 완료된 템플릿 업로드", type=["xlsx", "xls"], key="ws_xlsx_upload",
        )

    if uploaded:
        # 모달 X 버튼으로 닫을 수 있으므로 취소 버튼 제거
        if st.button("가져와서 편집 시작", type="primary",
                     use_container_width=True, key="ws_do_xlsx_import"):
            try:
                result = excel_template.parse_template_xlsx(uploaded)
                record = {
                    "id": None,
                    "data": result["data"],
                    "status": "draft",
                    "type": result["type"],
                    "source": "excel",
                }
                kb_session.enter_detail_mode(record=record)
                st.session_state["current_exhibition_id"] = None
                if result["type"] is not None:
                    st.session_state["current_exhibition_type"] = result["type"]
                if result["warnings"]:
                    st.session_state["_excel_import_warnings"] = result["warnings"]
                st.rerun()
            except Exception as e:
                st.error(f"가져오기 실패: {e}")
                import traceback
                st.code(traceback.format_exc())


def _render_json_section():
    """JSON 업로드 (통합 다이얼로그의 2탭)."""
    st.markdown(
        "이전에 저장한 v3 또는 v5 JSON 파일에서 데이터를 복원합니다. "
        "두 형식 모두 자동 인식되며, 업로드 후 검수·수정이 가능합니다."
    )
    uploaded = st.file_uploader(
        "JSON 파일 선택", type=["json"], key="ws_json_upload",
        help="v3 형식(평면 data) 또는 v5 형식({data: {...}}) 모두 인식",
    )
    if uploaded is None:
        return
    if st.button("불러와서 편집 시작", type="primary", use_container_width=True,
                 key="ws_do_import"):
        try:
            raw = json.loads(uploaded.read())
            record = _normalize_imported(raw)
            kb_session.enter_detail_mode(record=record)
            st.session_state["current_exhibition_id"] = None
            st.rerun()
        except Exception as e:
            st.error(f"가져오기 실패: {e}")


def _normalize_imported(raw: dict) -> dict:
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        return raw
    return {"id": None, "data": raw, "status": "draft", "type": None, "source": "form"}


def _safe_list():
    try:
        return kb_store.list_exhibitions()
    except Exception as e:
        msg = str(e)
        st.error(f"전시 목록 로드 실패\n\n{msg}")
        # 모드별 추가 안내
        try:
            mode = kb_store.get_mode()
        except Exception:
            mode = "unknown"
        if mode == "github":
            st.caption(
                "GitHub 모드입니다. 위 메시지가 401(인증 실패)이면 "
                "Streamlit Cloud의 Settings → Secrets에서 `KB_GITHUB_PAT`를 "
                "새 토큰으로 교체해야 합니다."
            )
        else:
            st.caption(
                "로컬 모드입니다. ../exhibition-report-generator-v5 클론 위치를 확인하세요."
            )
        return None


# ──────────────────────────────────────────────
# 필터·정렬
# ──────────────────────────────────────────────

def _apply_filters(records):
    # 컬럼 [1, 1, 4]: 필터·정렬 16.7%, 검색 66.7% (빈 칸 제거, 검색이 남은 폭 채움)
    col1, col2, col3 = st.columns([1, 1, 4])
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
    """전시 목록 — 연도별 그룹화 + 3열 그리드 (최신 연도부터)."""
    # 연도별 그룹화
    by_year = {}
    no_year = []
    for rec in records:
        ps = (rec.get("data", {}).get("period_start") or "")
        year = ps[:4] if len(ps) >= 4 else None
        if year:
            by_year.setdefault(year, []).append(rec)
        else:
            no_year.append(rec)

    # 연도 내림차순 (최신부터)
    for year in sorted(by_year.keys(), reverse=True):
        _render_year_header(year, len(by_year[year]))
        _render_year_grid(by_year[year])

    # 연도 미상
    if no_year:
        _render_year_header("미상", len(no_year))
        _render_year_grid(no_year)


def _render_year_header(year_str: str, count: int):
    """연도 헤더 — eyebrow + 큰 연도 + 카운트."""
    label = f"{year_str}년" if year_str != "미상" else year_str
    st.markdown(
        f'<div class="year-header">'
        f'<div class="eyebrow">YEAR · {year_str}</div>'
        f'<div>'
        f'<span class="year-label">{label}</span>'
        f'<span class="year-count">· {count}건</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_year_grid(records):
    """해당 연도의 전시들을 4열 그리드로 배치. 마지막 행이 4개 미만이면 빈 컬럼은 그대로."""
    for i in range(0, len(records), 4):
        chunk = records[i:i + 4]
        cols = st.columns(4, gap="medium")
        for col, rec in zip(cols, chunk):
            with col:
                _render_card(rec)


def _fmt_money(v) -> str:
    """예산·수입 한국식 포맷."""
    if not v:
        return "—"
    v = int(v)
    if v >= 100_000_000:
        return f"{v / 100_000_000:.2f}억"
    if v >= 10_000_000:
        return f"{v / 10_000:,.0f}만"
    return f"{v:,}원"


def _render_card(rec):
    """미술관 톤 전시 카드 (3열 그리드 좁은 너비용).

    구성:
      - eyebrow: 연도 · 상태
      - 제목 (《》)
      - 기간 (YYYY-MM-DD ~ YYYY-MM-DD)
      - 상태·유형 chips
      - 4개 핵심 지표 (총 관객 / 일평균 관객 / 총 예산 / 총 수입)
      - 편집 버튼
    """
    from datetime import date as _date

    data = rec.get("data", {})
    title = data.get("exhibition_title") or "(제목없음)"
    ps = data.get("period_start") or "—"
    pe = data.get("period_end") or "—"
    status = rec.get("status", "draft")
    status_label = STATUS_LABELS.get(status, status)
    year = (ps or "")[:4] or "—"

    # 핵심 수치 (총 수입은 4열 그리드에서 제외 — 카드 폭 줄어듦에 맞춤)
    tv = data.get("total_visitors") or 0
    tb = data.get("total_budget") or 0

    # 일평균 관객 (파생)
    daily = None
    if tv and ps and pe and ps != "—" and pe != "—":
        try:
            s = _date.fromisoformat(ps)
            e = _date.fromisoformat(pe)
            days = (e - s).days + 1
            if days > 0:
                daily = int(tv / days)
        except (ValueError, TypeError):
            pass

    # 포맷
    visitor_str = f"{tv:,}명" if tv else "—"
    daily_str = f"{daily:,}명" if daily else "—"
    budget_str = _fmt_money(tb)

    chips_html = status_chip(status) + " " + type_chip(rec.get("type"))

    metrics_html = (
        '<div class="exhibition-card-metrics">'
        f'<span class="metric-item">👥 <strong>{visitor_str}</strong></span>'
        f'<span class="metric-item">📊 <strong>{daily_str}</strong></span>'
        f'<span class="metric-item">💰 <strong>{budget_str}</strong></span>'
        '</div>'
    )

    with st.container(border=True):
        st.markdown(
            f'<div class="eyebrow">{year} · {status_label}</div>'
            f'<div class="exhibition-card-title">《{title}》</div>'
            f'<div class="exhibition-card-meta">{ps} ~ {pe}</div>'
            f'<div style="margin: 6px 0;">{chips_html}</div>'
            f'{metrics_html}',
            unsafe_allow_html=True,
        )
        if st.button("편집 →", key=f"ws_edit_{rec['id']}", use_container_width=True):
            kb_session.enter_detail_mode(record=rec)
            st.rerun()
