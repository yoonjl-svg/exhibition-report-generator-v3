"""
차트 자동 생성 모듈
- 관객 구성 파이차트 (입장권별)
- 유형별 관객 구성 파이차트
- 주별 관객 수 바 차트
- 예산 계획 대비 집행 비교 차트
"""

import matplotlib
matplotlib.use('Agg')  # GUI 없이 사용
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import tempfile

# ──────────────────────────────────────────────
# 한글 폰트 설정
# ──────────────────────────────────────────────

def setup_korean_font():
    """한글 폰트 설정 - Noto Sans CJK 우선, 환경에 따라 자동 탐색"""
    font_candidates = [
        # Noto Sans CJK (우선)
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf',
        '/usr/share/fonts/noto-cjk/NotoSansCJKkr-Regular.otf',
        # macOS
        '/System/Library/Fonts/Supplemental/NotoSansCJKkr-Regular.otf',
        '/Library/Fonts/NotoSansCJKkr-Regular.otf',
        # Windows
        'C:/Windows/Fonts/NotoSansCJKkr-Regular.otf',
        # Fallback: Nanum Gothic
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
        # Fallback: 맑은 고딕 (Windows)
        'C:/Windows/Fonts/malgun.ttf',
        # Fallback: Apple Gothic
        '/System/Library/Fonts/AppleGothic.ttf',
    ]

    for font_path in font_candidates:
        if os.path.exists(font_path):
            return fm.FontProperties(fname=font_path)

    # matplotlib font_manager에서 Noto Sans CJK 탐색
    for font in fm.fontManager.ttflist:
        if 'Noto Sans CJK' in font.name or 'NotoSansCJK' in font.name:
            return fm.FontProperties(fname=font.fname)

    # 폰트를 찾지 못한 경우 기본 설정
    plt.rcParams['font.family'] = 'DejaVu Sans'
    return None


def get_font_prop():
    """폰트 속성 반환"""
    prop = setup_korean_font()
    return prop


# ──────────────────────────────────────────────
# 미술관 톤 팔레트 (v5.3.60) — 보고서 차트 색 통일
# ──────────────────────────────────────────────

C_ACCENT = "#255c4a"     # 메인 강조 (녹색)
C_ACCENT2 = "#b4512a"    # 보조 강조 (테라코타)
C_ACCENT3 = "#3f5e99"    # 추가 강조 (블루)
C_INK = "#20231f"
C_MUTED = "#9aa39a"      # 역대 전시 점 등 흐린 회색
C_GRID = "#d9ddd4"       # 격자·기준선
# 범주형(매체 구성 등) — 미술관 톤 확장 팔레트
C_CATEGORICAL = ["#255c4a", "#b4512a", "#3f5e99", "#8a6d3b",
                 "#6d6a8c", "#4a7c59", "#a8632c", "#5a6e80"]


# ──────────────────────────────────────────────
# 파이차트: 관객 구성 (입장권별)
# ──────────────────────────────────────────────

