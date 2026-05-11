"""탭 D: 보고서 미리보기 & 생성"""

import os
import json
import tempfile
import streamlit as st
from datetime import date

from utils import fmt_money, fmt_number, collect_analysis_data
import analysis_engine as ae
import reference_data as rd
from llm_writer import rewrite_insights, validate_api_key, estimate_cost, HAS_ANTHROPIC


def render(tab, load_reference_data):
    with tab:
        st.markdown('<div class="section-header">📄 보고서 생성</div>', unsafe_allow_html=True)

        # ── 데이터 완성도 체크 ──
        _show_completeness_check()

        st.divider()

        # ── 보고서 구조 미리보기 ──
        st.subheader("📖 보고서 구조 미리보기")
        st.caption("최종 보고서의 흐름을 미리 확인합니다. 분석 인사이트가 각 섹션에 배치된 모습을 볼 수 있습니다.")

        _show_preview()

        st.divider()

        # ── AI 글쓰기 설정 ──
        st.subheader("✨ AI 분석 글쓰기")

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
                st.caption(f"✅ {msg} — Sonnet 모델로 분석 문단을 재작성합니다.")
            else:
                st.caption(f"⚠️ {msg}")

        use_llm = bool(api_key and api_key.strip().startswith("sk-ant-"))

        st.divider()

        # ── 생성 ──
        st.subheader("📥 보고서 생성")

        if use_llm:
            st.info("🤖 AI 글쓰기 활성화 — 보고서 생성 시 Claude Sonnet이 분석 문단을 보고서 문체로 재작성합니다.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 Word 보고서 생성", type="primary", use_container_width=True):
                _generate_report(api_key=api_key if use_llm else None)

        with col2:
            if st.button("💾 데이터 JSON 저장", use_container_width=True):
                _save_json()

        # JSON 불러오기
        st.divider()
        st.subheader("📂 데이터 불러오기")
        uploaded = st.file_uploader("이전 작업 JSON 파일", type=["json"], key="json_upload")
        if uploaded:
            if st.button("JSON 데이터 적용"):
                _load_json(uploaded)


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

    # VI. 평가 + 교차 분석 + 평가 초안
    with st.expander("**VI. 평가 및 개선 방안**", expanded=True):
        _show_section_insights("evaluation")

        st.markdown("**긍정 평가:**")
        _show_eval_items("positive")
        st.markdown("**부정 평가:**")
        _show_eval_items("negative")
        st.markdown("**개선 방안:**")
        _show_eval_items("improvement")


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
        st.caption("📊 데이터 기반 분석:")
        for ins, text in selected:
            icon = ae.CATEGORY_ICONS.get(ins.category, "")
            st.markdown(f"> {icon} {text}")


def _show_eval_items(eval_type):
    """평가 항목 미리보기 (사용자 메모)"""
    custom_key = f"eval_{eval_type}_custom"

    customs = st.session_state.get(custom_key, [])
    for c in customs:
        if c.strip():
            st.markdown(f"- {c}")

    if not any(c.strip() for c in customs):
        st.caption("(항목 없음)")


