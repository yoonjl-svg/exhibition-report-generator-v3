"""탭 D: 보고서 미리보기 & 생성"""

import os
import tempfile
import streamlit as st
import pandas as pd
from datetime import date

from utils import fmt_money, fmt_number, collect_analysis_data
import analysis_engine as ae
import reference_data as rd
from llm_writer import rewrite_insights, validate_api_key, estimate_cost, HAS_ANTHROPIC
from ui_helpers import section_header, subsection


def render(tab, load_reference_data):
    with tab:
        section_header(
            "REPORT",
            "보고서 생성",
            "분석 결과를 신문 기사 톤의 종합 보고서로 변환하고, 웹에서 검수 후 Word로 다운로드합니다.",
        )

        # 가로 폭 원칙(CLAUDE.md): 상단 영역(완성도·구조·키입력)을 ~60% 안에
        body_col = st.container(key="ws_gen_body")
        with body_col:
            # ── 데이터 완성도 체크 ──
            _show_completeness_check()

            st.divider()

            # ── 보고서 구조 미리보기 ──
            subsection("", "보고서 구조 미리보기")
            st.caption("분석 인사이트가 각 섹션에 배치된 모습을 미리 확인합니다.")

            _show_preview()

            st.divider()

            # ── AI 글쓰기 설정 ──
            subsection("", "AI 분석 글쓰기")

            if not HAS_ANTHROPIC:
                st.warning("`anthropic` 패키지가 설치되지 않았습니다. `pip install anthropic`으로 설치하면 AI 글쓰기를 사용할 수 있습니다.")

            api_key = st.text_input(
                "Anthropic API 키",
                type="password",
                key="anthropic_api_key",
                help="Claude API 키를 입력하면 보고서 생성 시 분석 문단을 보고서 문체로 자동 재작성합니다. 없으면 룰 기반 텍스트가 그대로 사용됩니다.",
                placeholder="sk-ant-api03-..."
            )

        if api_key:
            is_valid, msg = validate_api_key(api_key)
            if is_valid:
                st.caption(f"{msg} — Opus 모델로 분석 문단을 재작성합니다.")
            else:
                st.caption(f"{msg}")

        use_llm = bool(api_key and api_key.strip().startswith("sk-ant-"))

        st.divider()

        # ── 생성 ──
        subsection("GENERATE", "보고서 생성")

        if use_llm:
            st.info("AI 글쓰기 활성화 — 보고서 생성 시 Claude Opus가 분석 문단을 보고서 문체로 재작성합니다.")

        col1, _ = st.columns([1.5, 8.5])
        with col1:
            if st.button("보고서 생성", type="primary", use_container_width=True,
                         help="LLM이 분석 문단을 작성하고, 아래에 미리보기·편집 영역이 나타납니다."):
                _generate_report(api_key=api_key if use_llm else None,
                                 load_ref=load_reference_data)

        # ── 미리보기 & 편집 & 다운로드 ──
        _render_preview_and_edit()
        # 데이터 저장/불러오기는 워크스페이스(KB 저장)와 '가져오기' 모달로
        # 일원화됨 — v5.3.59에서 보고서 탭의 JSON 저장·불러오기 제거.


def _show_completeness_check():
    """데이터 완성도 표시"""
    s = st.session_state
    checks = {
        "전시 제목": bool(s.exhibition_title),
        "전시 기간": bool(s.period_start and s.period_end),
        "참여 작가": bool(s.artists),
        "전시 에세이": bool(s.theme_text),
        "총 사용 예산": bool(s.total_budget),
        "총 관객수": bool(s.total_visitors),
        "출품 작품 수": bool(s.artwork_total),
        "프로그램 정보": bool(s.program_count),
        "분석 실행": bool(s.get("analysis_result")),
    }

    completed = sum(checks.values())
    total = len(checks)
    progress = completed / total

    st.progress(progress, text=f"데이터 완성도: {completed}/{total} ({progress*100:.0f}%)")

    if completed < total:
        missing = [k for k, v in checks.items() if not v]
        st.caption(f"미입력: {', '.join(missing)}")


