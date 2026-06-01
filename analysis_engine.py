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
    unit: str = ""          # 근거 표시용 단위 ("원", "명", "건", "개", "%")
    is_ratio: bool = False  # True면 current/reference가 0~1 분수 → 표시 시 ×100 %
    # 비교군 중 최근 전시 [(제목, 값), ...] 최근순 (직전 전시·比 서술용)
    recent_compares: list = field(default_factory=list)


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
    start: Optional[str] = None  # 전시 시작일(YYYY-MM-DD) — 시간순 정렬용


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
    return "높음" if diff_pct > 0 else "낮음"

def _postposition(word, pair=("은", "는")):
    if not word:
        return pair[1]
    last_char = word.rstrip("0123456789,. 원명건개점%")
    if not last_char:
        # 숫자+단위만 남은 경우: 마지막 한글(단위) 글자의 받침으로 판정
        # (예: "32건" → '건'의 받침 → "으로")
        for c in reversed(word):
            if 0xAC00 <= ord(c) <= 0xD7A3:
                return pair[0] if (ord(c) - 0xAC00) % 28 != 0 else pair[1]
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
# 서술용 숫자·순위 헬퍼
# ──────────────────────────────────────────────

def fmt_narrative(v, unit):
    """서술(인사이트 텍스트)용 숫자.

    - 만(명)·억(원) 미만은 정확히 표기 (예: 9,413명, 32건).
    - 만 명·억 원을 넘으면 차트와 동일하게 백 명/백만 원 단위로 내림하여
      소수 둘째 자리까지 표기 (예: 1.52만 명, 2.10억 원).
    - 내림으로 절사가 발생하면 앞에 '약'을 붙임 (예: 약 0.86만 명).
    """
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if unit == "명" and abs(v) >= 10_000:
        floored = (int(v) // 100) * 100            # 백 명 단위 내림
        approx = int(round(v)) != floored
        return f"{'약 ' if approx else ''}{floored / 10_000:.2f}만 명"
    if unit == "원" and abs(v) >= 100_000_000:
        floored = (int(v) // 1_000_000) * 1_000_000  # 백만 원 단위 내림
        approx = int(round(v)) != floored
        return f"{'약 ' if approx else ''}{floored / 100_000_000:.2f}억 원"
    return format_number(v, unit)


def position_label(rank, total):
    """순위 → '상위 X%' / '하위 X%' (50 기준 더 작은 숫자 쪽). 0% 미발생."""
    if not rank or not total or total < 1:
        return None
    top = rank / total * 100
    if top <= 50:
        return f"상위 {top:.0f}%"
    return f"하위 {(total - rank + 1) / total * 100:.0f}%"


def is_notable_rank(rank, total):
    """상위 34% 또는 하위 34%에 속하면 True (순위 서술 노출 조건)."""
    if not rank or not total or total < 1:
        return False
    return (rank / total <= 0.34) or ((total - rank + 1) / total <= 0.34)


def _main_title(t):
    """전시 제목에서 주 제목만 추출(부제목 제거). 길이 제한 없음.

    ':'(전각 '：' 포함)를 주/부 제목 경계로 보고 그 앞부분만 사용.
    제목 괄호·따옴표(《》「」『』""'')는 정리하여 잘림 없이 깔끔하게 표기.
    """
    t = (t or "").strip()
    for sep in (":", "："):
        if sep in t:
            t = t.split(sep)[0]
            break
    return t.strip().strip("《》「」『』\"'“”‘’ ").strip()


def _recent_compares(df, field, k=2):
    """비교군에서 가장 최근 k개 전시의 (제목, 값)을 최근순으로 반환."""
    if df is None or field is None:
        return []
    if (field not in df.columns or "전시 제목" not in df.columns
            or "전시 기간_시작" not in df.columns):
        return []

    def _parse_d(x):
        s = str(x)[:10].replace(".", "-").replace("/", "-")
        return pd.to_datetime(s, errors="coerce")

    sub = df[["전시 제목", "전시 기간_시작", field]].copy()
    sub = sub[sub[field].notna()]
    sub["_d"] = sub["전시 기간_시작"].map(_parse_d)
    sub = sub[sub["_d"].notna()].sort_values("_d", ascending=False)
    out = []
    for _, r in sub.head(k).iterrows():
        out.append((str(r["전시 제목"]).strip(), float(r[field])))
    return out


# ──────────────────────────────────────────────
# 기본 인사이트 생성
# ──────────────────────────────────────────────

def _make_insight(
    category, section, title, metric_name,
    current_val, stats, unit="",
    higher_is_better=True, priority=None, group_label="역대", df=None
) -> Optional[Insight]:
    if current_val is None or stats is None or stats.count < 3:
        return None
    avg = stats.mean
    if avg == 0:
        return None
    diff_pct = (current_val - avg) / abs(avg) * 100
    pct = compute_percentile(stats, current_val)
    rank = compute_rank(stats, current_val, ascending=not higher_is_better)
    total = stats.count
    current_fmt = fmt_narrative(current_val, unit)
    avg_fmt = fmt_narrative(avg, unit)
    pp = _postposition(metric_name, ("은", "는"))
    pp_ro = _postposition(current_fmt, ("으로", "로"))

    # 비교군 중 최근 전시 2개 (stats.field_name = 해당 지표 컬럼)
    recent = _recent_compares(df, getattr(stats, "field_name", None), 2)

    # 말미 괄호: 순위(상·하위 34% 한정) + 比(최근 2개 전시 비교)
    tail = ""
    parts = []
    if is_notable_rank(rank, total):
        parts.append(f"(기존 전시 중 {rank}위)")
    if recent:
        cmp_str = ", ".join(
            (f"《{_main_title(t)}》 {fmt_narrative(val, unit)}"
             if _main_title(t) else fmt_narrative(val, unit))
            for t, val in recent
        )
        parts.append(f"(比 {cmp_str})")
    if parts:
        tail = " " + " ".join(parts)

    text = (
        f"이번 전시의 {metric_name}{pp} {current_fmt}{pp_ro}, "
        f"{group_label} 평균({avg_fmt}) 대비 {abs(diff_pct):.1f}% "
        f"{_direction_verb(diff_pct)}{tail}."
    )
    # priority가 명시되지 않으면 diff_pct 기반 자동 산출
    if priority is None:
        priority = _compute_salience(diff_pct, rank, stats.count)
    return Insight(
        category=category, section=section, title=title, text=text,
        metric_name=metric_name, current_value=current_val,
        reference_avg=avg, percentile=pct, rank=rank,
        total_count=stats.count, priority=priority,
        unit=unit, recent_compares=recent,
    )


def _diff_pct(val, stats):
    if val is None or stats is None or stats.mean == 0:
        return None
    return (val - stats.mean) / abs(stats.mean) * 100


def _compute_salience(diff_pct, rank=None, total=None):
    """인사이트의 현저성(salience) 점수를 계산하여 priority 결정.

    기준:
    - diff_pct의 절댓값이 클수록 현저함 (평균에서 크게 벗어난 지표)
    - 순위가 극단(1~2위 또는 하위 1~2위)이면 추가 가중
    - 결과: 1(핵심 — 자동 체크), 2(보통 — 자동 체크), 3(참고 — 체크 해제)

    Returns:
        priority (int): 1, 2, or 3
    """
    if diff_pct is None:
        return 3

    abs_diff = abs(diff_pct)
    score = 0

    # 차이 폭 기반 점수 (0~50)
    if abs_diff >= 50:
        score += 50
    elif abs_diff >= 30:
        score += 40
    elif abs_diff >= 20:
        score += 30
    elif abs_diff >= 15:
        score += 25
    elif abs_diff >= 10:
        score += 20
    else:
        score += 10

    # 순위 극단성 가산 (0~20)
    if rank is not None and total is not None and total >= 5:
        if rank <= 2 or rank >= total - 1:
            score += 20
        elif rank <= 3 or rank >= total - 2:
            score += 10

    # 점수 → priority 매핑
    if score >= 40:
        return 1  # 핵심: 확실히 부각되는 차이
    elif score >= 25:
        return 2  # 보통: 유의미한 차이
    else:
        return 3  # 참고: 평균 근처


# ──────────────────────────────────────────────
# 카테고리별 분석
# ──────────────────────────────────────────────

def _analyze_visitors(cur, df, gl="역대"):
    insights = []
    v = cur.get("총 관객수")
    if v:
        ins = _make_insight("관객", "results", "총 관객수", "총 관객수", v,
                            compute_stats(df, "총 관객수"), "명", group_label=gl, df=df)
        if ins: insights.append(ins)

    v = cur.get("일평균 관객수")
    if v:
        ins = _make_insight("관객", "results", "일평균 관객수", "일평균 관객수", v,
                            compute_stats(df, "일평균 관객수"), "명", group_label=gl, df=df)
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
                text=f"유료 관객 비율은 {ratio*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%) 대비 {abs(ratio-avg_r)*100:.1f}%p {'높음' if ratio > avg_r else '낮음'}.",
                metric_name="유료 관객 비율", current_value=ratio, reference_avg=avg_r,
                priority=_compute_salience((ratio - avg_r) / abs(avg_r) * 100 if avg_r else None),
                is_ratio=True,
            ))

    # 학생 관객 비율 (신규)
    student = cur.get("학생 관객수(만 24세 이하)")
    if student and total and total > 0:
        s_stats = compute_stats(df, "학생 관객수(만 24세 이하)")
        if s_stats and s_stats.count >= 3:
            ins = _make_insight("관객", "results", "학생 관객수", "학생 관객수", student,
                                s_stats, "명", group_label=gl, df=df)
            if ins: insights.append(ins)

    # 예술인패스 (신규)
    artpass = cur.get("예술인패스 관객수")
    if artpass and artpass > 0:
        a_stats = compute_stats(df, "예술인패스 관객수")
        if a_stats and a_stats.count >= 3:
            ins = _make_insight("관객", "results", "예술인패스 관객", "예술인패스 관객수", artpass,
                                a_stats, "명", group_label=gl, df=df)
            if ins: insights.append(ins)

    return insights