def create_visitor_pie_chart(data, title="관객 구성", output_path=None):
    """관객 구성 파이차트 생성

    Args:
        data: dict, {"카테고리": 값, ...}
            예: {"일반": 3500, "학생": 1200, "초대권": 300}
        title: 차트 제목
        output_path: 저장 경로 (None이면 임시 파일)

    Returns:
        저장된 파일 경로
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')

    font_prop = get_font_prop()

    fig, ax = plt.subplots(1, 1, figsize=(6, 5))

    labels = list(data.keys())
    values = list(data.values())
    total = sum(values)

    # 색상 팔레트 (미술관 톤)
    colors = C_CATEGORICAL[:len(labels)]

    def autopct_func(pct):
        absolute = int(round(pct / 100.0 * total))
        return f'{pct:.1f}%\n({absolute:,}명)'

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct=autopct_func,
        startangle=90,
        colors=colors,
        pctdistance=0.65,
        wedgeprops=dict(width=0.85, edgecolor='white', linewidth=2)
    )

    # 텍스트 스타일
    for autotext in autotexts:
        autotext.set_fontsize(9)
        if font_prop:
            autotext.set_fontproperties(font_prop)

    # 범례
    legend_labels = [f'{l} ({v:,}명)' for l, v in zip(labels, values)]
    legend = ax.legend(
        wedges, legend_labels,
        title="",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1),
        fontsize=9,
        prop=font_prop
    )

    if font_prop:
        ax.set_title(title, fontsize=14, fontweight='bold', fontproperties=font_prop, pad=20)
    else:
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    return output_path


# ──────────────────────────────────────────────
# 파이차트: 유형별 관객 구성
# ──────────────────────────────────────────────

def create_visitor_type_chart(data, title="유형별 관객 구성", output_path=None):
    """유형별 관객 구성 파이차트

    Args:
        data: dict, {"개인": 4000, "미술대학 단체": 500, ...}
    """
    return create_visitor_pie_chart(data, title=title, output_path=output_path)


# ──────────────────────────────────────────────
# 바 차트: 주별 관객 수
# ──────────────────────────────────────────────

def create_weekly_visitors_chart(data, title="주별 관객 수", output_path=None,
                                 ref_lines=None):
    """주별 관객 수 영역·라인 차트.

    Args:
        data: dict, {"1주": 500, "2주": 620, ...}
        ref_lines: [(value, label, color), ...] — 비교 기준선(같은 유형 평균/마지막
                   전시의 주당 환산 등). 없으면 자체 평균선 표시.
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')

    font_prop = get_font_prop()

    fig, ax = plt.subplots(figsize=(10, 4.6))

    weeks = list(data.keys())
    values = list(data.values())
    x = list(range(len(weeks)))

    # 영역 + 라인 + 마커 (추세감) — 미술관 톤
    ax.fill_between(x, values, color=C_ACCENT, alpha=0.12, zorder=1)
    ax.plot(x, values, color=C_ACCENT, linewidth=2, marker='o', markersize=6,
            markerfacecolor='white', markeredgecolor=C_ACCENT,
            markeredgewidth=1.5, zorder=3, label="이번 전시")

    # 비교 기준선 (같은 유형 평균/마지막) — 없으면 자체 평균
    drawn_ref = False
    if ref_lines:
        ref_colors = [C_ACCENT2, "#3f5e99"]
        for i, (val, label, color) in enumerate(ref_lines):
            if val is None or val <= 0:
                continue
            c = color or ref_colors[i % len(ref_colors)]
            ax.axhline(val, color=c, linestyle='--', linewidth=1.2, alpha=0.85,
                       zorder=2)
            ax.text(x[-1], val, f' {label} {val:,.0f}', va='bottom', ha='right',
                    fontsize=8.5, color=c, fontproperties=font_prop)
            drawn_ref = True
    if not drawn_ref and values:
        avg = sum(values) / len(values)
        ax.axhline(avg, color=C_ACCENT2, linestyle='--', linewidth=1.1,
                   alpha=0.8, zorder=2)
        ax.text(x[0], avg, f' 평균 {avg:,.0f}', va='bottom', ha='left',
                fontsize=8.5, color=C_ACCENT2, fontproperties=font_prop)

    # 값 표시
    for xi, val in zip(x, values):
        ax.text(xi, val + max(values) * 0.03, f'{val:,}', ha='center',
                va='bottom', fontsize=9, fontproperties=font_prop, color=C_INK)

    ax.set_xticks(x)
    if font_prop:
        ax.set_xticklabels(weeks, fontproperties=font_prop, fontsize=9)
        ax.set_title(title, fontsize=14, fontweight='bold', fontproperties=font_prop, pad=15)
        ax.set_ylabel('관객 수 (명)', fontproperties=font_prop, fontsize=10)
    else:
        ax.set_xticklabels(weeks, fontsize=9)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Visitors', fontsize=10)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    return output_path


# ──────────────────────────────────────────────
# 바 차트: 예산 계획 대비 집행
# ──────────────────────────────────────────────