def _show_preview():
    """보고서 구조의 텍스트 미리보기"""
    s = st.session_state

    # 제목
    title = s.exhibition_title or "(전시 제목)"
    st.markdown(f"### 전시보고서 - 《{title}》")
    st.markdown("---")

    # I. 전시 개요
    with st.expander("**I. 전시 개요**", expanded=False):
        period = ""
        if s.period_start and s.period_end:
            days = (s.period_end - s.period_start).days + 1
            period = f"{s.period_start.strftime('%Y.%m.%d')} - {s.period_end.strftime('%Y.%m.%d')} ({days}일)"
        st.markdown(f"- 전시 제목: 《{title}》")
        st.markdown(f"- 전시 기간: {period}")
        st.markdown(f"- 참여 작가: {s.artists}")
        if s.total_budget:
            st.markdown(f"- 총 사용 예산: **{fmt_money(s.total_budget)}**")
        if s.total_visitors:
            st.markdown(f"- 관객 수: **{fmt_number(s.total_visitors, '명')}**")

    # II. 전시 주제와 내용
    with st.expander("**II. 전시 주제와 내용**", expanded=False):
        if s.theme_text:
            st.markdown(s.theme_text[:300] + ("..." if len(s.theme_text) > 300 else ""))
        else:
            st.caption("(전시 에세이 미입력)")

    # III. 전시 구성 + 인라인 분석
    with st.expander("**III. 전시 구성**", expanded=False):
        st.markdown(f"- 전시실: {len(s.rooms)}개")
        if s.program_count:
            st.markdown(f"- 프로그램: {s.program_count}개, {s.program_participants}명 참여")
        if s.artwork_total:
            st.markdown(f"- 출품 작품: {s.artwork_total}점")
        _show_section_insights("composition")

    # IV. 전시 결과 + 인라인 분석
    with st.expander("**IV. 전시 결과**", expanded=True):
        if s.total_budget:
            st.markdown(f"- 총 사용 예산: {fmt_money(s.total_budget)}")
        if s.total_revenue:
            st.markdown(f"- 총수입: {fmt_money(s.total_revenue)}")
        if s.total_visitors:
            st.markdown(f"- 총 관객수: {fmt_number(s.total_visitors, '명')}")
        _show_section_insights("results")

    # V. 홍보 + 인라인 분석
    with st.expander("**V. 홍보 방식 및 언론 보도**", expanded=False):
        if s.press_count:
            st.markdown(f"- 언론 보도: {s.press_count}건")
        if s.sns_posts:
            st.markdown(f"- SNS 게시: {s.sns_posts}건")
        _show_section_insights("promotion")

    # VI. Executive Summary (교차 분석 + 자동 도출 평가 항목)
    with st.expander("**VI. Executive Summary**", expanded=True):
        _show_section_insights("evaluation")
        st.caption("보고서 생성 시 LLM이 위 인사이트를 종합하여 신문 기사 톤의 종합 의견을 자동 작성합니다.")


def _show_section_insights(section):
    """특정 보고서 섹션에 배치될 인사이트 미리보기"""
    result = st.session_state.get("analysis_result")
    if not result:
        return

    by_section = ae.get_insights_by_section(result)
    section_insights = by_section.get(section, [])

    selected = []
    for i, ins in enumerate(section_insights):
        key = f"ins_{section}_{i}"
        if st.session_state.get("insight_selections", {}).get(key, ins.priority <= 2):
            text = st.session_state.get("insight_texts", {}).get(key, ins.text)
            selected.append((ins, text))

    if selected:
        st.markdown("---")
        st.caption("데이터 기반 분석:")
        for ins, text in selected:
            st.markdown(f"> {text}")