def _analyze_budget(cur, df, gl="역대"):
    insights = []
    v = cur.get("총 사용 예산")
    if v:
        ins = _make_insight("예산", "results", "총 사용 예산", "총 사용 예산", v,
                            compute_stats(df, "총 사용 예산"), "원", group_label=gl, df=df)
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
                metric_name="관객당 비용", current_value=cost, reference_avg=avg_c,
                priority=_compute_salience(diff, rank),
                rank=rank, total_count=len(valid), unit="원",
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
                    text=f"전시비 비율은 {exh_ratio*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%)과 비교됨. {'전시 직접비에 집중 투자한' if exh_ratio > avg_r else '부대 사업에 상대적으로 많이 배분한'} 구조임.",
                    metric_name="전시비 비율", current_value=exh_ratio, reference_avg=avg_r,
                    priority=_compute_salience((exh_ratio - avg_r) / abs(avg_r) * 100 if avg_r else None),
                    is_ratio=True,
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
                text=f"예산 대비 수입 비율은 {ratio*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%)을 {'상회함' if ratio > avg_r else '하회함'}.",
                metric_name="예산 회수율", current_value=ratio, reference_avg=avg_r,
                priority=_compute_salience((ratio - avg_r) / abs(avg_r) * 100 if avg_r else None),
                is_ratio=True,
            ))

    return insights