def create_budget_comparison_chart(categories, planned, actual,
                                    title="예산 계획 대비 집행", output_path=None):
    """예산 계획 대비 집행 비교 바 차트

    Args:
        categories: list, ["전시비", "부대비", ...]
        planned: list, [계획액, ...]
        actual: list, [집행액, ...]
        title: 차트 제목
        output_path: 저장 경로

    Returns:
        저장된 파일 경로
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')

    font_prop = get_font_prop()

    fig, ax = plt.subplots(figsize=(8, 5))

    x = range(len(categories))
    width = 0.35

    bars1 = ax.bar([i - width / 2 for i in x], planned, width,
                   label='계획', color=C_ACCENT3, edgecolor='white')
    bars2 = ax.bar([i + width / 2 for i in x], actual, width,
                   label='집행', color=C_ACCENT, edgecolor='white')

    ax.set_xticks(x)
    if font_prop:
        ax.set_xticklabels(categories, fontproperties=font_prop, fontsize=10)
        ax.set_title(title, fontsize=14, fontweight='bold', fontproperties=font_prop, pad=15)
        ax.set_ylabel('금액 (원)', fontproperties=font_prop, fontsize=10)
        ax.legend(prop=font_prop, fontsize=10)
    else:
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Amount', fontsize=10)
        ax.legend(fontsize=10)

    # 값 표시
    def format_amount(val):
        if val >= 10000:
            return f'{val / 10000:.0f}만'
        return f'{val:,.0f}'

    for bar in bars1:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height,
                format_amount(height), ha='center', va='bottom', fontsize=8,
                fontproperties=font_prop)
    for bar in bars2:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height,
                format_amount(height), ha='center', va='bottom', fontsize=8,
                fontproperties=font_prop)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    return output_path


# 하위 호환: 기존 함수 이름 유지
def create_monthly_visitors_chart(data, title="월별 관객 수", output_path=None):
    """하위 호환 — create_weekly_visitors_chart 사용 권장"""
    return create_weekly_visitors_chart(data, title=title, output_path=output_path)


def create_age_distribution_chart(data, title="연령대별 관객 구성", output_path=None):
    """하위 호환 — create_visitor_type_chart 사용 권장"""
    return create_visitor_type_chart(data, title=title, output_path=output_path)


# ──────────────────────────────────────────────
# 유사 전시 비교 그룹 막대 그래프
# ──────────────────────────────────────────────

def create_similar_bar_chart(current_data, similar_rows, field_labels=None,
                              title="유사 전시 비교", output_path=None):
    """현재 전시와 유사 전시들을 그룹 막대 그래프로 비교.

    Parameters:
        current_data: dict — {field_name: value}
        similar_rows: list of SimilarExhibitionRow
        field_labels: dict — {field_name: 표시 라벨} (기본값 제공)
        title: str
        output_path: str or None

    Returns:
        output_path (str) or None
    """
    import numpy as np

    if field_labels is None:
        field_labels = {
            "총 관객수": "관객수",
            "총 사용 예산": "예산",
            "프로그램 총 수": "프로그램",
            "언론 보도 건수": "언론보도",
            "출품 작품 수_총": "출품작품",
            "일평균 관객수": "일평균",
        }

    font_prop = get_font_prop()

    # 사용 가능한 필드만 필터 (현재 전시에 값이 있는 것)
    fields = []
    for f in field_labels:
        val = current_data.get(f)
        if val and val > 0:
            fields.append(f)

    if len(fields) < 2:
        return None

    labels = [field_labels.get(f, f) for f in fields]
    n = len(fields)

    # 각 전시의 값 수집
    all_series = []
    series_names = []

    # 현재 전시
    current_vals = [current_data.get(f, 0) or 0 for f in fields]
    all_series.append(current_vals)
    series_names.append(current_data.get("전시 제목", "현재 전시"))

    # 유사 전시 (상위 3개만)
    for row in similar_rows[:3]:
        vals = [row.metrics.get(f, 0) or 0 for f in fields]
        if any(v > 0 for v in vals):
            all_series.append(vals)
            title_short = row.title[:10] + "…" if len(row.title) > 10 else row.title
            series_names.append(title_short)

    if len(all_series) < 2:
        return None

    # 정규화 (각 축의 최댓값 기준 0~1 스케일) — 스케일이 다른 항목 비교를 위해
    max_vals = [max(s[i] for s in all_series) for i in range(n)]
    max_vals = [m if m > 0 else 1 for m in max_vals]
    normalized = [[s[i] / max_vals[i] for i in range(n)] for s in all_series]

    # 그래프 생성
    num_series = len(all_series)
    x = np.arange(n)
    bar_width = 0.7 / num_series

    fig, ax = plt.subplots(figsize=(max(8, n * 1.8), 5))

    colors = [C_ACCENT, C_ACCENT2, C_ACCENT3, "#8a6d3b"]

    for idx, (norm_vals, raw_vals, name) in enumerate(
            zip(normalized, all_series, series_names)):
        offset = (idx - num_series / 2 + 0.5) * bar_width
        bars = ax.bar(x + offset, norm_vals, bar_width,
                      label=name, color=colors[idx % len(colors)],
                      edgecolor='white', linewidth=0.5, alpha=0.85)

        # 값 라벨 (현재 전시만 실제 값 표시)
        if idx == 0:
            for bar, raw_v in zip(bars, raw_vals):
                if raw_v >= 100_000_000:
                    display = f"{raw_v/100_000_000:.1f}억"
                elif raw_v >= 10_000:
                    display = f"{raw_v/10_000:.0f}만"
                elif raw_v >= 1_000:
                    display = f"{raw_v:,.0f}"
                else:
                    display = f"{raw_v:,.0f}"
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                        display, ha='center', va='bottom', fontsize=8,
                        fontproperties=font_prop, color=C_ACCENT, fontweight='bold')

    ax.set_xticks(x)
    if font_prop:
        ax.set_xticklabels(labels, fontproperties=font_prop, fontsize=10)
        ax.set_title(title, fontsize=13, fontweight='bold', fontproperties=font_prop, pad=15)
        ax.legend(prop=font_prop, fontsize=9, loc='upper right')
    else:
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_title(title, fontsize=13, fontweight='bold', pad=15)
        ax.legend(fontsize=9, loc='upper right')

    ax.set_ylim(0, 1.3)
    ax.set_ylabel('')
    ax.set_yticklabels([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.tick_params(left=False)
    ax.grid(axis='y', alpha=0.2)

    plt.tight_layout()

    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), "similar_bar.png")
    fig.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 차트 공통 스타일 상수 (v5.3.61) — 도판 전반의 타이포·여백 일관성
# ──────────────────────────────────────────────

CH_TITLE = 14      # 도판 제목
CH_LABEL = 11      # 축·항목 라벨(굵게)
CH_VALUE = 11      # 강조 수치
CH_CAPTION = 9     # 보조 캡션(흐린 회색)
CH_TICK = 9        # 축 눈금


def _fp(size=None, bold=False):
    """폰트 속성 사본 반환(크기·굵기 적용). 한글 폰트 우선."""
    base = get_font_prop()
    if base is None:
        return None
    import copy
    fp = copy.copy(base)
    if size:
        fp.set_size(size)
    if bold:
        fp.set_weight('bold')
    return fp


def _eok_man(v):
    """원 단위 → '2.10억' / '1,400만' 표시."""
    v = v or 0
    if v >= 1e8:
        return f"{v/1e8:.2f}억"
    if v >= 1e4:
        return f"{v/1e4:,.0f}만"
    return f"{v:,.0f}원"


# ──────────────────────────────────────────────
# 롤리팝(점-막대): 기준 대비 핵심 지표 (v5.3.61 신규)
# ──────────────────────────────────────────────

def create_keymetrics_lollipop(rows, title="기준 대비 핵심 지표", output_path=None):
    """기준(=100) 대비 핵심 지표를 롤리팝(가는 트랙+점)으로 표현.

    rows: [{"label", "current_fmt", "reference_fmt", "ratio"(float, 기준=100)}]
    기준 위(>=100)=녹색, 아래(<100)=테라코타. 평가 의미 없이 '평균 대비 위치'.
    """
    rows = [r for r in rows if r.get("ratio") is not None]
    if len(rows) < 2:
        return None
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')

    n = len(rows)
    fig, ax = plt.subplots(figsize=(9, 0.62 * n + 1.1))

    ratios = [r["ratio"] for r in rows]
    xmax = max(160, max(ratios) * 1.08)
    ys = list(range(n))[::-1]  # 위에서 아래로

    for y, r in zip(ys, rows):
        val = r["ratio"]
        color = C_ACCENT if val >= 100 else C_ACCENT2
        # 트랙(전체 0~xmax 연한 배경 선)
        ax.plot([0, xmax], [y, y], color="#eef1ec", linewidth=5,
                solid_capstyle='round', zorder=1)
        # 기준(100)에서 값까지 강조 세그먼트
        ax.plot([100, val], [y, y], color=color, linewidth=5,
                solid_capstyle='round', zorder=2)
        ax.scatter([val], [y], s=90, color=color, zorder=3,
                   edgecolor='white', linewidth=1.2)
        # 값 라벨(점 위)
        ax.text(val, y + 0.28, f"{val:.0f}", ha='center', va='bottom',
                fontproperties=_fp(CH_VALUE, bold=True), color=color)

    # 기준선(100) 점선
    ax.axvline(100, color="#9aa39a", linestyle='--', linewidth=1.1, zorder=1)

    # 좌측 거터: 항목명(굵게) + 캡션(현재 / 기준)
    ax.set_yticks(ys)
    ax.set_yticklabels([r["label"] for r in rows])
    for tick, r in zip(ax.get_yticklabels(), rows):
        tick.set_fontproperties(_fp(CH_LABEL, bold=True))
        tick.set_color(C_INK)
    # 캡션은 각 라벨 아래에 별도 텍스트(축 바깥)
    for y, r in zip(ys, rows):
        cap = f"{r.get('current_fmt','')} / 기준 {r.get('reference_fmt','')}"
        ax.annotate(cap, xy=(0, y), xycoords=('axes fraction', 'data'),
                    xytext=(-12, -11), textcoords='offset points',
                    ha='right', va='center',
                    fontproperties=_fp(CH_CAPTION), color="#7a827a")

    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([0, 100, round(xmax)])
    ax.set_xticklabels(["0", "100", f"{round(xmax)}"])
    for lbl in ax.get_xticklabels():
        lbl.set_fontproperties(_fp(CH_TICK)); lbl.set_color("#7a827a")
    ax.xaxis.set_ticks_position('top')
    ax.tick_params(axis='y', length=0)
    ax.tick_params(axis='x', length=0)
    for sp in ('top', 'right', 'bottom', 'left'):
        ax.spines[sp].set_visible(False)
    ax.set_title(title, fontproperties=_fp(CH_TITLE, bold=True), color=C_INK,
                 pad=18, loc='left')

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 재정 지표 멀티패널 (v5.3.61 신규)
# ──────────────────────────────────────────────

def create_financial_panel(fin, title="재정 지표 구조", output_path=None):
    """재정 지표를 2x2 멀티패널로: 총예산·총수입(미니 막대), 집행률·관객당비용(진행 막대).

    fin = {
      "budget":  {"current": 원, "ref": 원},
      "revenue": {"current": 원, "ref": 원},
      "exec_rate": {"current": %, "ref": %},
      "cost":    {"current": 원, "ref": 원},
    }
    """
    if not fin:
        return None
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')

    fig, axes = plt.subplots(2, 2, figsize=(9, 4.6))
    fig.subplots_adjust(hspace=0.7, wspace=0.35)

    def mini_bar(ax, sub_title, cur, ref, fmt):
        ax.set_title(sub_title, fontproperties=_fp(11, bold=True), color=C_INK,
                     loc='left', pad=8)
        vals = [cur or 0, ref or 0]
        bars = ax.bar([0, 1], vals, width=0.55,
                      color=[C_ACCENT, "#c7cdc2"], edgecolor='white')
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width()/2, v, fmt(v), ha='center',
                    va='bottom', fontproperties=_fp(CH_CAPTION, bold=True),
                    color=C_INK)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["이번", "기준"], fontproperties=_fp(CH_TICK),
                           color="#7a827a")
        ax.set_ylim(0, max(vals) * 1.25 if max(vals) > 0 else 1)
        ax.set_yticks([])
        for sp in ('top', 'right', 'left'):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0)

    def progress(ax, sub_title, cur, ref, fmt):
        ax.set_title(sub_title, fontproperties=_fp(11, bold=True), color=C_INK,
                     loc='left', pad=8)
        scale = max(cur or 0, ref or 0) * 1.15 or 1
        ax.barh([0], [scale], color="#eef1ec", height=0.4, zorder=1)
        ax.barh([0], [cur or 0], color=C_ACCENT, height=0.4, zorder=2)
        if ref:
            # 기준 점선은 막대 높이로만 제한 (캡션과 겹침 방지)
            ax.plot([ref, ref], [-0.26, 0.26], color=C_INK, linestyle='--',
                    linewidth=1.2, zorder=3)
        ax.text(0, -0.5, f"이번 {fmt(cur)}", ha='left', va='top',
                fontproperties=_fp(CH_CAPTION), color=C_ACCENT)
        ax.text(scale, -0.5, f"기준 {fmt(ref)}", ha='right', va='top',
                fontproperties=_fp(CH_CAPTION), color="#7a827a")
        ax.set_xlim(0, scale)
        ax.set_ylim(-1, 0.5)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ('top', 'right', 'left', 'bottom'):
            ax.spines[sp].set_visible(False)

    won = _eok_man
    pct = lambda v: f"{v:.1f}%" if v else "—"
    won_per = lambda v: f"{v:,.0f}원/명" if v else "—"

    b, r = fin.get("budget", {}), fin.get("revenue", {})
    e, c = fin.get("exec_rate", {}), fin.get("cost", {})
    mini_bar(axes[0][0], "총 사용 예산", b.get("current"), b.get("ref"), won)
    mini_bar(axes[0][1], "총 수입", r.get("current"), r.get("ref"), won)
    progress(axes[1][0], "예산 집행률", e.get("current"), e.get("ref"), pct)
    progress(axes[1][1], "관객당 비용", c.get("current"), c.get("ref"), won_per)

    fig.suptitle(title, fontproperties=_fp(CH_TITLE, bold=True), color=C_INK,
                 x=0.02, ha='left', y=1.02)
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 유사 전시 시간순 추세선 (v5.3.68) — x=전시(시간순), 선=지표
# ──────────────────────────────────────────────

def create_similar_trend_chart(current_data, similar_rows, current_start=None,
                               field_labels=None, title="유사 전시 비교 (시간순 추이)",
                               output_path=None):
    """유사 전시군을 시간순으로 배열하고 지표별 추세선을 그림.

    각 지표는 해당 군 내 최댓값=100%로 정규화(스케일 다른 지표 동시 비교).
    이번 전시는 x축 라벨 강조 + 점 강조.
    """
    import numpy as np
    from datetime import date as _date

    if field_labels is None:
        field_labels = {
            "총 관객수": "관객수", "총 사용 예산": "예산",
            "프로그램 총 수": "프로그램", "언론 보도 건수": "언론보도",
            "출품 작품 수_총": "출품작품", "일평균 관객수": "일평균",
        }

    def _pdate(d):
        if not d:
            return None
        try:
            s = str(d)[:10].replace(".", "-").replace("/", "-")
            p = [int(x) for x in s.split("-")[:3]]
            return _date(p[0], p[1], p[2]) if len(p) == 3 else None
        except (ValueError, TypeError):
            return None

    # 전시 목록: (이름, 날짜, metrics, is_current)
    exs = []
    cur_name = current_data.get("전시 제목", "이번 전시")
    exs.append((cur_name, _pdate(current_start), current_data, True))
    for r in similar_rows:
        exs.append((r.title, _pdate(getattr(r, "start", None)), r.metrics, False))

    # 날짜 있는 것만, 시간순 정렬
    exs = [e for e in exs if e[1] is not None]
    if len(exs) < 3:
        return None
    exs.sort(key=lambda e: e[1])

    # 사용할 지표(이번 전시에 값이 있는 것)
    fields = [f for f in field_labels if current_data.get(f)]
    if len(fields) < 2:
        return None

    fp = get_font_prop()
    # 넉넉한 가로폭 + 하단 라벨(가로·줄바꿈) 공간
    fig, ax = plt.subplots(figsize=(max(10, len(exs) * 2.0), 6.2))

    x = list(range(len(exs)))
    colors = C_CATEGORICAL
    for fi, f in enumerate(fields):
        vals = [float(m.get(f) or 0) for _, _, m, _ in exs]
        mx = max(vals) or 1
        norm = [v / mx * 100 for v in vals]
        ax.plot(x, norm, marker='o', markersize=7, linewidth=2.2,
                color=colors[fi % len(colors)], label=field_labels[f],
                markerfacecolor='white', markeredgewidth=2,
                markeredgecolor=colors[fi % len(colors)], zorder=2)

    # 이번 전시 위치 강조
    cur_idx = next((i for i, e in enumerate(exs) if e[3]), None)
    if cur_idx is not None:
        ax.axvspan(cur_idx - 0.24, cur_idx + 0.24, color=C_ACCENT, alpha=0.08, zorder=1)

    def _wrap(s, width=11):
        # 전체 이름 표기(절단 없음) — 공백 기준 가로 줄바꿈, 긴 토큰은 강제 분할
        lines, cur = [], ""
        for tok in str(s).split(" "):
            cand = (cur + " " + tok).strip() if cur else tok
            if len(cand) <= width:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                while len(tok) > width:
                    lines.append(tok[:width]); tok = tok[width:]
                cur = tok
        if cur:
            lines.append(cur)
        return "\n".join(lines)

    ax.set_xticks(x)
    # 가로 표기(rotation 0), 표 본문과 같은 서체·크기(11) — 절단 없음
    ax.set_xticklabels([_wrap(e[0]) for e in exs], rotation=0, ha='center')
    for tk, e in zip(ax.get_xticklabels(), exs):
        tk.set_fontproperties(_fp(11, bold=e[3]))
        tk.set_color(C_ACCENT if e[3] else "#20231f")
    ax.set_ylim(0, 116)
    ax.set_ylabel("지표별 최댓값 대비 (%)", fontproperties=_fp(11), color="#646b61")
    # 차트 제목은 탭의 '유사 전시 비교' 헤더와 중복 → 생략. 범례만 상단에.
    ax.legend(prop=_fp(11), ncol=min(len(fields), 6), loc='lower center',
              bbox_to_anchor=(0.5, 1.01), frameon=False, columnspacing=1.8,
              handlelength=1.8)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis='x', length=0, pad=8)
    ax.tick_params(axis='y', labelsize=10, length=0)
    ax.grid(axis='y', alpha=0.15)
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 가로 막대: 이번 vs 기준 비교 (v5.3.63) — 유료 비율 등
# ──────────────────────────────────────────────

def create_comparison_bar(items, title="비교", unit="%", output_path=None):
    """이번/같은 유형 평균/마지막 전시를 가로 막대로 비교.

    items: [(label, value, is_current_bool), ...]  (value 단위는 unit)
    이번 전시 막대는 녹색 강조, 기준은 회색.
    """
    items = [(lbl, v, cur) for (lbl, v, cur) in items if v is not None]
    if len(items) < 2:
        return None
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')
    fp = get_font_prop()
    n = len(items)
    fig, ax = plt.subplots(figsize=(8, 0.6 * n + 0.9))

    ys = list(range(n))[::-1]
    vmax = max(v for _, v, _ in items) * 1.18 or 1
    for y, (lbl, v, is_cur) in zip(ys, items):
        color = C_ACCENT if is_cur else "#c7cdc2"
        ax.barh([y], [v], color=color, height=0.55, edgecolor='white', zorder=2)
        val_txt = f"{v:.1f}{unit}" if unit == "%" else f"{v:,.0f}{unit}"
        ax.text(v, y, f" {val_txt}", va='center', ha='left',
                fontproperties=_fp(CH_CAPTION, bold=is_cur),
                color=C_INK if is_cur else "#7a827a")
    ax.set_yticks(ys)
    ax.set_yticklabels([lbl for lbl, _, _ in items])
    for tick, (_, _, is_cur) in zip(ax.get_yticklabels(), items):
        tick.set_fontproperties(_fp(CH_CAPTION, bold=is_cur))
        tick.set_color(C_INK if is_cur else "#7a827a")
    ax.set_xlim(0, vmax)
    ax.set_xticks([])
    ax.set_title(title, fontproperties=_fp(12, bold=True), color=C_INK,
                 loc='left', pad=10)
    ax.tick_params(length=0)
    for sp in ('top', 'right', 'bottom', 'left'):
        ax.spines[sp].set_visible(False)
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 도넛: 출품 매체 구성 (v5.3.60 신규)
# ──────────────────────────────────────────────

def create_media_composition_chart(media_dict, title="출품 매체 구성",
                                   output_path=None, unit="점", center_suffix=None):
    """구성 도넛 (매체·신작/구작·입장권·유료무료 공용).

    v5.3.64: 범례를 하단 가로로 내리고 도넛을 크게(2개 나란히 배치 최적화).
    media_dict: {"회화": 18, ...} (0은 자동 제외)
    unit: 범례·중앙 단위 ("점"/"명")
    center_suffix: 중앙 총계 단위 (None이면 unit 사용)
    """
    data = {k: v for k, v in media_dict.items() if v and v > 0}
    if len(data) < 2:
        return None
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')
    fp = get_font_prop()
    labels = list(data.keys())
    values = list(data.values())
    total = sum(values)
    colors = C_CATEGORICAL[:len(labels)]

    # 정사각형 도넛 + 하단 가로 범례 공간
    fig, ax = plt.subplots(figsize=(5.4, 6.0))

    def autopct(pct):
        return f'{pct:.0f}%' if pct >= 7 else ''

    wedges, _t, autotexts = ax.pie(
        values, labels=None, autopct=autopct, startangle=90, colors=colors,
        radius=1.0, pctdistance=0.80,
        wedgeprops=dict(width=0.40, edgecolor='white', linewidth=2.5))
    for at in autotexts:
        at.set_color('white'); at.set_fontproperties(_fp(11, bold=True))
    # 중앙 총계
    cs = center_suffix if center_suffix is not None else unit
    ax.text(0, 0, f'{total:,}{cs}', ha='center', va='center',
            fontproperties=_fp(17, bold=True), color=C_INK)
    ax.set_title(title, fontproperties=_fp(CH_TITLE, bold=True), color=C_INK,
                 pad=14)

    # 하단 가로 범례 (값 포함). 항목 많으면 줄바꿈(최대 3열).
    legend_labels = [f'{l} {v:,}{unit}' for l, v in zip(labels, values)]
    ncol = min(3, len(labels))
    ax.legend(wedges, legend_labels, loc="upper center",
              bbox_to_anchor=(0.5, -0.02), ncol=ncol, frameon=False,
              prop=_fp(CH_CAPTION), handlelength=1.0, columnspacing=1.4,
              labelspacing=0.5)
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 가로 막대: 예산 구조 (v5.3.60 신규)
# ──────────────────────────────────────────────

def create_budget_structure_chart(exhibition, supplementary, planned=None,
                                   title="예산 구조", output_path=None):
    """전시비/부대비 구성을 가로 스택 막대로, 계획액은 기준선으로 표시.

    exhibition, supplementary, planned: 원 단위 숫자
    """
    total = (exhibition or 0) + (supplementary or 0)
    if total <= 0:
        return None
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')
    fp = get_font_prop()
    fig, ax = plt.subplots(figsize=(9, 2.4))

    def eok(v):  # 억 단위
        return (v or 0) / 1e8

    e, s = eok(exhibition), eok(supplementary)
    ax.barh([0], [e], color=C_ACCENT, edgecolor='white', height=0.5, label='전시비')
    ax.barh([0], [s], left=[e], color=C_ACCENT2, edgecolor='white', height=0.5, label='부대비')
    # 세그먼트 값 라벨
    if e > 0:
        ax.text(e / 2, 0, f'전시비\n{e:.2f}억 ({exhibition/total*100:.0f}%)',
                ha='center', va='center', color='white', fontsize=9,
                fontweight='bold', fontproperties=fp if fp else None)
    if s > 0:
        ax.text(e + s / 2, 0, f'부대비\n{s:.2f}억 ({supplementary/total*100:.0f}%)',
                ha='center', va='center', color='white', fontsize=9,
                fontweight='bold', fontproperties=fp if fp else None)
    # 계획액 기준선
    if planned and planned > 0:
        px = eok(planned)
        ax.axvline(px, color=C_INK, linestyle='--', linewidth=1.2)
        ax.text(px, 0.42, f'계획 {px:.2f}억', ha='center', va='bottom',
                fontsize=8.5, color=C_INK, fontproperties=fp if fp else None)
    ax.set_xlim(0, max(eok(total), eok(planned) if planned else 0) * 1.15)
    ax.set_yticks([])
    ax.set_xlabel('금액 (억원)', fontproperties=fp if fp else None, fontsize=9)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=12,
                 fontproperties=fp if fp else None)
    for sp in ('top', 'right', 'left'):
        ax.spines[sp].set_visible(False)
    ax.grid(axis='x', alpha=0.2)
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 산점도(사분면): 예산 대비 관객 효율 — 역대 분포 속 위치 (v5.3.60 신규)
# ──────────────────────────────────────────────

def create_efficiency_scatter_chart(current, ref_points,
                                    title="예산 대비 관객 (역대 전시 분포)",
                                    output_path=None):
    """x=예산, y=관객 산점도. 역대 18개 전시 분포 + 이번 전시 강조,
    평균선으로 4분면 구획.

    current: {"title", "budget", "visitors"}
    ref_points: [{"title","budget","visitors"}, ...]
    """
    import numpy as np
    pts = [(p.get("budget"), p.get("visitors"), p.get("title", ""))
           for p in (ref_points or [])
           if p.get("budget") and p.get("visitors")]
    if len(pts) < 3:
        return None
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')
    fp = get_font_prop()
    fig, ax = plt.subplots(figsize=(8, 5.6))

    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    ax.scatter(xs / 1e8, ys, s=48, color=C_MUTED, alpha=0.65,
               edgecolor='white', linewidth=0.6, zorder=2, label='역대 전시')
    # 평균 사분면 기준선
    mx, my = float(xs.mean()), float(ys.mean())
    ax.axvline(mx / 1e8, color=C_GRID, linestyle='--', linewidth=1, zorder=1)
    ax.axhline(my, color=C_GRID, linestyle='--', linewidth=1, zorder=1)
    ax.text(mx / 1e8, ax.get_ylim()[1], ' 평균 예산', va='top', ha='left',
            fontsize=8, color=C_MUTED, fontproperties=fp if fp else None)

    cb, cv = current.get("budget"), current.get("visitors")
    if cb and cv:
        ax.scatter([cb / 1e8], [cv], s=200, color=C_ACCENT, edgecolor='white',
                   linewidth=1.6, zorder=4, label='이번 전시')
        ax.annotate(
            (current.get("title", "이번 전시") or "이번 전시")[:14],
            (cb / 1e8, cv), textcoords="offset points", xytext=(9, 9),
            fontsize=10, fontweight='bold', color=C_ACCENT,
            fontproperties=fp if fp else None)

    ax.set_xlabel("총 사용 예산 (억원)", fontproperties=fp if fp else None, fontsize=10)
    ax.set_ylabel("총 관객수 (명)", fontproperties=fp if fp else None, fontsize=10)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=14,
                 fontproperties=fp if fp else None)
    ax.legend(prop=fp, fontsize=9, loc='lower right')
    ax.get_yaxis().set_major_formatter(
        plt.FuncFormatter(lambda v, _p: f'{int(v):,}'))
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    ax.grid(alpha=0.12)
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 라인: 역대 전시 지표 시계열 — 이번 전시 강조 (v5.3.60 신규)
# ──────────────────────────────────────────────

def create_trend_chart(current, ref_points, metric_key="visitors",
                       metric_label="총 관객수", unit="명",
                       title=None, output_path=None):
    """역대 전시를 시작일 순으로 늘어놓고 지표 추이를 라인으로, 이번 전시를 강조.

    current/ref_points 항목: {"start"(YYYY-MM-DD), metric_key, "title"}
    """
    from datetime import date as _date

    def _parse(d):
        if not d:
            return None
        if isinstance(d, _date):
            return d
        # "2021.10.01", "2021-10-01", "2021/10/01" 등 구분자 정규화
        s = str(d)[:10].replace('.', '-').replace('/', '-').strip('-')
        parts = [p for p in s.split('-') if p]
        if len(parts) >= 3:
            try:
                return _date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, TypeError):
                return None
        return None

    rows = []
    for p in (ref_points or []):
        dt = _parse(p.get("start"))
        v = p.get(metric_key)
        if dt and v:
            rows.append((dt, float(v), p.get("title", "")))
    if len(rows) < 3:
        return None
    rows.sort(key=lambda r: r[0])

    if title is None:
        title = f"역대 전시 {metric_label} 추이"
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')
    fp = get_font_prop()
    fig, ax = plt.subplots(figsize=(9, 4.6))

    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    ax.plot(xs, ys, color=C_MUTED, linewidth=1.6, marker='o', markersize=5,
            markerfacecolor='white', markeredgecolor=C_MUTED, zorder=2,
            label='역대 전시')
    # 평균선
    import numpy as np
    avg = float(np.mean(ys))
    ax.axhline(avg, color=C_ACCENT2, linestyle='--', linewidth=1.1, alpha=0.8,
               zorder=1)
    ax.text(xs[0], avg, f' 평균 {avg:,.0f}{unit}', va='bottom', ha='left',
            fontsize=8.5, color=C_ACCENT2, fontproperties=fp if fp else None)

    # 이번 전시 강조
    cdt = _parse(current.get("start"))
    cv = current.get(metric_key)
    if cdt and cv:
        ax.scatter([cdt], [float(cv)], s=170, color=C_ACCENT, edgecolor='white',
                   linewidth=1.6, zorder=4, label='이번 전시')
        ax.annotate((current.get("title", "이번 전시") or "이번 전시")[:14],
                    (cdt, float(cv)), textcoords="offset points", xytext=(8, 9),
                    fontsize=10, fontweight='bold', color=C_ACCENT,
                    fontproperties=fp if fp else None)

    ax.set_ylabel(f"{metric_label} ({unit})", fontproperties=fp if fp else None,
                  fontsize=10)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=14,
                 fontproperties=fp if fp else None)
    ax.legend(prop=fp, fontsize=9, loc='best')
    ax.get_yaxis().set_major_formatter(
        plt.FuncFormatter(lambda v, _p: f'{int(v):,}'))
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    for lbl in ax.get_xticklabels():
        if fp:
            lbl.set_fontproperties(fp)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    ax.grid(axis='y', alpha=0.15)
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return output_path


# ──────────────────────────────────────────────
# 테스트용
# ──────────────────────────────────────────────

if __name__ == "__main__":
    visitor_data = {"일반": 3500, "학생": 800, "초대권": 300, "예술인패스": 509, "기타 할인": 200}
    path1 = create_visitor_pie_chart(visitor_data, title="입장권별 관객 구성",
                                      output_path="/tmp/test_pie.png")
    print(f"파이차트 생성: {path1}")

    weekly_data = {"1주": 800, "2주": 1200, "3주": 1500, "4주": 1000, "5주": 900}
    path2 = create_weekly_visitors_chart(weekly_data, output_path="/tmp/test_bar.png")
    print(f"주별 바차트 생성: {path2}")

    categories = ["전시비", "부대비", "인건비"]
    planned = [50000000, 20000000, 15000000]
    actual = [48000000, 22000000, 14500000]
    path3 = create_budget_comparison_chart(categories, planned, actual,
                                            output_path="/tmp/test_budget.png")
    print(f"예산 비교 차트 생성: {path3}")

    type_data = {"개인": 4000, "미술대학 단체": 500, "기타 단체": 300, "오프닝 리셉션": 200}
    path4 = create_visitor_type_chart(type_data, output_path="/tmp/test_type.png")
    print(f"유형별 파이차트 생성: {path4}")