def _generate_report(api_key=None, load_ref=None):
    """보고서 데이터 준비 (LLM 글쓰기 + 종합표 계산) → session_state 저장.

    Word 생성은 미리보기·편집 UI(_render_preview_and_edit)에서 즉시 수행.
    load_ref: 레퍼런스 DataFrame 로더(render에서 전달). 종합표·차트용.
    """
    try:
        data = _collect_report_data(load_ref)
        s = st.session_state

        # ── 핵심 수치 종합표 먼저 계산 ──
        # LLM 사용 여부와 무관하게 항상 계산. LLM에도 전달해 종합 의견에서 일관성 보장.
        try:
            ref_df_for_summary = load_ref() if load_ref else None
            summary_analysis_data = collect_analysis_data()
            exhibition_type_val = s.get("exhibition_type", None)
            data["summary_metrics"] = ae.compute_summary_metrics(
                summary_analysis_data, ref_df_for_summary, exhibition_type_val
            )
        except Exception:
            data["summary_metrics"] = []

        # ── LLM 분석 글쓰기 ──
        if api_key:
            with st.spinner("🤖 Claude가 분석 문단을 작성하고 있습니다..."):
                # 선택된 인사이트를 LLM에 전달할 형태로 변환
                insights_for_llm = data.get("section_insights", {})
                analysis_data = collect_analysis_data()

                # v4 단계 5b: 큐레이터 메모 입력란 제거됨. LLM이 데이터 자체로 종합.
                llm_result = rewrite_insights(
                    api_key=api_key,
                    exhibition_title=s.exhibition_title,
                    insights_by_section=insights_for_llm,
                    analysis_data=analysis_data,
                    eval_drafts=None,
                    theme_text=s.get("theme_text", ""),
                    summary_metrics=data.get("summary_metrics", []),
                    visitor_reviews=data.get("visitor_reviews", []),
                )

                if llm_result.is_fallback:
                    if llm_result.error:
                        st.warning(f"AI 글쓰기 실패 — 룰 기반으로 대체합니다.\n{llm_result.error}")
                    else:
                        st.info("룰 기반 텍스트를 사용합니다.")
                else:
                    cost = estimate_cost(
                        llm_result.input_tokens,
                        llm_result.output_tokens,
                        cache_creation_tokens=llm_result.cache_creation_tokens,
                        cache_read_tokens=llm_result.cache_read_tokens,
                    )
                    cache_note = ""
                    if cost["cache_hit"]:
                        cache_note = f" · 캐시 히트 {cost['cache_read_tokens']:,} 토큰 재사용"
                    elif cost["cache_creation_tokens"]:
                        cache_note = f" · 캐시 생성 {cost['cache_creation_tokens']:,} 토큰 (다음 호출부터 적용)"
                    st.success(
                        f"AI 분석 글쓰기 완료 — "
                        f"{cost['total_tokens']:,} 토큰 사용 "
                        f"(약 {cost['cost_krw']:.0f}원)"
                        f"{cache_note}"
                    )

                # 결과를 report data에 삽입
                data["llm_sections"] = llm_result.sections

        # ── 세션 상태에 저장 (미리보기·편집 UI에서 사용) ──
        st.session_state["report_state"] = {
            "data": data,
            "llm_sections_original": dict(data.get("llm_sections", {})),
            "title": s.exhibition_title or "v3",
        }
        # 재생성 시 이전 편집 클리어
        for sec in ["composition", "results", "promotion", "evaluation", "audience_response"]:
            st.session_state.pop(f"preview_edit_{sec}", None)

        st.success("보고서가 준비되었습니다. 아래에서 미리보기·편집·다운로드하세요.")

    except Exception as e:
        st.error(f"보고서 생성 오류: {e}")
        import traceback
        st.code(traceback.format_exc())