def _analyze_programs(cur, df, gl="역대"):
    insights = []
    v = cur.get("프로그램 총 수")
    if v:
        ins = _make_insight("프로그램", "composition", "프로그램 수", "프로그램 수", v,
                            compute_stats(df, "프로그램 총 수"), "개", group_label=gl, df=df)
        if ins: insights.append(ins)

    v = cur.get("프로그램 참여 인원")
    if v:
        ins = _make_insight("프로그램", "composition", "프로그램 참여 인원", "프로그램 참여 인원", v,
                            compute_stats(df, "프로그램 참여 인원"), "명", group_label=gl, df=df)
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
                text=f"프로그램 참여율(참여인원/총관객)은 {rate*100:.1f}%로, {gl} 평균({avg_r*100:.1f}%) 대비 {abs(rate-avg_r)*100:.1f}%p {'높음' if rate > avg_r else '낮음'}.",
                metric_name="프로그램 참여율", current_value=rate, reference_avg=avg_r,
                priority=_compute_salience((rate - avg_r) / abs(avg_r) * 100 if avg_r else None),
                is_ratio=True,
            ))

    return insights


def _analyze_artworks(cur, df, gl="역대"):
    """작품 분석 — 총수 + 매체별 구성 (v3 신규)"""
    insights = []

    total = cur.get("출품 작품 수_총")
    if total:
        ins = _make_insight("작품", "composition", "출품 작품 수", "출품 작품 수", total,
                            compute_stats(df, "출품 작품 수_총"), "점", group_label=gl, df=df)
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

                text = f"출품 작품의 매체 구성은 {composition_str}임. "
                if ref_dominant_pct > 0:
                    text += f"{dominant}의 비중({dominant_pct:.0f}%)은 {gl} 평균({ref_dominant_pct:.0f}%)과 비교하여 {'높은' if dominant_pct > ref_dominant_pct else '낮은'} 편임."

                media_diff = (dominant_pct - ref_dominant_pct) / abs(ref_dominant_pct) * 100 if ref_dominant_pct else None
                insights.append(Insight(
                    category="작품", section="composition", title="매체별 작품 구성",
                    text=text, metric_name="매체별 작품 구성",
                    current_value=dominant_pct, reference_avg=ref_dominant_pct,
                    priority=_compute_salience(media_diff),
                    unit="%",
                ))

    return insights


