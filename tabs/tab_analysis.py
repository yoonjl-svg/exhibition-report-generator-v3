"""탭 C: 자동 분석 및 평가 초안

v5.3.45 — GPT v4 툴의 '근거(Evidence)' 패턴 흡수.
각 인사이트를 카드로 표시하고, '근거' expander를 펼치면 해당 관찰이
어떤 수치에서 도출됐는지(현재 값·비교군 평균·평균 대비 차이·순위 등)를
투명하게 제공. 보고서 포함 여부 체크박스와 편집 가능 텍스트는 유지.
"""

import streamlit as st
import reference_data as rd
import analysis_engine as ae
from utils import collect_analysis_data
from ui_helpers import subsection, chip


# ──────────────────────────────────────────────
# 근거(Evidence) 포매팅
# ──────────────────────────────────────────────

# 보고서 섹션 → 짧은 칩 라벨 (앞의 로마숫자 제거)
_SECTION_CHIP = {
    "results": "전시 결과",
    "composition": "전시 구성",
    "promotion": "홍보",
    "evaluation": "평가",
}

# priority → (칩 라벨, 칩 kind) — 전용 클래스로 빨강/주황/노랑 변별
_PRIORITY_CHIP = {
    1: ("중요", "pri-1"),
    2: ("보통", "pri-2"),
    3: ("참고", "pri-3"),
}


def _fmt_val(v, unit: str, is_ratio: bool) -> str:
    """근거 값 표시 — 단위·비율 형식에 맞춰 사람이 읽기 쉽게."""
    if v is None:
        return "—"
    if is_ratio:
        return f"{v * 100:.1f}%"
    if unit == "%":
        return f"{v:.1f}%"
    if unit == "원":
        return f"{v:,.0f}원"
    if unit in ("명", "건", "개", "점"):
        return f"{v:,.0f}{unit}"
    # 단위 미지정 — 정수면 정수, 아니면 소수 1자리
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:,.1f}"


def _evidence_rows(ins) -> list:
    """Insight → 근거 데이터 포인트 [(label, value), ...]."""
    rows = []
    if ins.current_value is not None:
        rows.append((ins.metric_name, _fmt_val(ins.current_value, ins.unit, ins.is_ratio)))
    if ins.reference_avg is not None:
        rows.append(("비교군 평균", _fmt_val(ins.reference_avg, ins.unit, ins.is_ratio)))
    # 평균 대비 차이
    if ins.current_value is not None and ins.reference_avg not in (None, 0):
        if ins.is_ratio or ins.unit == "%":
            cur_p = ins.current_value * 100 if ins.is_ratio else ins.current_value
            avg_p = ins.reference_avg * 100 if ins.is_ratio else ins.reference_avg
            d = cur_p - avg_p
            rows.append(("평균 대비 차이", f"{'+' if d >= 0 else ''}{d:.1f}%p"))
        else:
            d = (ins.current_value - ins.reference_avg) / abs(ins.reference_avg) * 100
            rows.append(("평균 대비 차이", f"{'+' if d >= 0 else ''}{d:.1f}%"))
    # 직전 전시 + 직전 대비 차이 (비교군 중 가장 최근 전시)
    recent = getattr(ins, "recent_compares", None) or []
    if recent and ins.current_value is not None:
        prev_title, prev_val = recent[0]
        rows.append(("직전 전시",
                     f"{prev_title} · {_fmt_val(prev_val, ins.unit, ins.is_ratio)}"))
        if prev_val not in (None, 0):
            if ins.is_ratio or ins.unit == "%":
                cur_p = ins.current_value * 100 if ins.is_ratio else ins.current_value
                prev_p = prev_val * 100 if ins.is_ratio else prev_val
                dd = cur_p - prev_p
                rows.append(("직전 대비 차이", f"{'+' if dd >= 0 else ''}{dd:.1f}%p"))
            else:
                dd = (ins.current_value - prev_val) / abs(prev_val) * 100
                rows.append(("직전 대비 차이", f"{'+' if dd >= 0 else ''}{dd:.1f}%"))
    # 순위 — 상위/하위 34%에 속할 때만 노출
    if ins.rank and ins.total_count and ae.is_notable_rank(ins.rank, ins.total_count):
        rows.append(("순위", f"기존 전시 중 {ins.rank}위 / {ins.total_count}개"))
    # 분포 위치 — 상위/하위 % (백분위 대체)
    if ins.rank and ins.total_count:
        pos = ae.position_label(ins.rank, ins.total_count)
        if pos:
            rows.append(("분포 위치", pos))
    return rows


