"""
v3 분석 엔진
- v2 기능 전체 포함 (단일 지표, 교차 분석, 유사 전시)
- 신규: 매체별 작품 구성 분석
- 신규: 예산 구조 분석 (전시비/부대비)
- 신규: 관객 다양성 분석 (학생, 패스, 단체)
- 신규: 인력 효율 분석
- 신규: 섹션별 인사이트 분류 (보고서 인라인 배치용)
- 신규: 평가 문장 자동 초안 생성
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

from reference_data import (
    compute_stats, compute_percentile, compute_rank,
    compute_derived_metrics, get_similar_exhibitions,
    exclude_type_zero, filter_by_type,
    get_type_label, get_type_count,
    format_number, format_percent, FieldStats,
)


# ──────────────────────────────────────────────
# 데이터 구조
# ──────────────────────────────────────────────

@dataclass
class Insight:
    """하나의 분석 인사이트"""
    category: str           # "관객", "예산", "프로그램", "홍보", "작품", "인력"
    section: str            # 보고서 삽입 위치: "results", "composition", "promotion", "evaluation"
    title: str
    text: str
    metric_name: str
    current_value: Optional[float] = None
    reference_avg: Optional[float] = None
    percentile: Optional[int] = None
    rank: Optional[int] = None
    total_count: Optional[int] = None
    priority: int = 2
    selected: bool = True


@dataclass
class EvalDraft:
    """자동 생성된 평가 문장 초안"""
    eval_type: str    # "positive", "negative", "improvement"
    text: str
    source_metric: str
    confidence: float = 0.8
    selected: bool = True


@dataclass
class SimilarExhibitionRow:
    title: str
    similarity: float
    metrics: dict = field(default_factory=dict)


@dataclass
class AnalysisResult:
    insights: list[Insight] = field(default_factory=list)
    eval_drafts: list[EvalDraft] = field(default_factory=list)
    similar_exhibitions: list[SimilarExhibitionRow] = field(default_factory=list)
    similar_comparison_table: Optional[pd.DataFrame] = None


# ──────────────────────────────────────────────
# 한국어 헬퍼 (v2 이관)
# ──────────────────────────────────────────────

def _direction_verb(diff_pct):
    return "상회합니다" if diff_pct > 0 else "하회합니다"

def _postposition(word, pair=("은", "는")):
    if not word:
        return pair[1]
    last_char = word.rstrip("0123456789,. 원명건개점%")
    if not last_char:
        digits_final = {"0": True, "1": True, "2": False, "3": True, "4": False,
                        "5": False, "6": True, "7": True, "8": True, "9": False}
        for c in reversed(word):
            if c in digits_final:
                return pair[0] if digits_final[c] else pair[1]
        return pair[1]
    last_code = ord(last_char[-1])
    if 0xAC00 <= last_code <= 0xD7A3:
        return pair[0] if (last_code - 0xAC00) % 28 != 0 else pair[1]
    return pair[1]

def _quality_word(diff_pct, higher_is_better=True):
    if higher_is_better:
        if diff_pct > 30: return "매우 우수한"
        elif diff_pct > 10: return "양호한"
        elif diff_pct > -10: return "평균 수준의"
        elif diff_pct > -30: return "다소 저조한"
        else: return "저조한"
    else:
        if diff_pct < -30: return "매우 효율적인"
        elif diff_pct < -10: return "효율적인"
        elif diff_pct < 10: return "평균 수준의"
        elif diff_pct < 30: return "다소 높은"
        else: return "높은"


# ──────────────────────────────────────────────
# 기본 인사이트 생성
# ──────────────────────────────────────────────

def _make_insight(
    category, section, title, metric_name,
    current_val, stats, unit="",
    higher_is_better=True, priority=2, group_label="역대"
) -> Optional[Insight]:
    if current_val is None or stats is None or stats.count < 3:
        return None
    avg = stats.mean
    if avg == 0:
        return None
    diff_pct = (current_val - avg) / abs(avg) * 100
    pct = compute_percentile(stats, current_val)
    rank = compute_rank(stats, current_val, ascending=not higher_is_better)
    current_fmt = format_number(current_val, unit)
    avg_fmt = format_number(avg, unit)
    pp = _postposition(metric_name, ("은", "는"))
    pp_ro = _postposition(current_fmt, ("으로", "로"))
    text = (
        f"이번 전시의 {metric_name}{pp} {current_fmt}{pp_ro}, "
        f"{group_label} 평균({avg_fmt}) 대비 {abs(diff_pct):.1f}% {_direction_verb(diff_pct)} "
        f"({stats.count}개 전시 중 {rank}위)."
    )
    return Insight(
        category=category, section=section, title=title, text=text,
        metric_name=metric_name, current_value=current_val,
        reference_avg=avg, percentile=pct, rank=rank,
        total_count=stats.count, priority=priority,
    )


def _diff_pct(val, stats):
    if val is None or stats is None or stats.mean == 0:
        return None
    return (val - stats.mean) / abs(stats.mean) * 100


# ──────────────────────────────────────────────
# 카테고리별 분석
# ──────────────────────────────────────────────

def _analyze_visitors(cur, df, gl="역대"):
    insights = []
    v = cur.get("총 관객수")
    if v:
        ins = _make_insight("관객", "results", "총 관객수", "총 관객수", v,
                            compute_stats(df, "총 관객수"), "명", priority=1, group_label=gl)
        if ins: insights.append(ins)

    v = cur.get("일평균 관객수")
    if v:
        ins = _make_insight("관객", "results", "일평균 관객수", "일평균 관객수", v,
                            compute_stats(df, "일평균 관객수"), "명", priority=2, group_label=gl)
        if ins: insights.append(ins)

    # 유료 비율
    paid = cur.get("유료 관객수")
    total = cur.get("총 관객수")
    if paid and total and total > 0 and "유료_비율" in df.columns:
        ratio = paid / total
        valid = df["유료_비율"].dropna()
        if len(valid) >= 3:
            avg_r = float(valid.mean())
            insights.append(Insight(
                category="관객", section="results", title="유료 관객 비율",
                text=f"유료 관객 비율은 {ratio*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%) 대비 {abs(ratio-avg_r)*100:.1f}%p {'높습니다' if ratio > avg_r else '낮습니다'}.",
                metric_name="유료 관객 비율", current_value=ratio, reference_avg=avg_r, priority=2,
            ))

    # 학생 관객 비율 (신규)
    student = cur.get("학생 관객수(만 24세 이하)")
    if student and total and total > 0:
        s_stats = compute_stats(df, "학생 관객수(만 24세 이하)")
        if s_stats and s_stats.count >= 3:
            ins = _make_insight("관객", "results", "학생 관객수", "학생 관객수", student,
                                s_stats, "명", priority=3, group_label=gl)
            if ins: insights.append(ins)

    # 예술인패스 (신규)
    artpass = cur.get("예술인패스 관객수")
    if artpass and artpass > 0:
        a_stats = compute_stats(df, "예술인패스 관객수")
        if a_stats and a_stats.count >= 3:
            ins = _make_insight("관객", "results", "예술인패스 관객", "예술인패스 관객수", artpass,
                                a_stats, "명", priority=3, group_label=gl)
            if ins: insights.append(ins)

    return insights


def _analyze_budget(cur, df, gl="역대"):
    insights = []
    v = cur.get("총 사용 예산")
    if v:
        ins = _make_insight("예산", "results", "총 사용 예산", "총 사용 예산", v,
                            compute_stats(df, "총 사용 예산"), "원", priority=2, group_label=gl)
        if ins: insights.append(ins)

    # 관객당 비용
    budget = cur.get("총 사용 예산")
    visitors = cur.get("총 관객수")
    if budget and visitors and visitors > 0 and "관객당_비용" in df.columns:
        cost = budget / visitors
        valid = df["관객당_비용"].dropna()
        if len(valid) >= 3:
            avg_c = float(valid.mean())
            diff = (cost - avg_c) / abs(avg_c) * 100
            rank = compute_rank(compute_stats(df, "관객당_비용"), cost, ascending=True) if compute_stats(df, "관객당_비용") else None
            insights.append(Insight(
                category="예산", section="results", title="관객당 비용",
                text=f"관객당 비용은 {format_number(cost, '원')}으로, {gl} 평균({format_number(avg_c, '원')}) 대비 {abs(diff):.1f}% {_direction_verb(diff)} ({_quality_word(diff, False)} 수준).",
                metric_name="관객당 비용", current_value=cost, reference_avg=avg_c, priority=1,
                rank=rank,
            ))

    # 예산 구조 분석 (신규: 전시비/부대비 비율)
    exh_budget = cur.get("전시 사용 예산")
    sup_budget = cur.get("부대 사용 예산")
    if exh_budget and budget and budget > 0:
        exh_ratio = exh_budget / budget
        if "전시 사용 예산" in df.columns and "총 사용 예산" in df.columns:
            df_temp = df.copy()
            with np.errstate(divide="ignore", invalid="ignore"):
                df_temp["_exh_ratio"] = np.where(
                    df_temp["총 사용 예산"] > 0,
                    df_temp["전시 사용 예산"] / df_temp["총 사용 예산"], np.nan)
            valid = df_temp["_exh_ratio"].dropna()
            if len(valid) >= 3:
                avg_r = float(valid.mean())
                insights.append(Insight(
                    category="예산", section="results", title="예산 구조",
                    text=f"전시비 비율은 {exh_ratio*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%)과 비교됩니다. {'전시 직접비에 집중 투자한' if exh_ratio > avg_r else '부대 사업에 상대적으로 많이 배분한'} 구조입니다.",
                    metric_name="전시비 비율", current_value=exh_ratio, reference_avg=avg_r, priority=3,
                ))

    # 수입/예산 비율
    revenue = cur.get("총수입")
    if budget and revenue and budget > 0 and "수입_예산_비율" in df.columns:
        ratio = revenue / budget
        valid = df["수입_예산_비율"].dropna()
        if len(valid) >= 3:
            avg_r = float(valid.mean())
            insights.append(Insight(
                category="예산", section="results", title="예산 회수율",
                text=f"예산 대비 수입 비율은 {ratio*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%)을 {'상회' if ratio > avg_r else '하회'}합니다.",
                metric_name="예산 회수율", current_value=ratio, reference_avg=avg_r, priority=1,
            ))

    return insights


def _analyze_programs(cur, df, gl="역대"):
    insights = []
    v = cur.get("프로그램 총 수")
    if v:
        ins = _make_insight("프로그램", "composition", "프로그램 수", "프로그램 수", v,
                            compute_stats(df, "프로그램 총 수"), "개", priority=2, group_label=gl)
        if ins: insights.append(ins)

    v = cur.get("프로그램 참여 인원")
    if v:
        ins = _make_insight("프로그램", "composition", "프로그램 참여 인원", "프로그램 참여 인원", v,
                            compute_stats(df, "프로그램 참여 인원"), "명", priority=2, group_label=gl)
        if ins: insights.append(ins)

    # 참여율
    participants = cur.get("프로그램 참여 인원")
    visitors = cur.get("총 관객수")
    if participants and visitors and visitors > 0 and "프로그램_참여율" in df.columns:
        rate = participants / visitors
        valid = df["프로그램_참여율"].dropna()
        if len(valid) >= 3:
            avg_r = float(valid.mean())
            insights.append(Insight(
                category="프로그램", section="composition", title="프로그램 참여율",
                text=f"프로그램 참여율(참여인원/총관객)은 {rate*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%) 대비 {abs(rate-avg_r)*100:.1f}%p {'높습니다' if rate > avg_r else '낮습니다'}.",
                metric_name="프로그램 참여율", current_value=rate, reference_avg=avg_r, priority=1,
            ))

    return insights


def _analyze_artworks(cur, df, gl="역대"):
    """작품 분석 — 총수 + 매체별 구성 (v3 신규)"""
    insights = []

    total = cur.get("출품 작품 수_총")
    if total:
        ins = _make_insight("작품", "composition", "출품 작품 수", "출품 작품 수", total,
                            compute_stats(df, "출품 작품 수_총"), "점", priority=2, group_label=gl)
        if ins: insights.append(ins)

    # 매체별 구성 비율 분석
    media_fields = [
        ("출품 작품 수_회화", "회화"), ("출품 작품 수_조각", "조각"),
        ("출품 작품 수_사진", "사진"), ("출품 작품 수_설치", "설치"),
        ("출품 작품 수_미디어", "미디어"), ("출품 작품 수_기타", "기타"),
    ]

    if total and total > 0:
        # 현재 전시의 매체 구성
        current_media = {}
        for field, label in media_fields:
            v = cur.get(field, 0) or 0
            if v > 0:
                current_media[label] = v

        if current_media:
            # 가장 큰 비중 매체 찾기
            dominant = max(current_media, key=current_media.get)
            dominant_pct = current_media[dominant] / total * 100

            # 레퍼런스 평균 매체 구성과 비교
            ref_avg_composition = {}
            for field, label in media_fields:
                if field in df.columns and "출품 작품 수_총" in df.columns:
                    with np.errstate(divide="ignore", invalid="ignore"):
                        ratios = np.where(df["출품 작품 수_총"] > 0,
                                          df[field] / df["출품 작품 수_총"], np.nan)
                    valid = pd.Series(ratios).dropna()
                    if len(valid) >= 3:
                        ref_avg_composition[label] = float(valid.mean()) * 100

            if ref_avg_composition:
                ref_dominant_pct = ref_avg_composition.get(dominant, 0)
                parts = [f"{label} {current_media[label]}점({current_media[label]/total*100:.0f}%)"
                         for label in ["회화", "조각", "사진", "설치", "미디어", "기타"]
                         if label in current_media]
                composition_str = ", ".join(parts)

                text = f"출품 작품의 매체 구성은 {composition_str}입니다. "
                if ref_dominant_pct > 0:
                    text += f"{dominant}의 비중({dominant_pct:.0f}%)은 {gl} 평균({ref_dominant_pct:.0f}%)과 비교하여 {'높은' if dominant_pct > ref_dominant_pct else '낮은'} 편입니다."

                insights.append(Insight(
                    category="작품", section="composition", title="매체별 작품 구성",
                    text=text, metric_name="매체별 작품 구성",
                    current_value=dominant_pct, reference_avg=ref_dominant_pct,
                    priority=2,
                ))

    return insights


def _analyze_promotion(cur, df, gl="역대"):
    insights = []
    v = cur.get("언론 보도 건수")
    if v:
        ins = _make_insight("홍보", "promotion", "언론 보도", "언론 보도 건수", v,
                            compute_stats(df, "언론 보도 건수"), "건", priority=2, group_label=gl)
        if ins: insights.append(ins)

    # 보도건당 관객
    press = cur.get("언론 보도 건수")
    visitors = cur.get("총 관객수")
    if press and visitors and press > 0 and "보도건당_관객" in df.columns:
        vpc = visitors / press
        valid = df["보도건당_관객"].dropna()
        if len(valid) >= 3:
            avg = float(valid.mean())
            diff = (vpc - avg) / abs(avg) * 100
            insights.append(Insight(
                category="홍보", section="promotion", title="보도건당 관객",
                text=f"보도 1건당 관객은 {format_number(vpc, '명')}으로, {gl} 평균({format_number(avg, '명')}) 대비 {abs(diff):.1f}% {_direction_verb(diff)}.",
                metric_name="보도건당 관객", current_value=vpc, reference_avg=avg, priority=1,
            ))

    v = cur.get("SNS 게시 건수")
    if v:
        ins = _make_insight("홍보", "promotion", "SNS 활동", "SNS 게시 건수", v,
                            compute_stats(df, "SNS 게시 건수"), "건", priority=3, group_label=gl)
        if ins: insights.append(ins)

    return insights


def _analyze_staff(cur, df, gl="역대"):
    """인력 효율 분석 (v3 신규)"""
    insights = []
    staff = cur.get("운영 인력_총")
    visitors = cur.get("총 관객수")

    if staff and visitors and staff > 0:
        v_per_staff = visitors / staff
        if "운영 인력_총" in df.columns and "총 관객수" in df.columns:
            with np.errstate(divide="ignore", invalid="ignore"):
                df_temp = df.copy()
                df_temp["_v_per_staff"] = np.where(
                    df_temp["운영 인력_총"] > 0,
                    df_temp["총 관객수"] / df_temp["운영 인력_총"], np.nan)
            valid = df_temp["_v_per_staff"].dropna()
            if len(valid) >= 3:
                avg = float(valid.mean())
                diff = (v_per_staff - avg) / abs(avg) * 100
                insights.append(Insight(
                    category="인력", section="composition", title="인력당 관객",
                    text=f"운영인력 1인당 관객은 {format_number(v_per_staff, '명')}으로, {gl} 평균({format_number(avg, '명')}) 대비 {abs(diff):.1f}% {_direction_verb(diff)}.",
                    metric_name="인력당 관객", current_value=v_per_staff, reference_avg=avg, priority=3,
                ))

    return insights


# ──────────────────────────────────────────────
# 교차 분석 (v2 이관 + 확장)
# ──────────────────────────────────────────────

def _analyze_cross(cur, df, gl="역대"):
    insights = []
    budget = cur.get("총 사용 예산")
    visitors = cur.get("총 관객수")
    revenue = cur.get("총수입")
    press = cur.get("언론 보도 건수")
    participants = cur.get("프로그램 참여 인원")

    b_stats = compute_stats(df, "총 사용 예산")
    v_stats = compute_stats(df, "총 관객수")
    b_diff = _diff_pct(budget, b_stats)
    v_diff = _diff_pct(visitors, v_stats)

    # 예산 vs 관객 효율
    if budget and visitors and visitors > 0 and b_diff is not None and v_diff is not None:
        cost = budget / visitors
        c_stats = compute_stats(df, "관객당_비용") if "관객당_비용" in df.columns else None
        if c_stats and c_stats.count >= 3:
            c_rank = compute_rank(c_stats, cost, ascending=True)
            if b_diff < -5 and v_diff > 5:
                insights.append(Insight(
                    category="교차분석", section="evaluation", title="예산 대비 관객 효율",
                    text=f"총 사용 예산은 {gl} 평균 대비 {abs(b_diff):.0f}% 낮았으나, 총 관객수는 오히려 {abs(v_diff):.0f}% 높아 관객당 비용 {format_number(cost, '원')}으로 매우 효율적인 운영을 보였습니다 ({c_stats.count}개 전시 중 {c_rank}위).",
                    metric_name="예산-관객 효율", current_value=cost, priority=1,
                ))
            elif b_diff > 10 and v_diff < -5:
                insights.append(Insight(
                    category="교차분석", section="evaluation", title="예산 대비 관객 효율",
                    text=f"총 사용 예산은 {gl} 평균 대비 {abs(b_diff):.0f}% 높았으나, 총 관객수는 {abs(v_diff):.0f}% 낮아 관객당 비용이 {format_number(cost, '원')}에 달했습니다. 향후 예산 효율 개선이 필요합니다.",
                    metric_name="예산-관객 비효율", current_value=cost, priority=1,
                ))

    # 홍보 vs 관객
    p_stats = compute_stats(df, "언론 보도 건수")
    p_diff = _diff_pct(press, p_stats)
    if press and visitors and p_diff is not None and v_diff is not None:
        if p_diff < -10 and v_diff > 5:
            insights.append(Insight(
                category="교차분석", section="evaluation", title="홍보 채널 효과",
                text=f"언론 보도는 {gl} 평균 대비 {abs(p_diff):.0f}% 적었으나 총 관객수는 {abs(v_diff):.0f}% 높아, 보도 외 채널(SNS, 구전 등)의 홍보 효과가 컸던 것으로 보입니다.",
                metric_name="보도-관객 관계", priority=2,
            ))

    # 수입 vs 예산 회수
    if revenue and budget and budget > 0:
        recovery = revenue / budget
        r_series = df["수입_예산_비율"].dropna() if "수입_예산_비율" in df.columns else pd.Series()
        if len(r_series) >= 3:
            avg_r = float(r_series.mean())
            if recovery > 1.0 and avg_r < 1.0:
                insights.append(Insight(
                    category="교차분석", section="evaluation", title="예산 회수율 초과",
                    text=f"총수입({format_number(revenue, '원')})이 총예산({format_number(budget, '원')})을 초과하여 예산 회수율 {recovery*100:.1f}%를 달성했습니다 ({gl} 평균 {avg_r*100:.1f}%).",
                    metric_name="예산 회수율", current_value=recovery, reference_avg=avg_r, priority=1,
                ))

    return insights


# ──────────────────────────────────────────────
# 유사 전시 비교 (v2 이관)
# ──────────────────────────────────────────────

COMPARISON_FIELDS = [
    ("총 관객수", "명"), ("일평균 관객수", "명"),
    ("총 사용 예산", "원"), ("프로그램 총 수", "개"),
    ("언론 보도 건수", "건"), ("출품 작품 수_총", "점"),
]

def _build_similar(cur, df, top_n=5):
    sim_df = get_similar_exhibitions(df, cur, top_n=top_n)
    if sim_df.empty:
        return [], None

    rows = []
    for _, row in sim_df.iterrows():
        metrics = {}
        for f, u in COMPARISON_FIELDS:
            v = row.get(f)
            if pd.notna(v): metrics[f] = v
        rows.append(SimilarExhibitionRow(
            title=row["전시 제목"], similarity=row.get("_similarity_score", 0), metrics=metrics))

    table_data = {"전시명": [cur.get("전시 제목", "현재 전시")]}
    for f, u in COMPARISON_FIELDS:
        v = cur.get(f)
        table_data[f] = [format_number(v, u) if v else "—"]
    for sim in rows:
        table_data["전시명"].append(sim.title)
        for f, u in COMPARISON_FIELDS:
            v = sim.metrics.get(f)
            table_data[f].append(format_number(v, u) if v else "—")

    return rows, pd.DataFrame(table_data)


# ──────────────────────────────────────────────
# 평가 문장 자동 초안 생성 (v3 신규)
# ──────────────────────────────────────────────

def _generate_eval_drafts(insights: list[Insight], cur: dict) -> list[EvalDraft]:
    """인사이트에서 긍정/부정/개선 평가 초안을 자동 생성"""
    drafts = []

    for ins in insights:
        if ins.current_value is None or ins.reference_avg is None:
            continue
        if ins.reference_avg == 0:
            continue

        diff = (ins.current_value - ins.reference_avg) / abs(ins.reference_avg) * 100

        # ── 긍정 평가 도출 ──
        if diff > 15:
            if "관객" in ins.metric_name:
                drafts.append(EvalDraft("positive",
                    f"{ins.metric_name}이 역대 평균 대비 {abs(diff):.0f}% 높은 우수한 성과를 기록했습니다.",
                    ins.metric_name))
            elif "비용" in ins.metric_name and diff < 0:
                drafts.append(EvalDraft("positive",
                    f"관객당 비용이 역대 평균보다 낮아 효율적인 예산 운영이 이루어졌습니다.",
                    ins.metric_name))
            elif "참여" in ins.metric_name:
                drafts.append(EvalDraft("positive",
                    f"프로그램 참여율이 역대 평균을 상회하여 관객 경험 강화에 효과적으로 기여했습니다.",
                    ins.metric_name))
            elif "회수" in ins.metric_name:
                drafts.append(EvalDraft("positive",
                    f"예산 회수율이 {ins.current_value*100:.1f}%로, 수입 확보 면에서 양호한 결과를 보였습니다.",
                    ins.metric_name))
            else:
                drafts.append(EvalDraft("positive",
                    f"{ins.metric_name}이 역대 평균 대비 우수한 수준입니다.",
                    ins.metric_name))

        # 관객당 비용이 낮은 것은 긍정
        if "비용" in ins.metric_name and diff < -10:
            drafts.append(EvalDraft("positive",
                f"관객당 비용이 역대 평균보다 {abs(diff):.0f}% 낮아 효율적인 예산 운영이 이루어졌습니다.",
                ins.metric_name))

        # ── 부정 평가 도출 ──
        if diff < -15:
            if "관객" in ins.metric_name and "비용" not in ins.metric_name:
                drafts.append(EvalDraft("negative",
                    f"{ins.metric_name}이 역대 평균 대비 {abs(diff):.0f}% 낮은 수치를 기록했습니다.",
                    ins.metric_name))
            elif "참여" in ins.metric_name:
                drafts.append(EvalDraft("negative",
                    f"프로그램 참여율이 역대 평균에 미치지 못하여, 프로그램 기획 및 홍보 전략 재검토가 필요합니다.",
                    ins.metric_name))

        # 관객당 비용이 높은 것은 부정
        if "비용" in ins.metric_name and diff > 15:
            drafts.append(EvalDraft("negative",
                f"관객당 비용이 역대 평균보다 {abs(diff):.0f}% 높아, 예산 효율성 면에서 개선이 필요합니다.",
                ins.metric_name))

        # ── 개선 방안 도출 ──
        if diff < -20:
            if "관객" in ins.metric_name and "비용" not in ins.metric_name:
                drafts.append(EvalDraft("improvement",
                    f"관객 유치 확대를 위한 다채널 홍보 전략 및 타깃 마케팅 강화가 필요합니다.",
                    ins.metric_name))
            elif "참여" in ins.metric_name:
                drafts.append(EvalDraft("improvement",
                    f"프로그램 참여율 제고를 위해 사전 예약 시스템 도입이나 참여형 프로그램 확대를 검토할 수 있습니다.",
                    ins.metric_name))
            elif "보도" in ins.metric_name:
                drafts.append(EvalDraft("improvement",
                    f"언론 노출 확대를 위해 보도자료 배포 시점 및 매체 타깃팅 전략을 재검토할 필요가 있습니다.",
                    ins.metric_name))

    # 중복 제거 (같은 eval_type + source_metric)
    seen = set()
    unique = []
    for d in drafts:
        key = (d.eval_type, d.source_metric)
        if key not in seen:
            seen.add(key)
            unique.append(d)

    return unique


# ──────────────────────────────────────────────
# 메인 분석 함수
# ──────────────────────────────────────────────

CATEGORY_ORDER = ["관객", "예산", "프로그램", "작품", "홍보", "인력", "교차분석"]
CATEGORY_LABELS = {
    "관객": "관객 분석", "예산": "예산 효율", "프로그램": "프로그램 밀도",
    "작품": "작품 규모", "홍보": "홍보 효과", "인력": "인력 효율",
    "교차분석": "교차 분석",
}
CATEGORY_ICONS = {
    "관객": "👥", "예산": "💰", "프로그램": "🎯",
    "작품": "🎨", "홍보": "📢", "인력": "👷",
    "교차분석": "🔗",
}

# 보고서 섹션별 라벨
SECTION_LABELS = {
    "results": "IV. 전시 결과",
    "composition": "III. 전시 구성",
    "promotion": "V. 홍보",
    "evaluation": "VI. 평가",
}


def generate_all_insights(current_data, ref_df, exhibition_type=None) -> AnalysisResult:
    df_full = compute_derived_metrics(exclude_type_zero(ref_df))
    df_typed = filter_by_type(df_full, exhibition_type)
    is_filtered = len(df_typed) < len(df_full)
    gl = f"동일 유형({get_type_label(exhibition_type)})" if is_filtered else "역대"

    all_insights = []
    all_insights.extend(_analyze_visitors(current_data, df_typed, gl))
    all_insights.extend(_analyze_budget(current_data, df_typed, gl))
    all_insights.extend(_analyze_programs(current_data, df_typed, gl))
    all_insights.extend(_analyze_artworks(current_data, df_typed, gl))
    all_insights.extend(_analyze_promotion(current_data, df_typed, gl))
    all_insights.extend(_analyze_staff(current_data, df_typed, gl))
    all_insights.extend(_analyze_cross(current_data, df_typed, gl))

    # 평가 초안 생성
    eval_drafts = _generate_eval_drafts(all_insights, current_data)

    # 유사 전시
    sim_rows, sim_table = _build_similar(current_data, df_full)

    all_insights.sort(key=lambda x: x.priority)

    return AnalysisResult(
        insights=all_insights,
        eval_drafts=eval_drafts,
        similar_exhibitions=sim_rows,
        similar_comparison_table=sim_table,
    )


def get_insights_by_category(result):
    grouped = {}
    for ins in result.insights:
        grouped.setdefault(ins.category, []).append(ins)
    return grouped


def get_insights_by_section(result):
    """보고서 섹션별로 인사이트 그룹핑"""
    grouped = {}
    for ins in result.insights:
        grouped.setdefault(ins.section, []).append(ins)
    return grouped
