"""
일민미술관 전시 워크스페이스 v5.1 — UI 헬퍼.

GPT v4.1의 디자인 언어(eyebrow 라벨, 미술관 톤 카드)를 Streamlit에서
구현하기 위한 공통 헬퍼. 모든 탭에서 import 가능.
"""

from typing import Optional, List, Dict
import streamlit as st


def eyebrow(text: str) -> None:
    """Eyebrow 라벨 단독 렌더 (작은 대문자 강조 라벨)."""
    st.markdown(f'<div class="eyebrow">{text}</div>', unsafe_allow_html=True)


def section_header(eyebrow_text: str, title: str, subtitle: str = "") -> None:
    """미술관 톤 섹션 헤더 — eyebrow + 큰 타이틀 + 옵션 부제.

    Examples:
        section_header("EXHIBITION WORKSPACE", "전시 워크스페이스",
                       "저장된 전시를 선택하거나 새로 만드세요.")
    """
    html = (
        f'<div class="eyebrow">{eyebrow_text}</div>'
        f'<div class="section-header">{title}</div>'
    )
    if subtitle:
        html += f'<p class="main-subtitle">{subtitle}</p>'
    st.markdown(html, unsafe_allow_html=True)


def subsection(eyebrow_text: str, title: str) -> None:
    """탭 내 하위 섹션 헤더 — eyebrow + 타이틀 (L3).

    상위 section_header(L2)보다 작고, 같은 탭 안의 그룹화 용도.

    Examples:
        subsection("BUDGET", "예산 및 수입")
    """
    st.markdown(
        f'<div style="margin: 18px 0 6px 0;">'
        f'<div class="eyebrow">{eyebrow_text}</div>'
        f'<div style="font-size: 14px; font-weight: 700; color: #20231f; '
        f'line-height: 1.3;">{title}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def chip(text: str, kind: str = "") -> str:
    """Chip HTML 문자열 반환 (st.markdown으로 출력 필요).

    kind: "" | "high" | "medium" | "low" | "completed" | "in-progress" | "draft" | "archived"
    """
    cls = f"chip {kind}".strip()
    return f'<span class="{cls}">{text}</span>'


def chip_row(chips: List[str]) -> None:
    """chip 여러 개를 한 줄로 렌더."""
    if not chips:
        return
    st.markdown("".join(chips), unsafe_allow_html=True)


def metric_card(label: str, value: str, context: str = "") -> str:
    """Metric card HTML 문자열 반환. 여러 개를 한 strip으로 묶을 때 사용."""
    context_html = f'<div class="metric-context">{context}</div>' if context else ""
    return (
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'{context_html}'
        f'</div>'
    )


def metric_strip(metrics: List[Dict]) -> None:
    """metric card 여러 개를 그리드로 렌더.

    metrics: [{"label": ..., "value": ..., "context": ""}]
    """
    if not metrics:
        return
    cards = "".join(metric_card(**m) for m in metrics)
    st.markdown(f'<div class="metric-strip">{cards}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 상태/유형 → chip 변환 (도메인 헬퍼)
# ──────────────────────────────────────────────

STATUS_LABELS = {
    "draft": "초안",
    "in_progress": "진행 중",
    "completed": "완료",
    "archived": "보관",
}
STATUS_CHIP_KIND = {
    "draft": "draft",
    "in_progress": "in-progress",
    "completed": "completed",
    "archived": "archived",
}
TYPE_LABELS = {1: "정기 기획전", 2: "특별전", 3: "기타", 0: "분석 제외"}


def status_chip(status: str) -> str:
    label = STATUS_LABELS.get(status, status or "—")
    kind = STATUS_CHIP_KIND.get(status, "")
    return chip(label, kind)


def type_chip(type_num: Optional[int]) -> str:
    label = TYPE_LABELS.get(type_num, "미분류")
    return chip(label)