def _render_preview_and_edit():
    """보고서 미리보기 + 인라인 편집 + Word 다운로드.

    Streamlit text_area 기반. 편집 시 자동 반영되어 다운로드는 항상 최신 상태.
    LLM 미생성 시에도 표시(편집은 불가, 다운로드만 가능).
    """
    state = st.session_state.get("report_state")
    if not state:
        return

    data = state["data"]
    original_sections = state["llm_sections_original"]

    # ── 웹 미리보기: 새 탭으로 열기(인라인 iframe 미사용 — 본문 길이 보존) ──
    try:
        import json as _json
        from html_report import build_report_html
        import streamlit.components.v1 as components
        edited = dict(original_sections)
        for _k in ("composition", "results", "promotion", "evaluation",
                   "audience_response"):
            _ek = f"preview_edit_{_k}"
            if _ek in st.session_state:
                edited[_k] = st.session_state[_ek]
        _pdata = dict(data)
        _pdata["llm_sections"] = edited
        _report_html = build_report_html(_pdata)
        # JS 문자열 리터럴로 안전 인코딩 + </script>·</ 조기 종료 방지
        _html_js = _json.dumps(_report_html).replace("</", "<\\/")
        st.markdown("---")
        subsection("", "보고서 미리보기")
        st.caption("정본은 웹(HTML) 리포트입니다. 새 창에서 열어 검토하고, "
                   "그 화면의 ‘인쇄 / PDF로 저장’으로 PDF를 만들 수 있습니다.")
        _rtitle = (data.get("overview", {}).get("title")
                   or data.get("exhibition_title") or "report")
        _launcher = (
            "<script>\n"
            "var REPORT_HTML = " + _html_js + ";\n"
            "function openReport(){\n"
            "  var w = window.open('', '_blank');\n"
            "  if(!w){ alert('팝업이 차단되었습니다. 허용 후 다시 시도하세요.'); return; }\n"
            "  w.document.open(); w.document.write(REPORT_HTML); w.document.close();\n"
            "}\n"
            "</script>\n"
            "<button onclick=\"openReport()\" "
            "style=\"background:#255c4a;color:#fff;border:none;border-radius:8px;"
            "padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;"
            "font-family:sans-serif;\">웹 미리보기 열기 (새 창)</button>"
            "<div style=\"font-size:12px;color:#646b61;margin-top:6px;\">"
            "팝업이 차단되면 허용해 주세요.</div>"
        )
        components.html(_launcher, height=70)
        # HTML 파일 다운로드(공유·보관용 — 어디서나 동일하게 열림)
        dl_col, _ = st.columns([2, 8])
        with dl_col:
            st.download_button(
                "HTML 파일 다운로드", _report_html,
                file_name=f"전시보고서_{_rtitle}.html",
                mime="text/html", use_container_width=True)
    except Exception as e:
        st.caption(f"웹 미리보기 생성 실패: {type(e).__name__}: {e}")

    st.markdown("---")
    subsection("", "분석 문단 편집 & Word 다운로드")
    st.caption("아래에서 문단을 수정하면 미리보기와 Word 다운로드에 함께 반영됩니다.")

    # 가로 폭 원칙(CLAUDE.md): 표·편집영역을 ~60% 컬럼 안에 렌더
    edit_col = st.container(key="ws_gen_edit")
    with edit_col:
        # 핵심 수치 종합표 (자동 계산, 편집 불가)
        summary = data.get("summary_metrics", [])
        if summary:
            with st.expander("VI. 핵심 수치 종합표 (자동 계산)", expanded=False):
                ref_label = summary[0].get("reference_label", "역대 전시")
                st.caption(f"비교 기준: {ref_label} 평균")
                df_summary = pd.DataFrame([
                    {
                        "지표": m["label"],
                        "본 전시": m["current_fmt"],
                        "비교 평균": m["reference_avg_fmt"],
                        "차이": m["diff_fmt"],
                    } for m in summary
                ])
                st.dataframe(df_summary, hide_index=True, use_container_width=True)

        # 편집 가능한 LLM 섹션 (보고서 등장 순서)
        section_order = [
            ("composition",       "III. 전시 구성 — 분석 문단"),
            ("results",           "IV. 전시 결과 — 분석 문단"),
            ("promotion",         "V. 홍보 — 분석 문단"),
            ("evaluation",        "VI. Executive Summary — 종합 의견"),
            ("audience_response", "VI. Executive Summary — 관객 반응 종합"),
        ]

        st.markdown("**분석 문단 편집**")
        has_editable = False
        for key, label in section_order:
            original = (original_sections.get(key) or "").strip()
            if not original:
                continue
            has_editable = True
            st.text_area(
                label,
                value=st.session_state.get(f"preview_edit_{key}", original),
                key=f"preview_edit_{key}",
                height=180,
            )

        if not has_editable:
            st.info("편집 가능한 LLM 생성 문단이 없습니다 (LLM 비활성화 또는 인사이트 없음). 본문은 룰 기반 텍스트로 채워집니다.")

    # ── 액션 영역: Word 다운로드(자동 갱신) + 원본 복원 ──
    # 가로 폭 원칙: 좌측 ~60% 안에 두 버튼 배치
    st.markdown("---")
    col_dl, col_reset, _ = st.columns([2.2, 1, 1.8])

    with col_dl:
        try:
            from report_generator import generate_report

            # 현재 편집 상태를 반영한 data 구성
            edited_sections = dict(original_sections)
            for key, _label in section_order:
                edit_key = f"preview_edit_{key}"
                if edit_key in st.session_state:
                    edited_sections[key] = st.session_state[edit_key]

            final_data = dict(data)
            final_data["llm_sections"] = edited_sections

            output_path = os.path.join(tempfile.gettempdir(), "exhibition_report_v3.docx")
            generate_report(final_data, output_path)
            with open(output_path, "rb") as f:
                report_bytes = f.read()

            st.download_button(
                "편집 적용 Word 다운로드",
                report_bytes,
                file_name=f"전시보고서_{state['title']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Word 생성 오류: {e}")
            import traceback
            st.code(traceback.format_exc())

    with col_reset:
        if st.button("원본 복원", use_container_width=True, help="편집 사항을 모두 되돌립니다."):
            for key, _label in section_order:
                st.session_state.pop(f"preview_edit_{key}", None)
            st.rerun()