def _analyze_promotion(cur, df, gl="역대"):
    insights = []
    v = cur.get("언론 보도 건수")
    if v:
        ins = _make_insight("홍보", "promotion", "언론 보도", "언론 보도 건수", v,
                            compute_stats(df, "언론 보도 건수"), "건", group_label=gl, df=df)
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
                metric_name="보도건당 관객", current_value=vpc, reference_avg=avg,
                priority=_compute_salience(diff), total_count=len(valid), unit="명",
            ))

    v = cur.get("SNS 게시 건수")
    if v:
        ins = _make_insight("홍보", "promotion", "SNS 활동", "SNS 게시 건수", v,
                            compute_stats(df, "SNS 게시 건수"), "건", group_label=gl, df=df)
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
                    metric_name="인력당 관객", current_value=v_per_staff, reference_avg=avg,
                    priority=_compute_salience(diff), total_count=len(valid), unit="명",
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
                    text=f"총 사용 예산은 {gl} 평균 대비 {abs(b_diff):.0f}% 낮았으나, 총 관객수는 오히려 {abs(v_diff):.0f}% 높아 관객당 비용 {format_number(cost, '원')}으로 매우 효율적인 운영을 보임 (기존 전시 중 {c_rank}위).",
                    metric_name="관객당 비용", current_value=cost, reference_avg=c_stats.mean,
                    rank=c_rank, total_count=c_stats.count,
                    priority=1, unit="원",  # 교차분석 핵심: 항상 우선
                ))
            elif b_diff > 10 and v_diff < -5:
                insights.append(Insight(
                    category="교차분석", section="evaluation", title="예산 대비 관객 효율",
                    text=f"총 사용 예산은 {gl} 평균 대비 {abs(b_diff):.0f}% 높았으나, 총 관객수는 {abs(v_diff):.0f}% 낮아 관객당 비용이 {format_number(cost, '원')}에 달함. 향후 예산 효율 개선이 필요함.",
                    metric_name="관객당 비용", current_value=cost, reference_avg=c_stats.mean,
                    rank=c_rank, total_count=c_stats.count,
                    priority=1, unit="원",  # 교차분석 핵심: 항상 우선
                ))

    # 홍보 vs 관객
    p_stats = compute_stats(df, "언론 보도 건수")
    p_diff = _diff_pct(press, p_stats)
    if press and visitors and p_diff is not None and v_diff is not None:
        if p_diff < -10 and v_diff > 5:
            insights.append(Insight(
                category="교차분석", section="evaluation", title="홍보 채널 효과",
                text=f"언론 보도는 {gl} 평균 대비 {abs(p_diff):.0f}% 적었으나 총 관객수는 {abs(v_diff):.0f}% 높아, 보도 외 채널(SNS, 구전 등)의 홍보 효과가 컸던 것으로 보임.",
                metric_name="보도-관객 관계",
                priority=1,  # 교차분석: 항상 우선
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
                    text=f"총수입({format_number(revenue, '원')})이 총예산({format_number(budget, '원')})을 초과하여 예산 회수율 {recovery*100:.1f}%를 달성함 ({gl} 평균 {avg_r*100:.1f}%).",
                    metric_name="예산 회수율", current_value=recovery, reference_avg=avg_r,
                    priority=1, is_ratio=True,  # 교차분석: 예산 초과 회수는 항상 핵심
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
        _start = row.get("전시 기간_시작")
        _start = str(_start)[:10].replace(".", "-") if pd.notna(_start) else None
        rows.append(SimilarExhibitionRow(
            title=row["전시 제목"], similarity=row.get("_similarity_score", 0),
            metrics=metrics, start=_start))

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
                    f"{ins.metric_name}이 역대 평균 대비 {abs(diff):.0f}% 높은 우수한 성과를 기록함.",
                    ins.metric_name))
            elif "비용" in ins.metric_name and diff < 0:
                drafts.append(EvalDraft("positive",
                    f"관객당 비용이 역대 평균보다 낮아 효율적인 예산 운영이 이루어짐.",
                    ins.metric_name))
            elif "참여" in ins.metric_name:
                drafts.append(EvalDraft("positive",
                    f"프로그램 참여율이 역대 평균을 상회하여 관객 경험 강화에 효과적으로 기여함.",
                    ins.metric_name))
            elif "회수" in ins.metric_name:
                drafts.append(EvalDraft("positive",
                    f"예산 회수율이 {ins.current_value*100:.1f}%로, 수입 확보 면에서 양호한 결과를 보임.",
                    ins.metric_name))
            else:
                drafts.append(EvalDraft("positive",
                    f"{ins.metric_name}이 역대 평균 대비 우수한 수준임.",
                    ins.metric_name))

        # 관객당 비용이 낮은 것은 긍정
        if "비용" in ins.metric_name and diff < -10:
            drafts.append(EvalDraft("positive",
                f"관객당 비용이 역대 평균보다 {abs(diff):.0f}% 낮아 효율적인 예산 운영이 이루어짐.",
                ins.metric_name))

        # ── 부정 평가 도출 ──
        if diff < -15:
            if "관객" in ins.metric_name and "비용" not in ins.metric_name:
                drafts.append(EvalDraft("negative",
                    f"{ins.metric_name}이 역대 평균 대비 {abs(diff):.0f}% 낮은 수치를 기록함.",
                    ins.metric_name))
            elif "참여" in ins.metric_name:
                drafts.append(EvalDraft("negative",
                    f"프로그램 참여율이 역대 평균에 미치지 못하여, 프로그램 기획 및 홍보 전략 재검토가 필요함.",
                    ins.metric_name))

        # 관객당 비용이 높은 것은 부정
        if "비용" in ins.metric_name and diff > 15:
            drafts.append(EvalDraft("negative",
                f"관객당 비용이 역대 평균보다 {abs(diff):.0f}% 높아, 예산 효율성 면에서 개선이 필요함.",
                ins.metric_name))

        # ── 개선 방안 도출 ──
        if diff < -20:
            if "관객" in ins.metric_name and "비용" not in ins.metric_name:
                drafts.append(EvalDraft("improvement",
                    f"관객 유치 확대를 위한 다채널 홍보 전략 및 타깃 마케팅 강화가 필요함.",
                    ins.metric_name))
            elif "참여" in ins.metric_name:
                drafts.append(EvalDraft("improvement",
                    f"프로그램 참여율 제고를 위해 사전 예약 시스템 도입이나 참여형 프로그램 확대를 검토할 수 있음.",
                    ins.metric_name))
            elif "보도" in ins.metric_name:
                drafts.append(EvalDraft("improvement",
                    f"언론 노출 확대를 위해 보도자료 배포 시점 및 매체 타깃팅 전략을 재검토할 필요가 있음.",
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
    "evaluation": "VI. Executive Summary",
}


def generate_all_insights(current_data, ref_df, exhibition_type=None) -> AnalysisResult:
    df_full = compute_derived_metrics(exclude_type_zero(ref_df))
    df_typed = filter_by_type(df_full, exhibition_type)
    is_filtered = len(df_typed) < len(df_full)
    # 보고서 자연어 표기: "기존 기획전" / "기존 특별전" / "기존 전시" / "역대 전시"
    gl = get_type_label(exhibition_type) if is_filtered else "역대 전시"

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

    # 보고서 관례 순서 유지 (관객→예산→프로그램→작품→홍보→인력→교차분석)
    # priority 정렬이 아닌, 분석 함수 호출 순서 그대로 보존

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


# ──────────────────────────────────────────────
# 핵심 수치 종합표 (VI. Executive Summary 상단)
# ──────────────────────────────────────────────

def _fmt_summary_value(v, unit: str) -> str:
    """종합표용 숫자 포매팅. 평가어 없이 사실만."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if unit == "원":
        v = int(v)
        if v >= 100_000_000:
            eok = v // 100_000_000
            man = (v % 100_000_000) // 10_000
            return f"약 {eok}억 {man:,}만 원" if man > 0 else f"약 {eok}억 원"
        if v >= 10_000_000:
            return f"약 {v // 10_000:,}만 원"
        return f"{v:,}원"
    return f"{v:,.0f}{unit}"


def compute_summary_metrics(
    analysis_data: dict,
    ref_df: pd.DataFrame,
    exhibition_type=None,
) -> list:
    """VI. Executive Summary 상단 핵심 수치 종합표 데이터 생성.

    6개 지표(총 관객 수, 일평균 관객, 총 사용 예산, 관객당 비용,
    언론 보도 건수, 프로그램 참여 인원)에 대해
    본 전시 수치 + 비교 기준 평균 + 차이를 사실 기반으로 산출.
    평가어·해석 없이 디렉터의 사실 판독을 위한 데이터만 제공.

    Returns:
        list of dict: [
            {
                "label": str,
                "current_fmt": str,           # "15,200명"
                "reference_label": str,       # "기존 기획전" 등
                "reference_avg_fmt": str,     # "12,500명"
                "diff_fmt": str,              # "+21.6%" 또는 "—"
            }, ...
        ]
        비교 평균이 없는 지표는 결과에서 제외됨 (사실 결여 노출 방지).
    """
    df_full = compute_derived_metrics(exclude_type_zero(ref_df))
    df_typed = filter_by_type(df_full, exhibition_type)
    is_filtered = len(df_typed) < len(df_full)
    reference_label = get_type_label(exhibition_type) if is_filtered else "역대 전시"

    # (라벨, analysis_data 키, ref_df 컬럼, 단위)
    # ref_df 컬럼이 None인 경우 파생 계산 사용
    metric_defs = [
        ("총 관객 수",        "총 관객수",         "총 관객수",         "명"),
        ("일평균 관객",       "일평균 관객수",      None,              "명"),
        ("총 사용 예산",      "총 사용 예산",       "총 사용 예산",      "원"),
        ("관객당 비용",       None,               "관객당_비용",       "원"),
        ("언론 보도 건수",    "언론 보도 건수",     "언론 보도 건수",    "건"),
        ("프로그램 참여 인원", "프로그램 참여 인원", "프로그램 참여 인원", "명"),
    ]

    results = []
    for label, ad_key, ref_col, unit in metric_defs:
        # 본 전시 값
        if label == "관객당 비용":
            budget = analysis_data.get("총 사용 예산")
            visitors = analysis_data.get("총 관객수")
            current = (budget / visitors) if (budget and visitors and visitors > 0) else None
        else:
            current = analysis_data.get(ad_key) if ad_key else None

        if current is None or (isinstance(current, float) and pd.isna(current)):
            continue

        # 비교 평균
        ref_avg = None
        if ref_col and ref_col in df_typed.columns:
            series = pd.to_numeric(df_typed[ref_col], errors="coerce").dropna()
            if len(series) >= 2:
                ref_avg = float(series.mean())
        elif label == "일평균 관객":
            # 파생 계산: 총 관객수 ÷ 전시 일수
            if "총 관객수" in df_typed.columns and "전시 일수" in df_typed.columns:
                v_series = pd.to_numeric(df_typed["총 관객수"], errors="coerce")
                d_series = pd.to_numeric(df_typed["전시 일수"], errors="coerce")
                with np.errstate(divide="ignore", invalid="ignore"):
                    daily = (v_series / d_series).replace([np.inf, -np.inf], np.nan).dropna()
                if len(daily) >= 2:
                    ref_avg = float(daily.mean())

        # 차이 (사실 기반: 부호와 % 만, 평가어 없음)
        if ref_avg is not None and ref_avg > 0:
            diff_pct = ((current - ref_avg) / ref_avg) * 100
            sign = "+" if diff_pct >= 0 else ""
            diff_fmt = f"{sign}{diff_pct:.1f}%"
        else:
            diff_fmt = "—"

        results.append({
            "label": label,
            "current": current,
            "current_fmt": _fmt_summary_value(current, unit),
            "reference_label": reference_label,
            "reference_avg": ref_avg,
            "reference_avg_fmt": _fmt_summary_value(ref_avg, unit),
            "diff_fmt": diff_fmt,
        })

    return results
