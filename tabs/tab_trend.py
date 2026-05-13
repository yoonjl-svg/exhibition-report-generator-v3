"""
탭 T: 트렌드 + 다중 비교 — 미술관 전체 누적 데이터의 시간축·횡단 비교.

워크스페이스 안에 expander로 포함되며, 두 가지 뷰 제공:
  1. 📈 시계열 트렌드: 전시별 핵심 지표를 시간 축에 따라 라인 차트
  2. 📋 다중 비교: 2~4개 전시를 선택해 카드 형태로 side-by-side 표시

데이터는 KB에서 로드된 records 리스트를 받음 (워크스페이스가 전달).
"""

from datetime import date
from typing import List, Dict, Optional

import streamlit as st
import pandas as pd
import altair as alt

from ui_helpers import (
    subsection, chip, status_chip, type_chip,
    metric_card, metric_strip,
    TYPE_LABELS,
)


# 미술관 톤 색상 (Altair용)
COLOR_ACCENT = "#255c4a"      # 메인 라인·점 (녹색)
COLOR_ACCENT_2 = "#b4512a"    # 평균 기준선 (테라코타)
COLOR_LINE = "#d9ddd4"        # 격자
COLOR_MUTED = "#646b61"       # 축 라벨


# ──────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────

def render(records: List[Dict]):
    """워크스페이스에서 호출. records: 전체 전시 레코드 목록."""
    analyzable = [r for r in records if r.get("type") != 0]
    if len(analyzable) < 2:
        st.info("📭 시계열·비교 분석은 최소 2건의 전시가 필요합니다. (분석 제외 전시는 집계에서 빠짐)")
        return

    tabs = st.tabs(["📈 누적 흐름", "📋 다중 전시 비교"])

    with tabs[0]:
        _render_trend(analyzable)

    with tabs[1]:
        _render_compare(analyzable)


# ──────────────────────────────────────────────
# 시계열 트렌드
# ──────────────────────────────────────────────

# 추적할 핵심 지표 정의
TREND_METRICS = [
    # (라벨, data 키, 단위, 파생 여부, higher_is_better)
    ("총 관객 수", "total_visitors", "명", False, True),
    ("일평균 관객", "_daily_avg", "명", True, True),
    ("총 사용 예산", "total_budget", "원", False, None),
    ("관객당 비용", "_cost_per_visitor", "원", True, False),
    ("언론 보도 건수", "press_count", "건", False, True),
    ("프로그램 참여 인원", "program_participants", "명", False, True),
]


