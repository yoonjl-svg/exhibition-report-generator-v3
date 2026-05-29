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

def create_weekly_visitors_chart(data, title="주별 관객 수", output_path=None):
    """주별 관객 수 바 차트 생성

    Args:
        data: dict, {"1주": 500, "2주": 620, ...}
        title: 차트 제목
        output_path: 저장 경로

    Returns:
        저장된 파일 경로
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
            markeredgewidth=1.5, zorder=3)

    # 평균 기준선
    if values:
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
# 도넛: 출품 매체 구성 (v5.3.60 신규)
# ──────────────────────────────────────────────

def create_media_composition_chart(media_dict, title="출품 매체 구성", output_path=None):
    """매체별 작품 수 도넛 차트.

    media_dict: {"회화": 18, "조각": 8, ...} (0은 자동 제외)
    """
    data = {k: v for k, v in media_dict.items() if v and v > 0}
    if len(data) < 2:
        return None
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.png')
    fp = get_font_prop()
    fig, ax = plt.subplots(figsize=(6.5, 5))
    labels = list(data.keys())
    values = list(data.values())
    total = sum(values)
    colors = C_CATEGORICAL[:len(labels)]

    def autopct(pct):
        return f'{pct:.0f}%' if pct >= 6 else ''

    wedges, _t, autotexts = ax.pie(
        values, labels=None, autopct=autopct, startangle=90, colors=colors,
        pctdistance=0.78,
        wedgeprops=dict(width=0.42, edgecolor='white', linewidth=2))
    for at in autotexts:
        at.set_fontsize(9); at.set_color('white'); at.set_fontweight('bold')
        if fp: at.set_fontproperties(fp)
    # 중앙 총계
    ax.text(0, 0, f'{total}점', ha='center', va='center',
            fontsize=15, fontweight='bold', color=C_INK,
            fontproperties=fp if fp else None)
    legend_labels = [f'{l} {v}점' for l, v in zip(labels, values)]
    ax.legend(wedges, legend_labels, loc="center left",
              bbox_to_anchor=(1, 0, 0.4, 1), fontsize=9, prop=fp)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=16,
                 fontproperties=fp if fp else None)
    plt.tight_layout()
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