def _render_insight_card(ins, key: str, show_evidence: bool):
    """단일 인사이트를 카드로 렌더. 보고서 포함 체크 + 편집 텍스트 + 근거.

    가로 폭 원칙(CLAUDE.md): 카드는 호출부에서 ~60% 컬럼 안에 렌더되어
    풀폭으로 늘어나지 않는다. 이모지 없음.
    """
    with st.container(border=True):
        # ── 헤더: 제목 + 칩들 ──
        chips = []
        pr_label, pr_kind = _PRIORITY_CHIP.get(ins.priority, ("참고", "low"))
        chips.append(chip(pr_label, pr_kind))
        sec_label = _SECTION_CHIP.get(ins.section, ins.section)
        chips.append(chip(sec_label))
        chips.append(chip(ins.category))

        head_col, chip_col = st.columns([5, 5])
        with head_col:
            st.markdown(
                f'<div style="font-size: 14px; font-weight: 700; color: #20231f; '
                f'line-height: 1.35;">{ins.title}</div>',
                unsafe_allow_html=True,
            )
        with chip_col:
            st.markdown(
                f'<div style="text-align: right;">{"".join(chips)}</div>',
                unsafe_allow_html=True,
            )

        # ── 보고서 포함 체크박스 ──
        prev = st.session_state["insight_selections"].get(key, ins.priority <= 2)
        selected = st.checkbox("보고서 포함", value=prev, key=f"chk_{key}")
        st.session_state["insight_selections"][key] = selected

        # ── 편집 가능 관찰 텍스트 ──
        prev_text = st.session_state["insight_texts"].get(key, ins.text)
        edited = st.text_area("관찰", value=prev_text, key=f"txt_{key}",
                              height=70, label_visibility="collapsed")
        st.session_state["insight_texts"][key] = edited

        # ── 근거(Evidence) ──
        rows = _evidence_rows(ins)
        if rows:
            with st.expander("근거", expanded=show_evidence):
                lines = "".join(
                    f'<li style="margin: 2px 0;"><span style="color: #646b61;">{label}</span>'
                    f' · <strong style="color: #20231f;">{val}</strong></li>'
                    for label, val in rows
                )
                st.markdown(
                    f'<ul style="margin: 2px 0 0 0; padding-left: 18px; '
                    f'font-size: 13px; line-height: 1.6;">{lines}</ul>',
                    unsafe_allow_html=True,
                )


# ──────────────────────────────────────────────
# 메인 렌더
# ──────────────────────────────────────────────

