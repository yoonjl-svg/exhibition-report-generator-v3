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

    # 색상 팔레트
    colors = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#5B9BD5',
              '#70AD47', '#264478', '#9B59B6'][:len(labels)]

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

    fig, ax = plt.subplots(figsize=(10, 5))

    weeks = list(data.keys())
    values = list(data.values())
    x = range(len(weeks))

    bars = ax.bar(x, values, color='#4472C4', width=0.6, edgecolor='white', linewidth=0.5)

    # 값 표시
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + max(values) * 0.02,
                f'{val:,}', ha='center', va='bottom', fontsize=9,
                fontproperties=font_prop)

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
                   label='계획', color='#4472C4', edgecolor='white')
    bars2 = ax.bar([i + width / 2 for i in x], actual, width,
                   label='집행', color='#ED7D31', edgecolor='white')

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