def _build_trend_df(records: List[Dict]) -> pd.DataFrame:
    """records → DataFrame (시간 축 = period_start, 컬럼 = 지표·메타)."""
    rows = []
    for r in records:
        data = r.get("data", {})
        ps = data.get("period_start")
        if not ps:
            continue

        tv = data.get("total_visitors") or 0
        tb = data.get("total_budget") or 0

        # 일평균 관객 (파생)
        daily_avg = None
        pe = data.get("period_end")
        if ps and pe:
            try:
                s = date.fromisoformat(ps)
                e = date.fromisoformat(pe)
                days = (e - s).days + 1
                if days > 0 and tv > 0:
                    daily_avg = tv / days
            except (ValueError, TypeError):
                pass

        # 관객당 비용 (파생)
        cost_per_visitor = None
        if tv > 0 and tb > 0:
            cost_per_visitor = tb / tv

        rows.append({
            "id": r.get("id"),
            "title": data.get("exhibition_title") or "(제목없음)",
            "type": r.get("type"),
            "type_label": TYPE_LABELS.get(r.get("type"), "미분류"),
            "period_start": ps,
            "total_visitors": tv or None,
            "_daily_avg": daily_avg,
            "total_budget": tb or None,
            "_cost_per_visitor": cost_per_visitor,
            "press_count": data.get("press_count") or None,
            "program_participants": data.get("program_participants") or None,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["period_start_dt"] = pd.to_datetime(df["period_start"], errors="coerce")
    df = df.dropna(subset=["period_start_dt"]).sort_values("period_start_dt")
    return df


def _render_trend(records: List[Dict]):
    """시계열 라인 차트들 렌더."""
    df = _build_trend_df(records)
    if df.empty:
        st.info("시계열 데이터가 부족합니다.")
        return

    # 유형 필터
    col1, col2 = st.columns([1, 3])
    with col1:
        type_options = ["전체"] + [TYPE_LABELS[k] for k in (1, 2, 3) if k in TYPE_LABELS]
        type_filter = st.selectbox("유형 필터", type_options, key="trend_type_filter")

    type_to_num = {v: k for k, v in TYPE_LABELS.items()}
    if type_filter != "전체":
        target = type_to_num.get(type_filter)
        df = df[df["type"] == target]

    if df.empty:
        st.info("해당 유형의 전시가 없습니다.")
        return

    st.caption(f"📊 {len(df)}건 전시의 시간축 추이 (시작일 기준)")

    # 6개 지표를 2행 x 3열 그리드로
    rows = [TREND_METRICS[i:i+3] for i in range(0, len(TREND_METRICS), 3)]
    for row in rows:
        cols = st.columns(len(row))
        for col, (label, key, unit, _is_derived, _hib) in zip(cols, row):
            with col:
                _render_metric_trend(df, label, key, unit)


def _render_metric_trend(df: pd.DataFrame, label: str, key: str, unit: str):
    """단일 지표의 시계열 차트 + 통계 표시.

    Altair 기반:
      - 라인: 시간순 추세
      - 점(circle): 각 전시 위치, 호버 시 툴팁
      - 평균 기준선: 가로 점선 (테라코타 색)
      - 툴팁: 전시명·시작일·값·유형
    """
    # 결측 제거
    sub = df[["period_start_dt", "title", "type_label", key]].dropna(subset=[key]).copy()
    if sub.empty:
        st.markdown(f"**{label}**")
        st.caption("데이터 없음")
        return

    # 통계 요약
    mean_v = float(sub[key].mean())
    latest_row = sub.iloc[-1]
    latest = float(latest_row[key])
    latest_title = str(latest_row["title"])
    delta_pct = ((latest - mean_v) / mean_v * 100) if mean_v else 0

    # 헤더 + 캡션
    st.markdown(f"**{label}**")
    st.caption(
        f"평균 {_fmt_value(mean_v, unit)} · "
        f"최근 《{latest_title[:14]}{'…' if len(latest_title) > 14 else ''}》 "
        f"{_fmt_value(latest, unit)} ({'+' if delta_pct >= 0 else ''}{delta_pct:.1f}%)"
    )

    # 포맷된 값 컬럼 (툴팁 표시용)
    sub["_formatted"] = sub[key].apply(lambda v: _fmt_value(v, unit))

    # 베이스 인코딩
    base = alt.Chart(sub).encode(
        x=alt.X(
            "period_start_dt:T",
            title=None,
            axis=alt.Axis(
                format="%Y-%m",
                grid=False,
                labelColor=COLOR_MUTED,
                labelFontSize=10,
                tickColor=COLOR_LINE,
            ),
        ),
        y=alt.Y(
            f"{key}:Q",
            title=None,
            axis=alt.Axis(
                grid=True,
                gridColor=COLOR_LINE,
                gridOpacity=0.6,
                labelColor=COLOR_MUTED,
                labelFontSize=10,
                tickCount=4,
            ),
            scale=alt.Scale(zero=False, nice=True),
        ),
        tooltip=[
            alt.Tooltip("title:N", title="전시"),
            alt.Tooltip("type_label:N", title="유형"),
            alt.Tooltip("period_start_dt:T", title="시작일", format="%Y-%m-%d"),
            alt.Tooltip("_formatted:N", title=label),
        ],
    )

    # 라인 (시간순 연결)
    line = base.mark_line(
        color=COLOR_ACCENT,
        strokeWidth=2,
        interpolate="linear",
    )

    # 점 (각 전시 위치)
    points = base.mark_circle(
        color=COLOR_ACCENT,
        size=80,
        opacity=0.9,
        stroke="white",
        strokeWidth=1.5,
    )

    # 평균 기준선 (가로 점선)
    mean_df = pd.DataFrame({"y": [mean_v], "label": [f"평균 {_fmt_value(mean_v, unit)}"]})
    mean_rule = alt.Chart(mean_df).mark_rule(
        color=COLOR_ACCENT_2,
        strokeDash=[5, 4],
        strokeWidth=1.2,
        opacity=0.7,
    ).encode(y="y:Q")

    chart = (line + points + mean_rule).properties(
        height=200,
        padding={"left": 6, "right": 12, "top": 8, "bottom": 8},
    ).configure_view(
        strokeWidth=0,
    )

    st.altair_chart(chart, use_container_width=True)


def _fmt_value(v: float, unit: str) -> str:
    if v is None or pd.isna(v):
        return "—"
    if unit == "원":
        if v >= 100_000_000:
            return f"{v / 100_000_000:.2f}억"
        if v >= 10_000_000:
            return f"{v / 10_000:,.0f}만"
        return f"{v:,.0f}원"
    return f"{v:,.0f}{unit}"


# ──────────────────────────────────────────────
# 다중 전시 비교
# ──────────────────────────────────────────────

def _render_compare(records: List[Dict]):
    """전시들을 선택해 막대 차트로 비교.

    정규화 기준: **선택된 전시들 중 지표별 최소값 = 100%**.
    선택을 변경할 때마다 최소값이 재계산되어 비교가 항상 자체완결적.
    KB 전체의 outlier 영향 없음.
    """
    # 선택용 라벨
    options = []
    id_to_record = {}
    for r in records:
        data = r.get("data", {})
        title = data.get("exhibition_title") or "(제목없음)"
        year = (data.get("period_start") or "")[:4] or "—"
        type_lbl = TYPE_LABELS.get(r.get("type"), "미분류")
        label = f"{year} · {title} · {type_lbl}"
        options.append(label)
        id_to_record[label] = r

    st.caption("최소 2개의 전시를 선택하세요. 막대 길이는 선택된 전시들 중 지표별 최소값을 100%로 한 비율입니다.")
    # multiselect 너비 30% 제한 (이전 60% → 절반)
    ms_col, _ = st.columns([3, 7])
    with ms_col:
        selected_labels = st.multiselect(
            "비교할 전시 선택",
            options=options,
            key="compare_select",
            label_visibility="collapsed",
        )

    if len(selected_labels) < 2:
        return

    selected = [id_to_record[lbl] for lbl in selected_labels]
    _render_compare_chart(selected)


def _compute_selection_minimums(records: List[Dict]) -> Dict[str, float]:
    """선택된 전시들의 지표별 최소값을 계산.

    각 지표마다 유효값(>0)만 추려 최소값. 모든 값이 0/None인 지표는 None.
    """
    minimums = {}
    for label, key, _unit in COMPARE_METRICS:
        values = []
        for r in records:
            v = _extract_metric(r.get("data", {}), key)
            if v is not None and v > 0:
                values.append(v)
        minimums[label] = min(values) if values else None
    return minimums


# 비교 차트에 표시할 핵심 지표 (모두 "클수록 큼"이라 정규화 비교에 적합)
# 정규화 기준: 선택된 전시들 중 지표별 최소값 = 100% (선택 변경 시 매번 재계산)
COMPARE_METRICS = [
    # (라벨, key 또는 derived flag, 단위)
    ("총 관객", "total_visitors", "명"),
    ("일평균 관객", "_daily_avg", "명"),
    ("총 예산", "total_budget", "원"),
    ("총 수입", "total_revenue", "원"),
    ("프로그램 참여", "program_participants", "명"),
    ("보도 건수", "press_count", "건"),
    ("SNS 피드백", "sns_feedback", "건"),
]


def _extract_metric(data: dict, key: str) -> Optional[float]:
    """data dict에서 비교 지표 값 추출 (파생값 처리 포함)."""
    if key == "_daily_avg":
        ps, pe = data.get("period_start"), data.get("period_end")
        tv = data.get("total_visitors") or 0
        if not (ps and pe and tv > 0):
            return None
        try:
            s = date.fromisoformat(ps); e = date.fromisoformat(pe)
            days = (e - s).days + 1
            return tv / days if days > 0 else None
        except (ValueError, TypeError):
            return None
    if key == "_artwork_total":
        total = sum([
            data.get("artwork_painting", 0) or 0,
            data.get("artwork_sculpture", 0) or 0,
            data.get("artwork_photo", 0) or 0,
            data.get("artwork_installation", 0) or 0,
            data.get("artwork_media", 0) or 0,
            data.get("artwork_other", 0) or 0,
        ])
        return total if total > 0 else None
    v = data.get(key)
    return v if v else None


def _build_compare_long_df(records: List[Dict]) -> pd.DataFrame:
    """선택된 전시들의 비교용 long-format DataFrame.

    한 행 = (전시, 지표, 실제값, 최소값 대비 비율, 포맷된 값).
    정규화 기준: **선택된 전시들 중 지표별 최소값**을 1.0(=100%)으로.
    """
    # 선택 내 최소값 재계산
    minimums = _compute_selection_minimums(records)

    rows = []
    for r in records:
        data = r.get("data", {})
        full_title = data.get("exhibition_title") or "(제목없음)"
        short = full_title if len(full_title) <= 18 else full_title[:17] + "…"
        ps = data.get("period_start") or "—"
        pe = data.get("period_end") or "—"
        type_lbl = TYPE_LABELS.get(r.get("type"), "미분류")

        for label, key, unit in COMPARE_METRICS:
            v = _extract_metric(data, key)
            v_actual = v if v is not None else 0
            mn = minimums.get(label)
            if mn and mn > 0:
                normalized = v_actual / mn
            else:
                normalized = 0.0
            min_fmt = _fmt_value(mn, unit) if mn else "—"
            rows.append({
                "exhibition": full_title,
                "exhibition_short": short,
                "metric": label,
                "value": v_actual,
                "formatted": _fmt_value(v_actual, unit) if v_actual else "—",
                "normalized": normalized,
                "minimum_fmt": min_fmt,
                "period": f"{ps} ~ {pe}",
                "type_label": type_lbl,
            })

    return pd.DataFrame(rows)


def _render_compare_chart(records: List[Dict]):
    """Altair 선택 내 최소값(=100%) 그룹 막대 차트."""
    df = _build_compare_long_df(records)

    # 색 팔레트 (미술관 톤 + 추가 색)
    palette = [
        COLOR_ACCENT,       # 녹색
        COLOR_ACCENT_2,     # 테라코타
        "#3f5e99",          # 슬레이트 블루
        "#8a4b15",          # 갈색
        "#7a6b8b",          # 자줏빛
        "#4a7c59",          # 다른 녹색
        "#a8632c",          # 다른 테라코타
        "#5a6e80",          # 회청색
    ]
    palette = palette[:len(records)]

    # 막대 순서를 보존하기 위해 metric 순서 명시
    metric_order = [m[0] for m in COMPARE_METRICS]

    # Y축 도메인: 0 ~ 데이터 최대값 + 여유 (100% 초과 표시 가능)
    y_max = max(df["normalized"].max() if not df.empty else 1.0, 1.0)
    y_domain_max = max(y_max * 1.1, 1.2)  # 최소 120% 표시 (평균선 위 공간 확보)

    bars = alt.Chart(df).mark_bar(
        cornerRadiusTopLeft=2,
        cornerRadiusTopRight=2,
    ).encode(
        x=alt.X(
            "metric:N",
            title=None,
            sort=metric_order,
            axis=alt.Axis(
                labelAngle=0,
                labelFontSize=12,
                labelColor=COLOR_MUTED,
                labelPadding=8,
            ),
        ),
        xOffset=alt.XOffset(
            "exhibition_short:N",
            sort=[r.get("data", {}).get("exhibition_title", "")[:18] for r in records],
        ),
        y=alt.Y(
            "normalized:Q",
            title=None,
            scale=alt.Scale(domain=[0, y_domain_max]),
            axis=alt.Axis(
                grid=True,
                gridColor=COLOR_LINE,
                gridOpacity=0.6,
                format=".0%",
                labelColor=COLOR_MUTED,
                labelFontSize=10,
                tickCount=5,
            ),
        ),
        color=alt.Color(
            "exhibition_short:N",
            title="전시",
            scale=alt.Scale(range=palette),
            legend=alt.Legend(
                orient="top",
                labelFontSize=11,
                titleFontSize=11,
                titleColor=COLOR_MUTED,
                labelColor="#20231f",
                offset=4,
            ),
        ),
        tooltip=[
            alt.Tooltip("exhibition:N", title="전시"),
            alt.Tooltip("type_label:N", title="유형"),
            alt.Tooltip("metric:N", title="지표"),
            alt.Tooltip("formatted:N", title="실제 값"),
            alt.Tooltip("minimum_fmt:N", title="선택 내 최소값"),
            alt.Tooltip("normalized:Q", title="최소값 대비", format=".0%"),
            alt.Tooltip("period:N", title="기간"),
        ],
    )

    # 100% 기준선 (선택 내 최소값)
    base_rule = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(
        color=COLOR_ACCENT_2,
        strokeDash=[5, 4],
        strokeWidth=1.4,
        opacity=0.8,
    ).encode(y="y:Q")

    chart = (bars + base_rule).properties(
        height=340,
        padding={"left": 6, "right": 12, "top": 8, "bottom": 8},
    ).configure_view(strokeWidth=0)

    st.altair_chart(chart, use_container_width=True)

    st.caption(
        "막대 길이는 **선택된 전시들 중 지표별 최소값을 100%로 한 비율**. "
        "테라코타 점선이 기준선(100%). 막대가 200%면 선택 내 최소값의 2배. "
        "선택을 변경하면 최소값이 다시 계산되어 비율도 재조정됨. "
        "‘총 예산’은 클수록 좋다는 의미가 아니라 규모 비교용입니다."
    )