def _generate_report(api_key=None):
    """Word 보고서 생성 — LLM 글쓰기 통합"""
    try:
        from report_generator import generate_report

        data = _collect_report_data()
        s = st.session_state

        # ── LLM 분석 글쓰기 ──
        if api_key:
            with st.spinner("🤖 Claude가 분석 문단을 작성하고 있습니다..."):
                # 선택된 인사이트를 LLM에 전달할 형태로 변환
                insights_for_llm = data.get("section_insights", {})

                # 사용자 평가 메모 수집
                eval_drafts_for_llm = []
                for eval_type in ["positive", "negative", "improvement"]:
                    for c in s.get(f"eval_{eval_type}_custom", []):
                        if c.strip():
                            eval_drafts_for_llm.append({
                                "eval_type": eval_type,
                                "text": c.strip(),
                            })

                analysis_data = collect_analysis_data()

                llm_result = rewrite_insights(
                    api_key=api_key,
                    exhibition_title=s.exhibition_title,
                    insights_by_section=insights_for_llm,
                    analysis_data=analysis_data,
                    eval_drafts=eval_drafts_for_llm,
                )

                if llm_result.is_fallback:
                    if llm_result.error:
                        st.warning(f"⚠️ AI 글쓰기 실패 — 룰 기반으로 대체합니다.\n{llm_result.error}")
                    else:
                        st.info("ℹ️ 룰 기반 텍스트를 사용합니다.")
                else:
                    cost = estimate_cost(llm_result.input_tokens, llm_result.output_tokens)
                    st.success(
                        f"✅ AI 분석 글쓰기 완료 — "
                        f"{cost['total_tokens']:,} 토큰 사용 "
                        f"(약 {cost['cost_krw']:.0f}원)"
                    )

                # 결과를 report data에 삽입
                data["llm_sections"] = llm_result.sections

        # ── Word 보고서 생성 ──
        output_path = os.path.join(tempfile.gettempdir(), "exhibition_report_v3.docx")
        generate_report(data, output_path)

        with open(output_path, "rb") as f:
            st.download_button(
                "📥 보고서 다운로드",
                f.read(),
                file_name=f"전시보고서_{s.exhibition_title or 'v3'}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        st.success("✅ 보고서가 생성되었습니다!")

    except Exception as e:
        st.error(f"보고서 생성 오류: {e}")
        import traceback
        st.code(traceback.format_exc())


def _collect_report_data():
    """전체 데이터를 report_generator에 맞는 구조로 수집"""
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
                if s.get("insight_selections", {}).get(key, ins.priority <= 2):
                    text = s.get("insight_texts", {}).get(key, ins.text)
                    items.append({
                        "category": ins.category,
                        "category_label": ae.CATEGORY_LABELS.get(ins.category, ins.category),
                        "text": text,
                    })
            selected_insights[section_key] = items

    # 평가 수집
    def collect_eval(drafts_key, custom_key):
        items = []
        for d in s.get(drafts_key, []):
            if d.selected:
                items.append(d.text)
        for c in s.get(custom_key, []):
            if c.strip():
                items.append(c)
        return items

    # 유사 전시 비교표
    sim_headers = None
    sim_data = None
    if result and result.similar_comparison_table is not None:
        df = result.similar_comparison_table
        sim_headers = list(df.columns)
        sim_data = df.values.tolist()

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
            "positive": collect_eval("eval_positive_drafts", "eval_positive_custom"),
            "negative": collect_eval("eval_negative_drafts", "eval_negative_custom"),
            "improvements": collect_eval("eval_improvement_drafts", "eval_improvement_custom"),
        },
        "visitor_reviews": [r for r in s.visitor_reviews if r.get("content")],
        # 유사 전시
        "similar_comparison_headers": sim_headers,
        "similar_comparison_table": sim_data,
    }

    # 입장권별 관객
    if s.visitor_general > 0: data["visitor_composition"]["ticket_type"]["일반"] = s.visitor_general
    if s.visitor_student > 0: data["visitor_composition"]["ticket_type"]["학생"] = s.visitor_student
    if s.visitor_invitation > 0: data["visitor_composition"]["ticket_type"]["초대권"] = s.visitor_invitation
    if s.visitor_artpass > 0: data["visitor_composition"]["ticket_type"]["예술인패스"] = s.visitor_artpass
    if s.visitor_discount > 0: data["visitor_composition"]["ticket_type"]["기타 할인"] = s.visitor_discount

    return data


def _convert_dates(obj):
    """중첩 구조 안의 date 객체를 ISO 문자열로 변환"""
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _convert_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_dates(item) for item in obj]
    return obj


def _save_json():
    """현재 데이터를 JSON으로 저장"""
    s = st.session_state
    save_data = {}
    skip_keys = {"analysis_result", "insight_selections", "insight_texts",
                 "eval_positive_drafts", "eval_negative_drafts", "eval_improvement_drafts",
                 "json_upload", "type_select"}

    for key in s:
        if key.startswith(("chk_", "txt_", "echk_", "etxt_", "custom_")):
            continue
        if key in skip_keys:
            continue
        val = s[key]
        if isinstance(val, date):
            save_data[key] = val.isoformat()
        elif isinstance(val, (list, dict)):
            save_data[key] = _convert_dates(val)
        elif isinstance(val, (str, int, float, bool)):
            save_data[key] = val

    json_str = json.dumps(save_data, ensure_ascii=False, indent=2)
    st.download_button(
        "💾 JSON 다운로드",
        json_str,
        file_name=f"report_data_{s.exhibition_title or 'v3'}.json",
        mime="application/json",
    )


def _load_json(uploaded):
    """JSON에서 데이터 복원 — pending 패턴으로 위젯 충돌 회피"""
    try:
        data = json.loads(uploaded.read())
        # 위젯이 이미 렌더링된 상태이므로 직접 대입 불가.
        # _pending_json에 저장 후 rerun → app.py의 init_session에서 적용
        st.session_state["_pending_json"] = data
        st.rerun()
    except Exception as e:
        st.error(f"JSON 로드 오류: {e}")