def _build_comparison(load_ref, exhibition_type, s):
    """비교형 차트용 기준치: 같은 유형 평균 / 같은 유형 마지막 전시.

    반환:
      {
        "weekly_ref": [(주당값, 라벨, None), ...],   # 주차별 추이 기준선
        "paid_ratio": [(라벨, 값%, is_current), ...] # 유료 비율 비교막대
      }
    데이터 부족 시 해당 항목은 빈 리스트.
    """
    out = {"weekly_ref": []}
    if not load_ref:
        return out
    try:
        import pandas as _pd
        ref_df = load_ref()
        if ref_df is None or len(ref_df) == 0:
            return out
        type_label = rd.get_type_label(exhibition_type)  # "기존 기획전" 등
        df = rd.filter_by_type(rd.exclude_type_zero(ref_df), exhibition_type)
        if df is None or len(df) == 0:
            return out

        # 같은 유형 마지막 전시 (시작일 기준) — 정확한 전시명 라벨용
        last_row = None
        if "전시 기간_시작" in df.columns:
            dd = df.copy()
            dd["_dt"] = _pd.to_datetime(
                dd["전시 기간_시작"].astype(str).str.replace(".", "-", regex=False),
                errors="coerce")
            dd = dd.dropna(subset=["_dt"]).sort_values("_dt")
            if len(dd):
                last_row = dd.iloc[-1]
        last_title = ""
        if last_row is not None:
            # 일부 원데이터에 《》가 포함돼 있어 중복 괄호 방지 위해 제거 후 재부착
            last_title = str(last_row.get("전시 제목", "") or "").strip().strip("《》 ")

        def _avg(col):
            if col not in df.columns:
                return None
            ser = _pd.to_numeric(df[col], errors="coerce").dropna()
            return float(ser.mean()) if len(ser) else None

        def _last(col):
            if last_row is None or col not in last_row:
                return None
            v = _pd.to_numeric(last_row.get(col), errors="coerce")
            return float(v) if _pd.notna(v) else None

        # ── 주차별 기준선: 일평균 × 7 (주당 환산) ──
        avg_daily = _avg("일평균 관객수")
        last_daily = _last("일평균 관객수")
        if avg_daily:
            out["weekly_ref"].append((avg_daily * 7, f"{type_label} 평균", None))
        if last_daily and last_title:
            short = last_title if len(last_title) <= 12 else last_title[:11] + "…"
            out["weekly_ref"].append((last_daily * 7, f"직전 《{short}》", None))
        return out
    except Exception:
        return out