def render(tab, load_reference_data):
    with tab:
        ref_df = load_reference_data()
        if ref_df is None:
            st.warning("레퍼런스 데이터를 찾을 수 없습니다.")
            return

        analysis_count = len(rd.exclude_type_zero(ref_df))
        st.caption(f"{analysis_count}개 과거 전시 데이터 기반 비교 분석")

        # ── 비교 대상 유형 + 분석 실행 ──
        col1, col2, _ = st.columns([2, 1, 3])
        with col1:
            type_col = "전시 유형"
            if type_col in ref_df.columns and ref_df[type_col].notna().any():
                valid_types = sorted([t for t in ref_df[type_col].dropna().unique() if int(t) != 0])
                options = ["전체 (유형 0 제외)"] + [
                    f"{int(t)}유형 ({rd.get_type_count(ref_df, t)}개)" for t in valid_types]
                idx = st.selectbox("비교 대상 유형", range(len(options)),
                                   format_func=lambda i: options[i], key="type_select")
                exhibition_type = valid_types[idx - 1] if idx > 0 else None
            else:
                exhibition_type = None
            st.session_state["exhibition_type"] = exhibition_type
        with col2:
            st.write("")
            st.write("")
            run_analysis = st.button("분석 실행", type="primary", use_container_width=True)

        # ── 분석 실행 ──
        if run_analysis:
            current = collect_analysis_data()
            has_data = any(v is not None and v != 0 for k, v in current.items() if k != "전시 제목")
            if not has_data:
                st.warning("분석할 데이터가 부족합니다. '전시 데이터' 탭에서 정보를 먼저 입력해주세요.")
            else:
                result = ae.generate_all_insights(current, ref_df, exhibition_type=exhibition_type)
                st.session_state["analysis_result"] = result
                st.session_state["insight_selections"] = {}
                st.session_state["insight_texts"] = {}
                st.session_state["eval_positive_drafts"] = [
                    d for d in result.eval_drafts if d.eval_type == "positive"]
                st.session_state["eval_negative_drafts"] = [
                    d for d in result.eval_drafts if d.eval_type == "negative"]
                st.session_state["eval_improvement_drafts"] = [
                    d for d in result.eval_drafts if d.eval_type == "improvement"]

        # ── 결과 없음 ──
        if "analysis_result" not in st.session_state or st.session_state["analysis_result"] is None:
            st.divider()
            st.markdown("*'전시 데이터' 탭에서 데이터를 입력한 뒤 '분석 실행'을 눌러주세요.*")
            return

        result = st.session_state["analysis_result"]
        if not result.insights:
            st.info("생성된 인사이트가 없습니다.")
            return

        # ═══════════════════════════════════════
        # PART 1: 분석 인사이트 (카드 + 근거)
        # ═══════════════════════════════════════
        st.divider()
        # 헤더·토글을 카드와 동일한 ~60% 폭 안에 둠 (가로 폭 원칙)
        head_wrap, _ = st.columns([3, 2])
        with head_wrap:
            hc1, hc2 = st.columns([2, 1])
            with hc1:
                subsection("", f"분석 인사이트 ({len(result.insights)}건)")
            with hc2:
                show_evidence = st.toggle("근거 모두 펼치기", value=False,
                                          key="show_all_evidence")
        st.caption("체크박스로 보고서 포함 여부를 정하고, 텍스트를 직접 수정할 수 있습니다. "
                   "각 카드의 ‘근거’를 펼치면 해당 관찰이 도출된 수치를 확인할 수 있습니다.")

        # 가로 폭 원칙(CLAUDE.md): 카드를 ~60% 컬럼 안에 렌더, 우측은 spacer.
        card_col, _ = st.columns([3, 2])
        with card_col:
            by_section = ae.get_insights_by_section(result)
            for section_key in ["results", "composition", "promotion", "evaluation"]:
                if section_key not in by_section:
                    continue
                section_insights = by_section[section_key]
                section_label = ae.SECTION_LABELS.get(section_key, section_key)

                st.markdown(
                    f'<div style="margin: 14px 0 6px 0; font-size: 13px; '
                    f'font-weight: 600; color: #255c4a;">{section_label}에 배치 '
                    f'({len(section_insights)}건)</div>',
                    unsafe_allow_html=True,
                )
                for i, ins in enumerate(section_insights):
                    key = f"ins_{section_key}_{i}"
                    _render_insight_card(ins, key, show_evidence)

        # ═══════════════════════════════════════
        # PART 2: 유사 전시 비교
        # ═══════════════════════════════════════
        if result.similar_comparison_table is not None:
            st.divider()
            subsection("", "유사 전시 비교")
            # 현재 전시 시작일(시간순 정렬·강조용)
            cur_start = None
            ps = st.session_state.get("period_start")
            if ps is not None:
                cur_start = ps.isoformat() if hasattr(ps, "isoformat") else str(ps)

            chart_col, _ = st.columns([3, 2])
            with chart_col:
                if result.similar_exhibitions:
                    from chart_generator import create_similar_compare_bar
                    current = collect_analysis_data()
                    bar_path = create_similar_compare_bar(
                        current, result.similar_exhibitions, current_start=cur_start)
                    if bar_path:
                        st.image(bar_path, use_container_width=True)
                        st.caption("지표별 최댓값=100% 정규화. 현재 전시(녹색)를 "
                                   "유사 전시 평균(회색)·유사 최근 2개와 비교. "
                                   "현재 막대 위는 실제 값.")

                # 비교표 — 날짜(yyyy-mm) 추가 + 최신 전시 상단 + 헤더 리네이밍
                df_tbl = result.similar_comparison_table
                try:
                    date_map = {r.title: (r.start or "")
                                for r in (result.similar_exhibitions or [])}
                    cur_title = collect_analysis_data().get("전시 제목") or "현재 전시"
                    date_map[cur_title] = cur_start or ""
                    df_tbl = df_tbl.copy()
                    df_tbl["_d"] = df_tbl["전시명"].map(lambda t: date_map.get(t, ""))
                    # 최신 전시부터 상단 (내림차순)
                    df_tbl = df_tbl.sort_values("_d", ascending=False, kind="stable")
                    df_tbl.insert(0, "날짜",
                                  df_tbl["_d"].map(lambda s: str(s)[:7] if s else "—"))
                    df_tbl = df_tbl.drop(columns=["_d"])
                    # 헤더 리네이밍 (요청 명칭)
                    df_tbl = df_tbl.rename(columns={
                        "총 관객수": "총 관객", "일평균 관객수": "일평균 관객",
                        "총 사용 예산": "사용 예산", "프로그램 총 수": "총 프로그램",
                        "언론 보도 건수": "언론 보도", "출품 작품 수_총": "작품 수",
                    })
                except Exception:
                    pass
                st.dataframe(df_tbl, use_container_width=True, hide_index=True)
