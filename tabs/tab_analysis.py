"""탭 C: 자동 분석 & 평가 초안"""

import streamlit as st
import reference_data as rd
import analysis_engine as ae
from utils import collect_analysis_data


def render(tab, load_reference_data):
    with tab:
        st.markdown('<div class="section-header">🔍 분석 & 평가</div>', unsafe_allow_html=True)
        st.caption("정량 데이터를 기반으로 과거 전시와 비교 분석하고, 평가 문장 초안을 자동 생성합니다.")

        ref_df = load_reference_data()
        if ref_df is None:
            st.warning("⚠️ 레퍼런스 데이터를 찾을 수 없습니다.")
            return

        # 분석 대상 수
        analysis_count = len(rd.exclude_type_zero(ref_df))
        st.info(f"📊 {analysis_count}개 과거 전시 데이터 기반 비교 분석")

        # 전시 유형 선택
        col1, col2 = st.columns([2, 1])
        with col1:
            type_col = "전시 유형"
            if type_col in ref_df.columns and ref_df[type_col].notna().any():
                valid_types = sorted([t for t in ref_df[type_col].dropna().unique() if int(t) != 0])
                options = ["전체 (유형 0 제외)"] + [f"{int(t)}유형 ({rd.get_type_count(ref_df, t)}개)" for t in valid_types]
                idx = st.selectbox("비교 대상 유형", range(len(options)),
                                   format_func=lambda i: options[i], key="type_select")
                exhibition_type = valid_types[idx - 1] if idx > 0 else None
            else:
                exhibition_type = None

        with col2:
            st.write("")
            st.write("")
            run_analysis = st.button("🔍 분석 실행", type="primary", use_container_width=True)

        # ── 분석 실행 ──
        if run_analysis:
            current = collect_analysis_data()
            has_data = any(v is not None and v != 0 for k, v in current.items() if k != "전시 제목")
            if not has_data:
                st.warning("분석할 데이터가 부족합니다. '정량 데이터' 탭에서 정보를 먼저 입력해주세요.")
            else:
                result = ae.generate_all_insights(current, ref_df, exhibition_type=exhibition_type)
                st.session_state["analysis_result"] = result
                st.session_state["insight_selections"] = {}
                st.session_state["insight_texts"] = {}
                # 평가 초안 초기화
                st.session_state["eval_positive_drafts"] = [
                    d for d in result.eval_drafts if d.eval_type == "positive"]
                st.session_state["eval_negative_drafts"] = [
                    d for d in result.eval_drafts if d.eval_type == "negative"]
                st.session_state["eval_improvement_drafts"] = [
                    d for d in result.eval_drafts if d.eval_type == "improvement"]

        # ── 결과 표시 ──
        if "analysis_result" not in st.session_state or st.session_state["analysis_result"] is None:
            st.markdown("---")
            st.markdown("*'정량 데이터' 탭에서 데이터를 입력한 뒤 '분석 실행'을 눌러주세요.*")
            return

        result = st.session_state["analysis_result"]

        if not result.insights:
            st.info("생성된 인사이트가 없습니다.")
            return

        # ═══════════════════════════════════════
        # PART 1: 분석 인사이트
        # ═══════════════════════════════════════
        st.markdown("---")
        st.subheader(f"📊 분석 인사이트 ({len(result.insights)}건)")
        st.caption("체크박스로 보고서에 포함할 항목을 선택하고, 텍스트를 자유롭게 수정할 수 있습니다. "
                   "각 인사이트는 보고서의 해당 섹션에 자동 배치됩니다.")

        # 섹션별 그룹핑
        by_section = ae.get_insights_by_section(result)

        for section_key in ["results", "composition", "promotion", "evaluation"]:
            if section_key not in by_section:
                continue

            section_insights = by_section[section_key]
            section_label = ae.SECTION_LABELS.get(section_key, section_key)

            with st.expander(f"📌 {section_label}에 배치 ({len(section_insights)}건)", expanded=True):
                for i, ins in enumerate(section_insights):
                    key = f"ins_{section_key}_{i}"

                    col_check, col_text = st.columns([0.5, 9.5])
                    with col_check:
                        default = ins.priority <= 2
                        prev = st.session_state["insight_selections"].get(key, default)
                        selected = st.checkbox("", value=prev, key=f"chk_{key}",
                                               label_visibility="collapsed")
                        st.session_state["insight_selections"][key] = selected

                    with col_text:
                        icon = ae.CATEGORY_ICONS.get(ins.category, "")
                        badges = []
                        if ins.rank and ins.total_count:
                            badges.append(f"#{ins.rank}/{ins.total_count}")
                        badge_str = " ".join(f"`{b}`" for b in badges)

                        st.markdown(f"{icon} **{ins.title}** {badge_str}")

                        prev_text = st.session_state["insight_texts"].get(key, ins.text)
                        edited = st.text_area("", value=prev_text, key=f"txt_{key}",
                                              height=68, label_visibility="collapsed")
                        st.session_state["insight_texts"][key] = edited

        # ═══════════════════════════════════════
        # PART 2: 유사 전시 비교
        # ═══════════════════════════════════════
        if result.similar_comparison_table is not None:
            st.markdown("---")
            st.subheader("📋 유사 전시 비교표")
            st.dataframe(result.similar_comparison_table, use_container_width=True, hide_index=True)

        # ═══════════════════════════════════════
        # PART 3: 평가 문장 자동 초안
        # ═══════════════════════════════════════
        st.markdown("---")
        st.subheader("📝 평가 자동 초안")
        st.caption("데이터 패턴에서 도출된 평가 문장 초안입니다. 수정하거나 삭제하고, 직접 추가할 수도 있습니다.")

        _render_eval_section("✅ 긍정 평가", "positive",
                             st.session_state.get("eval_positive_drafts", []),
                             "eval_positive_custom")

        _render_eval_section("⚠️ 부정 평가", "negative",
                             st.session_state.get("eval_negative_drafts", []),
                             "eval_negative_custom")

        _render_eval_section("💡 개선 방안", "improvement",
                             st.session_state.get("eval_improvement_drafts", []),
                             "eval_improvement_custom")


def _render_eval_section(title, eval_type, drafts, custom_key):
    """평가 초안 섹션 렌더링"""
    st.markdown(f"**{title}**")

    if not drafts:
        st.caption("자동 생성된 항목이 없습니다.")
    else:
        for i, draft in enumerate(drafts):
            key = f"eval_{eval_type}_{i}"
            col_check, col_text = st.columns([0.5, 9.5])
            with col_check:
                prev = getattr(draft, 'selected', True)
                selected = st.checkbox("", value=prev, key=f"echk_{key}",
                                       label_visibility="collapsed")
                drafts[i].selected = selected
            with col_text:
                st.markdown(f'<div class="eval-draft">{draft.text}</div>', unsafe_allow_html=True)
                edited = st.text_area("", value=draft.text, key=f"etxt_{key}",
                                      height=60, label_visibility="collapsed")
                drafts[i].text = edited

    # 사용자 직접 추가
    st.caption("직접 추가:")
    if custom_key not in st.session_state:
        st.session_state[custom_key] = [""]
    for i, txt in enumerate(st.session_state[custom_key]):
        st.session_state[custom_key][i] = st.text_input(
            f"추가 {i+1}", value=txt, key=f"custom_{eval_type}_{i}",
            label_visibility="collapsed")

    if st.button(f"➕ 항목 추가", key=f"add_custom_{eval_type}"):
        st.session_state[custom_key].append("")
        st.rerun()