def _collect_report_data(load_ref=None):
    """전체 데이터를 report_generator에 맞는 구조로 수집.

    load_ref: 레퍼런스 DataFrame 로더 — 종합표·비교형 차트 기준치 계산용.
    """
    s = st.session_state

    # 전시 기간
    period = ""
    days = 0
    if s.period_start and s.period_end:
        days = (s.period_end - s.period_start).days + 1
        period = f"{s.period_start.strftime('%Y.%m.%d')} - {s.period_end.strftime('%Y.%m.%d')} ({days}일간)"

    artists = [a.strip() for a in s.artists.split(",") if a.strip()]

    # 선택된 인사이트 수집 (섹션별)
    selected_insights = {}
    result = s.get("analysis_result")
    if result:
        by_section = ae.get_insights_by_section(result)
        for section_key, section_insights in by_section.items():
            items = []
            for i, ins in enumerate(section_insights):
                key = f"ins_{section_key}_{i}"
                # 출품 작품은 III장 도넛+서술이 전담 → 중복 방지 위해 인사이트에서 제외
                if section_key == "composition" and ins.category == "작품":
                    continue
                if s.get("insight_selections", {}).get(key, ins.priority <= 2):
                    text = s.get("insight_texts", {}).get(key, ins.text)
                    items.append({
                        "category": ins.category,
                        "category_label": ae.CATEGORY_LABELS.get(ins.category, ins.category),
                        "text": text,
                    })
            selected_insights[section_key] = items

    # 자동 도출 평가 항목 수집 (v4 단계 5b: 큐레이터 직접 입력란 제거됨)
    def collect_eval(drafts_key):
        items = []
        for d in s.get(drafts_key, []):
            if d.selected:
                items.append(d.text)
        return items

    # 유사 전시 비교 (그래프로 렌더링됨; 표 데이터는 호환용으로 보존)
    sim_headers = None
    sim_data = None
    sim_rows = []
    if result and result.similar_comparison_table is not None:
        df = result.similar_comparison_table
        sim_headers = list(df.columns)
        sim_data = df.values.tolist()
    if result:
        sim_rows = result.similar_exhibitions or []

    data = {
        "exhibition_title": s.exhibition_title,
        "overview": {
            "title": s.exhibition_title,
            "period": period,
            "artists": artists,
            "chief_curator": s.chief_curator,
            "curators": s.curators,
            "coordinators": s.coordinators,
            "curatorial_team": s.curatorial_team,
            "pr": s.pr_person,
            "sponsors": s.sponsors,
            "total_budget": fmt_money(s.total_budget),
            "budget_breakdown": [],
            "total_revenue": fmt_money(s.total_revenue),
            "programs": f"총 {s.program_count}개({s.program_sessions}회) 프로그램 진행, {s.program_participants:,}명 참여" if s.program_count else "",
            "staff_count": f"스태프 {s.staff_paid}명, 봉사자 {s.staff_volunteer}명" if s.staff_paid else "",
            "visitors": fmt_number(s.total_visitors, "명"),
            "exhibition_days": str(days) + "일" if days else "",
        },
        "theme_text": s.theme_text,
        "graphic_designer": s.get("graphic_designer", ""),
        "space_designer": s.get("space_designer", ""),
        "rooms": [],
        "related_programs": [p for p in s.related_programs if p.get("title")],
        "program_photos": [],
        "staff": {},
        "printed_materials": [m for m in s.printed_materials if m.get("type")],
        "material_photos": [],
        "budget": {
            "total_spent": fmt_money(s.total_budget),
            "breakdown_notes": [n for n in s.budget_breakdown_notes if n.strip()],
            "summary": [x for x in s.budget_summary if x.get("category")],
            "arrow_notes": [n for n in s.budget_arrow_notes if n.strip()],
            "chart_data": {},
            "details": [d for d in s.budget_details if d.get("subcategory") or d.get("detail")],
        },
        "revenue": {
            "total_visitors": fmt_number(s.total_visitors, "명"),
            "daily_average": fmt_number(s.total_visitors // days, "명") if (s.total_visitors and days) else "",
            "visitor_notes": [],
            "total_revenue": fmt_money(s.total_revenue),
            "ticket_revenue": fmt_money(s.ticket_revenue),
        },
        "visitor_composition": {
            "ticket_type": {},
            "ticket_analysis": [t for t in s.visitor_ticket_analysis if t.strip()],
            "visitor_type": {},
            "weekly_visitors": s.weekly_visitors,
            "analysis": s.visitor_analysis_text,
        },
        # 작품 정보 (v3 신규)
        "artworks": {
            "total": s.artwork_total,
            "new": s.get("artwork_new", 0),
            "old": s.get("artwork_old", max(0, s.artwork_total - s.get("artwork_new", 0))),
            "painting": s.artwork_painting,
            "sculpture": s.artwork_sculpture,
            "photo": s.artwork_photo,
            "installation": s.artwork_installation,
            "media": s.artwork_media,
            "other": s.artwork_other,
        },
        "promotion": {
            "advertising": s.promo_advertising,
            "press_release": s.promo_press_release,
            "web_invitation": s.promo_web_invitation,
            "newsletter": s.promo_newsletter,
            "sns": s.promo_sns,
            "other": s.promo_other,
        },
        "press_coverage": {
            "print_media": [p for p in s.press_print if p.get("outlet")],
            "online_media": [p for p in s.press_online if p.get("outlet")],
        },
        "membership": s.membership_text,
        # v3: 섹션별 인사이트
        "section_insights": selected_insights,
        # v3: 평가
        "evaluation": {
            "positive": collect_eval("eval_positive_drafts"),
            "negative": collect_eval("eval_negative_drafts"),
            "improvements": collect_eval("eval_improvement_drafts"),
        },
        "visitor_reviews": [r for r in s.visitor_reviews if r.get("content")],
        # 유사 전시 (그래프 입력)
        "similar_comparison_headers": sim_headers,
        "similar_comparison_table": sim_data,
        "similar_exhibitions": sim_rows,
        "analysis_data_flat": collect_analysis_data(),
        # v5.3.63: 비교형 차트(주차 기준선·유료비율)용 — 같은 유형 평균/마지막
        "comparison": _build_comparison(load_ref, s.get("exhibition_type"), s),
    }

    # 입장권별 관객
    if s.visitor_general > 0: data["visitor_composition"]["ticket_type"]["일반"] = s.visitor_general
    if s.visitor_student > 0: data["visitor_composition"]["ticket_type"]["학생"] = s.visitor_student
    if s.visitor_invitation > 0: data["visitor_composition"]["ticket_type"]["초대권"] = s.visitor_invitation
    if s.visitor_artpass > 0: data["visitor_composition"]["ticket_type"]["예술인패스"] = s.visitor_artpass
    if s.visitor_discount > 0: data["visitor_composition"]["ticket_type"]["기타 할인"] = s.visitor_discount

    return data
