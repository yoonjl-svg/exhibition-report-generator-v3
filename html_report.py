"""HTML 웹 리포트 렌더러 (v5.3.65, Phase 2)

보고서 생성 탭의 미리보기를 GPT 'Rendered Report'처럼 CSS/SVG 네이티브로
렌더. Word(.docx)는 정식 아카이브로 유지하고, 이쪽은 '보는 즐거움'용 화면 렌더.

핵심 시각화:
  - 핵심 지표: CSS 롤리팝(기준=100 점선, 위=녹색/아래=테라코타)
  - 구성(매체·신작·입장권·유료무료): conic-gradient 도넛 2-up 그리드
  - 주차별 관객 추이: 인라인 SVG 라인 + 비교 기준선

build_report_html(data) -> str  (self-contained HTML 문서; components.html로 표시)
"""

import html as _html

# 미술관 톤 팔레트
ACCENT = "#255c4a"      # 브랜드 녹색(유지)
ACCENT2 = "#a05c44"     # 기준 아래(롤리팝) — 약간 채도 낮춘 테라코타
ACCENT3 = "#2d4a85"     # 포인트색 — 짙은 네이비(어둡고 선명하게, 강조용)
INK = "#20231f"
MUTED = "#7a827a"
LINE = "#d9ddd4"
SOFT = "#eef2ea"
# 컬러칩: 동계열(녹색–세이지–틸–토프) 저채도. 명도 교차로 인접 슬라이스 구분.
CAT = ["#2f5d4e", "#7c9c8b", "#4a7c6a", "#a7b3a0", "#5f8088", "#8c8270"]

# ── 의미 기반 색 토큰 (보고서 전체 문법) ──
# 같은 의미는 보고서 어디서나 같은 색. 색은 '좋다/나쁘다'보다 먼저 '성격'을 구분.
C_BRAND   = ACCENT        # 딥그린 — 브랜드/제목/성과·주요 데이터
C_PERF    = ACCENT        #   = 성과·주요 데이터(막대 본체)
C_CAUTION = ACCENT2       # 테라코타 — 평균 미달·주의(롤리팝 하단)
C_POINT   = ACCENT3       # 블루그레이 — 포인트/보조 강조(수입·보조 기준선) [유지]
C_BASE    = "#9aa39a"     # 중립 회색 — 기준·평균·규모성 지표(예: 총 예산)
C_ETC     = "#c4ccc2"     # 옅은 회색 — 기타·미분류·무료


def _esc(s):
    return _html.escape(str(s if s is not None else ""))


# ──────────────────────────────────────────────
# 컴포넌트
# ──────────────────────────────────────────────

def _lollipop(summary_metrics):
    """평균 대비 핵심 지표 롤리팝. 각 지표를 평균(중앙) 대비 ±% 편차로 표시.
    낮을수록 좋은 지표(관객당 비용)는 부호를 반전해 '개선=+(녹색)'이 되게 한다."""
    rows = []
    for m in (summary_metrics or []):
        cur, ref = m.get("current"), m.get("reference_avg")
        if cur is None or not ref:
            continue
        diff = (cur - ref) / ref * 100          # 평균 대비 % 편차
        if "비용" in (m.get("label") or ""):    # 낮을수록 좋음 → 부호 반전
            diff = -diff
        rows.append((m["label"], m.get("current_fmt", ""),
                     m.get("reference_avg_fmt", ""), diff,
                     m.get("reference_label", "기준")))
    if len(rows) < 2:
        return ""
    # 평균(중앙=50%) 기준 대칭 스케일: 좌우 ±span(%)
    span = max(max(abs(r[3]) for r in rows) * 1.12, 30)
    base_pct = 50.0

    items = []
    for label, cur_fmt, ref_fmt, diff, ref_label in rows:
        clamped = min(max(diff, -span), span)
        val_pct = (clamped + span) / (2 * span) * 100
        # 색=성격: 성과 +는 녹색·-는 테라코타. 단 총 예산은 규모 정보라 중립 회색.
        if "예산" in label:
            color = C_BASE
        else:
            color = C_PERF if diff >= 0 else C_CAUTION
        seg_left = min(base_pct, val_pct)
        seg_w = abs(val_pct - base_pct)
        items.append(f"""
        <div class="lolli">
          <div class="lolli-label">{_esc(label)}
            <span class="cap">{_esc(cur_fmt)} / {_esc(ref_label)} {_esc(ref_fmt)}</span>
          </div>
          <div class="lolli-track">
            <div class="lolli-base" style="left:{base_pct:.1f}%"></div>
            <div class="lolli-seg" style="left:{seg_left:.1f}%;width:{seg_w:.1f}%;background:{color}"></div>
            <div class="lolli-dot" style="left:{val_pct:.1f}%;background:{color}"></div>
            <div class="lolli-val" style="left:{val_pct:.1f}%;color:{color}">{diff:+.0f}%</div>
          </div>
        </div>""")
    # 평균(기준) 라벨만 — 기준선 바로 위
    scale = f'<div class="lolli-scale"><span style="left:{base_pct:.1f}%">평균</span></div>'
    return f"""<div class="subhead">평균 대비 핵심 지표</div>
      <div class="lolli-wrap">{scale}{''.join(items)}</div>"""


def _money_short(v):
    """억 이상은 백만원 단위 내림 → '약 2.10억', 천만 이상은 '약 N,NNN만 원'.
    (롤리팝·종합표의 _fmt_summary_value와 동일 규칙)."""
    if not v:
        return "—"
    v = int(v)
    if v >= 100_000_000:
        return f"약 {v // 1_000_000 / 100:.2f}억"
    if v >= 10_000_000:
        return f"약 {v // 10_000:,}만 원"
    return f"{v:,}원"


def _hbar(title, data_dict, unit="점", muted_keys=()):
    """가로 막대그래프 — 항목 수가 많은 구성(매체·입장권 등)에 도넛 대신 사용.
    수량 내림차순 정렬, 막대 끝에 '값 단위 (비율%)' 병기. 막대는 성과 녹색,
    muted_keys(기타·무료 등)는 회색으로 분리해 '미분류/수입 무관'을 시각 구분."""
    data = [(k, v) for k, v in data_dict.items() if v and v > 0]
    if len(data) < 2:
        return ""
    data.sort(key=lambda kv: kv[1], reverse=True)
    total = sum(v for _, v in data) or 1
    vmax = data[0][1] or 1
    rows = "".join(
        f'<div class="hbar-row">'
        f'<div class="hbar-label">{_esc(k)}</div>'
        f'<div class="hbar-track"><div class="hbar-fill" '
        f'style="width:{v / vmax * 100:.1f}%;background:{C_ETC if k in muted_keys else C_PERF}"></div></div>'
        f'<div class="hbar-val">{v:,}{unit} <span class="hbar-pct">{v / total * 100:.0f}%</span></div>'
        f'</div>'
        for k, v in data
    )
    return (f'<div class="hbar-wrap"><div class="fig-title sm">{_esc(title)}</div>'
            f'{rows}</div>')


def _budget_revenue(budget, revenue):
    """예산·수입 구조 — 2개 가로 막대(예산/수입) + 회수율·순비용 캡션.
    한쪽이라도 억 단위면 두 값 모두 억(소수 2자리)으로 통일 표기(2.10억 / 0.98억)."""
    if not budget or budget <= 0:
        return ""
    rev = revenue or 0
    vmax = max(budget, rev) or 1
    use_eok = vmax >= 100_000_000  # 둘 중 하나라도 억 이상 → 둘 다 억으로 통일

    def fmt(v):
        v = int(v or 0)
        return f"약 {v // 1_000_000 / 100:.2f}억" if use_eok else _money_short(v)

    def bar(label, val, color):
        return (f'<div class="hbar-row">'
                f'<div class="hbar-label">{label}</div>'
                f'<div class="hbar-track"><div class="hbar-fill" '
                f'style="width:{(val or 0) / vmax * 100:.1f}%;background:{color}"></div></div>'
                f'<div class="hbar-val">{fmt(val)}</div></div>')

    # 총 예산=중립 회색(규모, 롤리팝과 동일), 총 수입=블루그레이 포인트
    bars = bar("총 사용 예산", budget, C_BASE) + bar("총 수입", rev, C_POINT)
    cap = ""
    if revenue is not None:
        cap = (f'<p class="body">예산 대비 수입(회수율) {rev / budget * 100:.1f}%, '
               f'순비용 {fmt(budget - rev)}.</p>')
    # 산점도와 한 줄에 배치(셀이 폭 제어). 작은 제목 동반.
    return (f'<div class="brc"><div class="fig-title sm">예산·수입 비율</div>'
            f'<div class="hbar-wrap">{bars}</div>{cap}</div>')


def _donut(title, data_dict, unit="점", center=None, colors=None):
    """conic-gradient 도넛 + 하단 범례. center=가운데 값 대체, colors=항목 색 지정."""
    data = [(k, v) for k, v in data_dict.items() if v and v > 0]
    if len(data) < 2:
        return ""
    total = sum(v for _, v in data)
    palette = colors or CAT
    stops, legend, acc = [], [], 0.0
    for i, (k, v) in enumerate(data):
        c = palette[i % len(palette)]
        p0 = acc / total * 100
        acc += v
        p1 = acc / total * 100
        stops.append(f"{c} {p0:.2f}% {p1:.2f}%")
        legend.append(
            f'<span class="lg"><i style="background:{c}"></i>'
            f'{_esc(k)} {v:,}{unit}</span>')
    return f"""<div class="donut-cell">
      <div class="fig-title sm">{_esc(title)}</div>
      <div class="donut" style="background:conic-gradient({','.join(stops)})">
        <div class="donut-hole">{center if center is not None else f"{total:,}{unit}"}</div>
      </div>
      <div class="legend">{''.join(legend)}</div>
    </div>"""


def _chart_pair(wide_html, narrow_html):
    """가로 막대(넓게) + 도넛(좁게)을 한 줄에 배치. 한쪽만 있으면 그대로 반환."""
    if wide_html and narrow_html:
        return (f'<div class="chart-pair">'
                f'<div class="cp-wide">{wide_html}</div>'
                f'<div class="cp-narrow">{narrow_html}</div></div>')
    return wide_html or narrow_html or ""


def _svg_weekly(weekly, ref_lines):
    """주차별 관객 추이 인라인 SVG 라인 + 비교 기준선."""
    if not weekly or len(weekly) < 2:
        return ""
    weeks = list(weekly.keys())
    vals = [float(v) for v in weekly.values()]
    N = len(vals)
    STEP = 66                           # 1주당 고정 가로 간격(viewBox 단위)
    padL, padR, padT, padB = 44, 16, 20, 28
    MAXW = padL + 10 * STEP + padR      # 11주 기준 전체 폭(=720)
    W, H = padL + (N - 1) * STEP + padR, 240
    refs = [(float(v), lbl) for (v, lbl, _c) in (ref_lines or []) if v]
    vmax = max(vals + [v for v, _ in refs] + [1]) * 1.12
    ih = H - padT - padB

    def X(i):
        return padL + i * STEP

    def Y(v):
        return padT + ih * (1 - v / vmax)

    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    area = f"{padL},{padT+ih} " + pts + f" {X(N-1):.1f},{padT+ih}"
    dots = "".join(
        f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.5" fill="#fff" '
        f'stroke="{ACCENT}" stroke-width="2"/>' for i, v in enumerate(vals))
    refsvg = ""
    rcolors = [C_BASE, C_POINT]   # 평균/기준선=중립 회색, 보조=블루그레이 포인트
    for j, (v, lbl) in enumerate(refs):
        y = Y(v)
        c = rcolors[j % 2]
        refsvg += (
            f'<line x1="{padL}" y1="{y:.1f}" x2="{W-padR}" y2="{y:.1f}" '
            f'stroke="{c}" stroke-width="1.2" stroke-dasharray="5 4"/>'
            f'<text x="{W-padR}" y="{y-4:.1f}" text-anchor="end" '
            f'font-size="11" fill="{c}">{_esc(lbl)} {v:,.0f}</text>')
    xlabels = "".join(
        f'<text x="{X(i):.1f}" y="{H-8}" text-anchor="middle" font-size="10" '
        f'fill="{MUTED}">{_esc(w)}</text>'
        for i, w in enumerate(weeks))
    # 주가 11(최대) 미만이면 폭이 그만큼 줄고 가운데 정렬 → 1주 폭은 항상 동일
    width_pct = min(100.0, W / MAXW * 100)
    return f"""<svg viewBox="0 0 {W} {H}" class="svgchart" style="width:{width_pct:.1f}%" preserveAspectRatio="xMidYMid meet">
      <polygon points="{area}" fill="{ACCENT}" opacity="0.10"/>
      {refsvg}
      <polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="2.2"/>
      {dots}{xlabels}
    </svg>"""


def _scatter(data):
    """예산·관객 분포 산점도 — 모든 전시(회색 점) + 본 전시(네이비, 같은 크기·색만 다름).
    제목 + 평균 십자선 + 효율영역 틴트. 축 끝 스케일 앵커 + 본 전시 라벨.
    SVG 텍스트는 주차별 차트 라벨과 같은 렌더 크기가 되도록 viewBox 폰트 19 사용."""
    pts = (data or {}).get("points") or []
    cur = (data or {}).get("current")
    if len(pts) < 4:
        return ""
    W, H = 440, 300
    padL, padR, padT, padB = 18, 18, 28, 28
    LBLF = 19   # viewBox 폰트(작은 차트라 크게 잡아야 주차 라벨과 같은 렌더 크기)
    iw, ih = W - padL - padR, H - padT - padB
    xs = [p[0] for p in pts] + ([cur[0]] if cur else [])
    ys = [p[1] for p in pts] + ([cur[1]] if cur else [])
    xmax = max(xs) * 1.12
    ymax = max(ys) * 1.12
    avb = sum(p[0] for p in pts) / len(pts)
    avv = sum(p[1] for p in pts) / len(pts)

    def X(x):
        return padL + iw * (x / xmax)

    def Y(y):
        return padT + ih * (1 - y / ymax)

    tint = (f'<rect x="{padL}" y="{Y(ymax):.1f}" width="{X(avb)-padL:.1f}" '
            f'height="{Y(avv)-Y(ymax):.1f}" fill="{ACCENT}" opacity="0.05"/>')
    axis = (f'<line x1="{padL}" y1="{padT}" x2="{padL}" y2="{H-padB}" stroke="{LINE}"/>'
            f'<line x1="{padL}" y1="{H-padB}" x2="{W-padR}" y2="{H-padB}" stroke="{LINE}"/>')
    avg = (f'<line x1="{X(avb):.1f}" y1="{padT}" x2="{X(avb):.1f}" y2="{H-padB}" '
           f'stroke="{C_BASE}" stroke-dasharray="4 4" stroke-width="1"/>'
           f'<line x1="{padL}" y1="{Y(avv):.1f}" x2="{W-padR}" y2="{Y(avv):.1f}" '
           f'stroke="{C_BASE}" stroke-dasharray="4 4" stroke-width="1"/>')
    # 모든 점 동일 크기. 본 전시는 색(네이비)만 다르고 '이번 전시' 라벨 부착.
    R = 5
    dots = "".join(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{R}" fill="{C_ETC}"/>'
                   for x, y in pts)
    curdot = ""
    if cur:
        cx, cy = X(cur[0]), Y(cur[1])
        if cx > W * 0.55:
            anchor, lx = "end", cx - R - 6
        else:
            anchor, lx = "start", cx + R + 6
        curdot = (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R}" fill="{C_POINT}"/>'
                  f'<text x="{lx:.1f}" y="{cy+LBLF*0.35:.1f}" text-anchor="{anchor}" '
                  f'font-size="{LBLF}" font-weight="700" fill="{C_POINT}">이번 전시</text>')
    # 축 끝 스케일 앵커(데이터 최댓값 반올림): x=억 원, y=만 명
    xlab = (f'<text x="{W-padR}" y="{H-9}" text-anchor="end" font-size="{LBLF}" '
            f'fill="{MUTED}">{round(xmax/100_000_000)}억 원</text>')
    ylab = (f'<text x="{padL}" y="{padT-10}" text-anchor="start" font-size="{LBLF}" '
            f'fill="{MUTED}">{round(ymax/10_000)}만 명</text>')
    return (f'<div class="scatter-wrap"><div class="fig-title sm">예산·관객 분포 (역대 전시)</div>'
            f'<svg viewBox="0 0 {W} {H}" class="scatterchart" preserveAspectRatio="xMidYMid meet">'
            f'{tint}{axis}{avg}{dots}{curdot}{xlab}{ylab}</svg></div>')


def _section(title, body, num=None):
    if not body:
        return ""
    head = f'{num}. {title}' if num else title
    return f'<div class="card"><div class="sec-title">{_esc(head)}</div>{body}</div>'


def _para(text):
    if not text:
        return ""
    paras = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    return "".join(f'<p class="body">{_esc(p)}</p>' for p in paras)


def _table(headers, rows, raw_cols=(), col_widths=None):
    """간단 표 HTML. raw_cols에 든 열 인덱스는 이스케이프하지 않음(HTML 그대로 삽입).

    col_widths: 열별 고정 너비 리스트(빈 문자열=자동). 주면 table-layout:fixed로
    렌더되어, 같은 col_widths를 쓰는 여러 표의 열 경계가 정확히 일치한다.
    """
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        return ""
    cls = "tbl tbl-fixed" if col_widths else "tbl"
    cg = ""
    if col_widths:
        cg = "<colgroup>" + "".join(
            (f'<col style="width:{w}">' if w else "<col>") for w in col_widths
        ) + "</colgroup>"
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    trs = "".join(
        "<tr>" + "".join(
            f"<td>{c if j in raw_cols else _esc(c)}</td>" for j, c in enumerate(r)
        ) + "</tr>"
        for r in rows)
    return (f'<table class="{cls}">{cg}'
            f'<thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>')


def _kv(pairs):
    """라벨·값 목록(개요용). pairs=[(label, value), ...] 빈 값 제외."""
    items = [(k, v) for k, v in pairs if v not in (None, "", [])]
    if not items:
        return ""
    rows = "".join(
        f'<div class="kv"><span class="k">{_esc(k)}</span>'
        f'<span class="v">{_esc(v)}</span></div>' for k, v in items)
    return f'<div class="kvlist">{rows}</div>'


def _subhead(text):
    return f'<div class="subhead">{_esc(text)}</div>'


def _imgcell(uri, ratio, cls=""):
    """이미지 칸 1개. uri가 있으면 실제 사진(object-fit:cover), 없으면 placeholder.
    ratio는 CSS aspect-ratio('가로 / 세로'). cls로 sizing 클래스(plan/thumb 등) 부여."""
    extra = (" " + cls) if cls else ""
    if uri:
        return (f'<div class="imgph has-img{extra}" style="aspect-ratio:{ratio}">'
                f'<img src="{uri}" alt=""></div>')
    return (f'<div class="imgph{extra}" style="aspect-ratio:{ratio}">'
            f'<span class="imgph-label">image</span></div>')


def _thumb(uri=None):
    """표 안 섬네일 (인쇄물·굿즈 등). 세로형 3:4. 사진 없으면 placeholder."""
    return _imgcell(uri, "3 / 4", "imgph-thumb")


def _img_grid(images=None, empty=2, ratio="4 / 3"):
    """한 줄에 2개씩(2열) 배치. 업로드된 사진이 있으면 그 장수만큼 동적 배치,
    없으면 empty개 placeholder(자리 표시). 콘텐츠 이미지는 가로형 4:3."""
    images = [u for u in (images or []) if u]
    if images:
        boxes = "".join(_imgcell(u, ratio) for u in images)
    else:
        boxes = "".join(_imgcell(None, ratio) for _ in range(empty))
    return f'<div class="imgph-grid2">{boxes}</div>'


def _space_block(name, floor_img=None, photo_imgs=None):
    """전시 공간 1개: 도면(세로형 9:16, 1장, 가운데) + 전경(2열 동적, 가로형).
    공간 이름을 머리로 표시. 사진 없으면 placeholder(전경 기본 4칸)."""
    plan = _imgcell(floor_img, "9 / 16", "imgph-plan")
    photo_imgs = [u for u in (photo_imgs or []) if u]
    grid = _img_grid(photo_imgs, empty=4)
    return (f'<div class="space-block">'
            f'<div class="space-name">{_esc(name)}</div>'
            f'<div class="imgph-plangrid">{plan}</div>'
            f'{grid}'
            f'</div>')


def _insights_html(data, section_key):
    """해당 섹션의 분석 서술 — LLM 산문 우선, 없으면 룰 기반 불릿(Word와 동일 규칙)."""
    llm = (data.get("llm_sections", {}) or {}).get(section_key, "")
    if llm and llm.strip():
        return _para(llm)
    items = data.get("section_insights", {}).get(section_key, [])
    if not items:
        return ""
    lis = "".join(f'<li>{_esc(i.get("text",""))}</li>' for i in items if i.get("text"))
    return f'<ul class="ins">{lis}</ul>' if lis else ""


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def build_report_html(data):
    """전체 data dict → self-contained HTML 문서. Word 보고서(I~VI)를 그대로 미러링.

    동일 내용·동일 차트 디자인(롤리팝·도넛·주차 SVG)으로 Word와 일치.
    """
    ov = data.get("overview", {})
    title = ov.get("title") or data.get("exhibition_title") or "(제목 미입력)"
    period = ov.get("period", "")
    artists = ov.get("artists", [])
    artists_str = ", ".join(artists) if isinstance(artists, list) else str(artists)

    # ── 헤더 ──
    header_html = f"""<div class="rep-head">
      <div class="eyebrow">Ilmin Museum of Art</div>
      <div class="rep-title">《{_esc(title)}》</div>
      <div class="rep-meta">{_esc(period)}</div>
    </div>"""

    # ── I. 전시 개요 ──
    sec_overview = _section("전시 개요", _kv([
        ("전시 제목", f"《{title}》"), ("전시 기간", period),
        ("참여 작가", artists_str),
        ("책임기획", ov.get("chief_curator")), ("기획", ov.get("curators")),
        ("진행", ov.get("coordinators")), ("학예팀", ov.get("curatorial_team")),
        ("홍보", ov.get("pr")), ("후원", ov.get("sponsors")),
        ("총 사용 예산", ov.get("total_budget")),
        ("총 수입", ov.get("total_revenue")),
        ("총 관객수", ov.get("visitors")),
    ]), num="I")

    # ── III. 전시 주제와 내용 ──
    sec_theme = _section("전시 주제와 내용", _para(data.get("theme_text", "")), num="III")

    # ── III. 전시 구성 ──
    iii = []
    rooms = data.get("rooms", [])
    # 공간별 (이름, 도면 이미지, 전경 이미지들) — 없으면 이름만 fallback
    if rooms:
        space_items = [((r.get("name") or f"{i+1}전시실"),
                        r.get("floor_plan_img"), (r.get("photo_imgs") or []))
                       for i, r in enumerate(rooms)]
    else:
        space_items = [(n, None, []) for n in ("1전시실", "2전시실", "3전시실")]
    # 1) 출품 작품 구성 (도넛 2-up) — 가장 먼저
    art = data.get("artworks", {})
    media = {"회화": art.get("painting", 0), "조각": art.get("sculpture", 0),
             "사진": art.get("photo", 0), "설치": art.get("installation", 0),
             "미디어": art.get("media", 0), "기타": art.get("other", 0)}
    # 매체(6항목)는 가로 막대로 — 도넛보다 수량 비교가 빠름. 신작·구작(2항목)은 도넛 유지.
    media_bar = _hbar("출품 매체 구성", media, "점", muted_keys={"기타"})
    nw, od = art.get("new", 0) or 0, art.get("old", 0) or 0
    nb_donut = _donut("신작·구작 구성", {"신작": nw, "구작": od}, "점")
    if media_bar or nb_donut:
        iii.append(_subhead("출품 작품 구성"))
        iii.append(_chart_pair(media_bar, nb_donut))
        total = art.get("total", 0)
        if any(media.values()) and total:
            top = max(media.items(), key=lambda kv: kv[1])
            cap = (f"출품작 {total}점의 매체 구성은 {top[0]}({top[1]}점, "
                   f"{top[1]/total*100:.0f}%) 비중이 가장 큼.")
            if nw or od:
                cap += f" 신작 {nw}점, 구작 {od}점."
            iii.append(f'<p class="body">{_esc(cap)}</p>')
    # 2) 전시 도면 · 전경 — 공간별로 도면 1개(세로형) + 전경 2×2(4개)
    #    (전시실→참여 작가 표는 불필요하여 제거)
    iii.append(_subhead("전시 도면 및 전경"))
    for name, floor_img, photo_imgs in space_items:
        iii.append(_space_block(name, floor_img, photo_imgs))
    # 프로그램 — 표 + 설명(구성 분석 서술)을 '전시 연계 프로그램' 밑에 배치
    progs = data.get("related_programs", [])
    comp_ins = _insights_html(data, "composition")
    if progs or comp_ins:
        iii.append(_subhead("전시 연계 프로그램"))
        if progs:
            iii.append(_table(["구분", "제목", "참여 인원", "비고"],
                              [[p.get("category", ""), p.get("title", ""),
                                p.get("participants", ""), p.get("note", "")] for p in progs]))
        if comp_ins:
            iii.append(comp_ins)
        prog_imgs = data.get("program_photo_imgs") or []
        if progs or prog_imgs:
            iii.append(_img_grid(prog_imgs, empty=2))
    # 인쇄물 — 표 맨 왼쪽 칸에 행별 섬네일(업로드 시 실제 사진, 없으면 placeholder)
    mats = data.get("printed_materials", [])
    if mats:
        iii.append(_subhead("인쇄물 및 굿즈"))
        iii.append(_table(["이미지", "종류", "수량", "비고"],
                          [[_thumb(m.get("image_img")), m.get("type", ""),
                            m.get("quantity", ""), m.get("note", "")] for m in mats],
                          raw_cols={0}))
    sec_compose = _section("전시 구성", "".join(iii), num="IV")

    # ── IV. 전시 결과 ──
    iv = []
    rev = data.get("revenue", {})
    # 전시 결과는 '약'이 아닌 정확한 금액(원 단위)으로 표기.
    # analysis_data_flat의 원시 숫자로 렌더 시점에 계산 → 재생성 없이도 정확액 반영.
    _b = data.get("budget", {})
    _adf = data.get("analysis_data_flat", {})

    def _won(x, fb):
        try:
            return f"{int(x):,}원" if x else fb
        except (TypeError, ValueError):
            return fb

    iv.append(_kv([
        ("총 사용 예산", _won(_adf.get("총 사용 예산"),
                          _b.get("total_spent_won") or _b.get("total_spent"))),
        ("총 수입", _won(_adf.get("총수입"),
                      rev.get("total_revenue_won") or rev.get("total_revenue"))),
        ("총 관객수", rev.get("total_visitors")),
        ("일평균 관객", rev.get("daily_average")),
    ]))
    # 예산·수입 구조 (신규) — 재정 구조를 서술이 아닌 막대로
    adf = data.get("analysis_data_flat", {})
    br = _budget_revenue(adf.get("총 사용 예산"), adf.get("총수입"))
    sc = _scatter(data.get("scatter"))   # 산점도(역대 전 전시 위치)
    # 예산·수입 막대 + 산점도를 한 줄에. 한쪽만 있으면 단독(좁게 가운데).
    if br and sc:
        iv.append(f'<div class="fin-row"><div class="fin-cell">{br}</div>'
                  f'<div class="fin-cell">{sc}</div></div>')
    elif br:
        iv.append(f'<div class="br-solo">{br}</div>')
    elif sc:
        iv.append(sc)
    # 주차별 추이 SVG
    vc = data.get("visitor_composition", {})
    weekly = vc.get("weekly_visitors", {})
    comp = data.get("comparison", {})
    svg = _svg_weekly(weekly, comp.get("weekly_ref"))
    if svg:
        iv.append(_subhead("주차별 관객 추이"))
        iv.append(svg)
        peak = max(weekly, key=weekly.get)
        wcap = f"주차별 관객은 {peak}에 최고 {max(weekly.values()):,}명을 기록함."
        wref = comp.get("weekly_ref", [])
        if wref:
            wcap += " 점선은 " + ", ".join(
                f"{lbl} 주당 {v:,.0f}명" for v, lbl, _ in wref) + "."
        iv.append(f'<p class="body">{_esc(wcap)}</p>')
    # 입장권 + 유료무료 도넛
    tt = vc.get("ticket_type", {})
    if tt:
        free = tt.get("초대권", 0) or 0
        paid = sum(v for k, v in tt.items() if k != "초대권")
        # 입장권별(5항목)은 가로 막대. 유료·무료(2항목)는 도넛 유지(중앙값=총량).
        ticket_bar = _hbar("입장권별 관객 구성", tt, "명", muted_keys={"초대권"})
        # 유료=성과 녹색, 무료·초대=회색(수입 무관) — 컬러로 수입 구조를 구분
        pf_donut = _donut("유료·무료 비율", {"유료": paid, "무료·초대": free}, "명",
                          colors=[C_PERF, C_ETC])
        if ticket_bar or pf_donut:
            iv.append(_subhead("관객 구성"))
            iv.append(_chart_pair(ticket_bar, pf_donut))
            top = max(tt, key=tt.get)
            tt_total = sum(tt.values()) or 1
            cap = (f"입장권별로는 {top}이(가) {tt[top]:,}명"
                   f"({tt[top]/tt_total*100:.0f}%)으로 가장 큼.")
            if paid + free:
                cap += f" 유료 관객 {paid:,}명({paid/(paid+free)*100:.0f}%)."
            iv.append(f'<p class="body">{_esc(cap)}</p>')
    iv.append(_insights_html(data, "results"))
    sec_results = _section("전시 결과", "".join(iv), num="V")

    # ── V. 홍보 방식 및 언론 보도 ──
    v = []
    promo = data.get("promotion", {})
    promo_rows = [(lbl, promo.get(k, "")) for k, lbl in
                  [("advertising", "광고"), ("press_release", "보도자료"),
                   ("web_invitation", "웹 초청장"), ("newsletter", "뉴스레터"),
                   ("sns", "SNS"), ("other", "그 외")] if promo.get(k)]
    if promo_rows:
        v.append(_subhead("홍보 방식"))
        v.append(_kv(promo_rows))
    press = data.get("press_coverage", {})
    pm = press.get("print_media", [])
    if pm:
        v.append(_subhead("일간지·월간지"))
        v.append(_table(["매체명", "일자", "제목", "비고"],
                        [[p.get("outlet", ""), p.get("date", ""), p.get("title", ""),
                          p.get("note", "")] for p in pm]))
    om = press.get("online_media", [])
    if om:
        v.append(_subhead("온라인 매체"))
        v.append(_table(["매체명", "일자", "제목", "URL"],
                        [[p.get("outlet", ""), p.get("date", ""), p.get("title", ""),
                          p.get("url", "")] for p in om]))
    if data.get("membership"):
        v.append(_subhead("멤버십 커뮤니케이션"))
        v.append(_para(data.get("membership")))
    # 홍보물·언론 보도 캡처 (업로드 장수만큼 동적, 없으면 placeholder 2칸)
    v.append(_subhead("홍보물·언론 보도"))
    v.append(_img_grid(data.get("promo_photo_imgs") or [], empty=2))
    v.append(_insights_html(data, "promotion"))
    # 관객 후기 — 긍정/부정/기타 3개 표 (해당 후기가 있는 분류만; 기타는 없을 수 있음)
    reviews = [r for r in (data.get("visitor_reviews") or []) if r.get("content")]
    if reviews:
        v.append(_subhead("관객 후기"))
        for cat in ("긍정", "부정", "기타"):
            crows = [[r.get("content", ""), r.get("source", "")]
                     for r in reviews if (r.get("category") or "기타") == cat]
            if crows:
                v.append(f'<div class="space-name">{_esc(cat)}</div>')
                # 세 표(긍정/부정/기타)의 '출처' 열을 동일 너비로 고정 → 가로 위치 일치
                v.append(_table(["내용", "출처"], crows, col_widths=["", "112px"]))
    sec_promo = (_section("커뮤니케이션", "".join(v), num="VI")
                 if "".join(v).strip() else "")

    # ── VI. Executive Summary ──
    vi = []
    lp = _lollipop(data.get("summary_metrics", []))
    if lp:
        vi.append(lp)  # _lollipop은 자체 card이므로 그대로
    vi.append(_subhead("종합 의견"))
    vi.append(_insights_html(data, "evaluation") or '<p class="body">—</p>')
    aud = _insights_html(data, "audience_response")
    if aud:
        vi.append(_subhead("관객 반응 종합"))
        vi.append(aud)
    # 데이터 도출 평가 항목
    ev = data.get("evaluation", {})
    for key, label in [("positive", "긍정 평가"), ("negative", "부정 평가"),
                       ("improvements", "개선 방안")]:
        vals = ev.get(key, [])
        if vals:
            vi.append(_subhead(label))
            vi.append('<ul class="ins">' +
                      "".join(f"<li>{_esc(x)}</li>" for x in vals) + "</ul>")
    sec_exec = _section("Executive Summary", "".join(vi), num="II")

    # 포스터(세로형, 1장) — 1페이지 상단. 업로드 시 실제 포스터, 없으면 placeholder.
    poster_img = data.get("poster_img")
    if poster_img:
        poster = (f'<div class="imgph has-img poster-ph">'
                  f'<img src="{poster_img}" alt=""></div>')
    else:
        poster = ('<div class="imgph poster-ph">'
                  '<span class="imgph-label">image</span></div>')
    # 보고서 순서: I 전시 개요 → II Executive Summary → III 주제 → IV 구성 → V 결과 → VI 홍보
    # 앞 2페이지 고정: 1p = 포스터 + I 전시 개요, 2p = II Executive Summary,
    # 3p부터는 페이지네이션 강제 없이 자연 흐름.
    parts = [
        # 1p = 헤더 + 세로형 포스터 + I 전시 개요 (한 페이지 고정, 포스터가 남는
        # 공간을 채우거나 개요가 커지면 줄어들어 한 페이지를 넘지 않음)
        f'<div class="rep-page rep-page-1">{header_html}{poster}{sec_overview}</div>',
        f'<div class="rep-page rep-page-2">{sec_exec}</div>',
        sec_theme, sec_compose, sec_results, sec_promo,
        '<div class="rep-end">끝.</div>',   # 문서 종료 — 두 줄 띄고 왼쪽 정렬
    ]
    body = "\n".join(b for b in parts if b)
    return _DOC.replace("{{BODY}}", body)


# ──────────────────────────────────────────────
# 문서 셸 + 스타일
# ──────────────────────────────────────────────

_DOC = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<style>
/* 인쇄/PDF에서도 배경(도넛 conic-gradient·롤리팝·표 헤더 등)이 출력되도록 강제 */
* { box-sizing: border-box;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; color-adjust: exact; }
html, body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin:0; background:#f4f6f2; color:#20231f;
  font-family: -apple-system, "Noto Sans KR", "Malgun Gothic", sans-serif; }
.report { max-width: 860px; margin: 0 auto; padding: 24px 16px 60px; }
/* ── 편집 위계(통일) ──
   1) 전시명(rep-title) = 유일한 최대 강조
   2) 섹션(sec-title) 16/600  3) 소제목(subhead) 13/600
   4) 본문 14/400  5) 캡션·보조 12/400 muted
   볼드는 '전시명·섹션·소제목·데이터 값·표 머리글'에만. 나머지는 regular. */
.rep-head { padding: 6px 2px 16px; border-bottom: 1.5px solid #255c4a; margin-bottom: 22px; }
.eyebrow { color:#255c4a; font-size:11px; font-weight:600; letter-spacing:.12em; }
.rep-title { font-size:23px; font-weight:700; margin:6px 0 4px; letter-spacing:-.01em; color:#20231f; }
.rep-meta { color:#8a918a; font-size:12.5px; }
.card { background:#fff; border:1px solid #e8ebe5; border-radius:10px;
  padding:20px 22px; margin-bottom:16px; box-shadow:0 1px 2px rgba(32,35,31,.03); }
.fig-title { font-size:13px; font-weight:600; color:#3c403a; margin-bottom:4px; }
.fig-title.sm { font-size:12px; text-align:center; margin-bottom:10px; color:#646b61; }
.fig-sub { font-size:12px; color:#9aa39a; margin-bottom:18px; font-weight:400; }
.body { font-size:13.5px; line-height:1.7; color:#3c403a; margin:10px 0 0; font-weight:400; }
.sec-title { font-size:16px; font-weight:600; color:#255c4a; margin-bottom:14px;
  padding-bottom:7px; border-bottom:1px solid #e8ebe5; letter-spacing:-.01em; }
.subhead { font-size:13px; font-weight:600; color:#3c403a; margin:18px 0 8px; }
.kvlist { display:grid; grid-template-columns:1fr 1fr; gap:5px 24px; }
@media (max-width:560px){ .kvlist{ grid-template-columns:1fr; } }
.kv { display:flex; gap:10px; font-size:13px; padding:3px 0;
  border-bottom:1px dotted #eef1ec; }
.kv .k { color:#9aa39a; min-width:90px; font-weight:400; }
.kv .v { color:#20231f; font-weight:400; min-width:0; overflow-wrap:anywhere; }
.tbl { width:100%; max-width:100%; border-collapse:collapse; font-size:13px; margin:6px 0; }
.tbl th { background:#f1f4ee; color:#4a5450; font-weight:600; text-align:left;
  padding:7px 10px; border-bottom:1px solid #e3e7df; }
.tbl td { padding:7px 10px; border-bottom:1px solid #eef1ec; color:#3c403a;
  vertical-align:middle; }
/* 긴 URL·제목 등이 줄바꿈 없이 표를 페이지보다 넓게 늘려 인쇄 시 전체가
   축소(가로 좁아짐)되는 것을 방지 — 모든 셀에서 강제 줄바꿈 허용 */
.tbl th, .tbl td { overflow-wrap:anywhere; word-break:break-word; }
/* 고정 레이아웃 표 — 같은 col_widths끼리 열 경계 정렬(예: 후기 '출처' 열) */
.tbl-fixed { table-layout:fixed; }
.tbl-fixed th, .tbl-fixed td { overflow-wrap:break-word; word-break:break-word; }
.ins { margin:8px 0 0; padding-left:20px; }
.ins li { font-size:13.5px; line-height:1.65; color:#3c403a; margin:4px 0; }

/* 롤리팝 */
.lolli-wrap { position:relative; padding-top:22px; }
/* 눈금 행을 트랙(라벨 170px + gap 14px = 184px) 위로 정렬 → '100'이 기준선 바로 위 */
.lolli-scale { position:relative; height:16px; margin:0 0 8px 184px;
  color:#9aa39a; font-size:11px; }
.lolli-scale span { position:absolute; transform:translateX(-50%); }
.lolli { display:grid; grid-template-columns:170px 1fr; align-items:center;
  gap:14px; margin:7px 0; }
.lolli-label { font-size:13px; font-weight:600; line-height:1.3; color:#3c403a; }
.lolli-label .cap { display:block; font-size:11px; font-weight:400; color:#9aa39a; }
.lolli-track { position:relative; height:22px; }
.lolli-track::before { content:""; position:absolute; top:50%; left:0; right:0;
  height:5px; transform:translateY(-50%); background:#eef1ec; border-radius:3px; }
.lolli-base { position:absolute; top:-2px; bottom:-2px; width:0;
  border-left:1px dashed #9aa39a; }
.lolli-seg { position:absolute; top:50%; height:5px; transform:translateY(-50%);
  border-radius:3px; }
.lolli-dot { position:absolute; top:50%; width:13px; height:13px; border-radius:50%;
  transform:translate(-50%,-50%); border:2px solid #fff; }
.lolli-val { position:absolute; top:-16px; transform:translateX(-50%);
  font-size:12px; font-weight:700; }

/* 도넛 */
.donut-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
@media (max-width:560px){ .donut-grid{ grid-template-columns:1fr; } }
/* 사진 placeholder 박스 — 실제 보고서에서 사진이 들어갈 자리 */
.imgph-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr));
  gap:10px; margin:18px 0 22px; }
.imgph { border:1.5px dashed #c2ccc2; border-radius:6px; background:#f5f7f4;
  display:flex; align-items:center; justify-content:center; }
.imgph-label { font-size:11.5px; color:#9aa39a; letter-spacing:0.3px; text-align:center; }
/* 실제 사진이 들어간 칸 — 박스를 꽉 채우되 가장자리 잘림(cover), 비율 유지 */
.imgph.has-img { border:1px solid #e3e7df; background:#fff; padding:0; overflow:hidden; }
.imgph.has-img img { width:100%; height:100%; object-fit:cover; display:block; }
/* 전시 전경 — 한 줄에 2개씩(2열) */
/* 한 줄 2개 이미지(3:4) — 90% 폭으로 10% 축소 + 가운데 정렬 */
.imgph-grid2 { display:grid; grid-template-columns:repeat(2, 1fr); gap:10px;
  margin:18px auto 22px; max-width:90%; }
@media (max-width:520px){ .imgph-grid2{ grid-template-columns:1fr; } }
/* 전시 도면 — 세로형(9:16) 박스, 가운데 정렬 */
.imgph-plangrid { display:flex; flex-wrap:wrap; justify-content:center;
  gap:12px; margin:16px 0 12px; }
.imgph-plan { width:189px; max-width:43%; }  /* 도면 박스 — 기존比 10% 축소 */
/* 표 안 섬네일 (인쇄물·굿즈) — 세로형 3:4, 1.5배 확대, 셀 안 가운데 정렬 */
.imgph-thumb { width:117px; margin:0 auto; }
.imgph-thumb .imgph-label { font-size:10px; }
/* 전시 공간 블록 (공간별 도면+전경) */
.space-block { margin:10px 0 24px; }
.space-name { font-size:13px; font-weight:600; color:#3c403a; margin:12px 0 6px; }
/* 문서 종료 표시 — 두 줄 띄고 왼쪽 정렬 */
.rep-end { margin-top:2.6rem; text-align:left; font-size:13.5px; color:#3c403a; }
/* 앞 2페이지 고정 레이아웃 + 세로형 포스터 자리 */
.rep-page-1 { display:flex; flex-direction:column; }
.poster-ph { width:100%; max-width:340px; align-self:center; min-height:440px;
  flex:0 0 auto; margin-bottom:6px; }
.donut-cell { text-align:center; }
.donut { position:relative; width:170px; height:170px; border-radius:50%;
  margin:0 auto; }
.donut::after { content:""; position:absolute; inset:26%; background:#fff;
  border-radius:50%; }
.donut-hole { position:absolute; inset:0; display:flex; align-items:center;
  justify-content:center; font-size:17px; font-weight:800; color:#20231f; z-index:1; }
/* 막대(넓게)+도넛(좁게) 한 줄 배치 — 도넛이 더 작은 영역 차지 */
.chart-pair { display:grid; grid-template-columns:1.7fr 1fr; gap:22px;
  align-items:center; margin:8px 0 2px; }
.chart-pair .cp-narrow .donut { width:124px; height:124px; }
.chart-pair .cp-narrow .donut-hole { font-size:13px; }
.chart-pair .cp-narrow .legend { font-size:11px; margin-top:8px; gap:3px 10px; }
@media (max-width:560px){ .chart-pair{ grid-template-columns:1fr; } }
/* 가로 막대그래프 (구성·예산수입) — 라벨 우측정렬 / 막대 / 값+비율 */
.hbar-wrap { margin:8px 0 4px; }
.hbar-row { display:grid; grid-template-columns:92px 1fr 108px; align-items:center;
  gap:10px; margin:7px 0; }
.hbar-label { font-size:12px; color:#3c403a; text-align:right; line-height:1.3; }
.hbar-track { background:#eef1ec; border-radius:3px; height:15px; overflow:hidden; }
.hbar-fill { background:#255c4a; height:100%; border-radius:3px; min-width:2px; }
.hbar-val { font-size:12px; color:#3c403a; white-space:nowrap; }
.hbar-pct { color:#8a918a; margin-left:3px; }
@media (max-width:520px){ .hbar-row{ grid-template-columns:70px 1fr 92px; } }
/* 예산·수입 블록 — 불필요하게 길지 않게 좁혀서 가운데 정렬 */
/* 예산·수입 막대 + 산점도 한 줄 배치 */
.fin-row { display:grid; grid-template-columns:1.3fr 0.7fr; gap:24px;
  align-items:center; margin:10px 0 2px; }
.fin-cell { min-width:0; }
.fin-cell .scatter-wrap { max-width:100%; margin:2px 0; }
.brc .hbar-row { grid-template-columns:74px 1fr 90px; }   /* 좁은 셀용 컬럼 축소 */
.br-solo { max-width:62%; margin:0 auto; }
@media (max-width:560px){ .fin-row{ grid-template-columns:1fr; } .br-solo{ max-width:100%; } }
.legend { display:flex; flex-wrap:wrap; justify-content:center; gap:4px 14px;
  margin-top:12px; font-size:12px; color:#3c403a; }
.legend .lg { display:inline-flex; align-items:center; gap:5px; white-space:nowrap; }
.legend i { width:10px; height:10px; border-radius:2px; display:inline-block; }

/* SVG — 폭은 인라인 style(주차 수 비례)로 지정, 좁으면 가운데 정렬 */
.svgchart { width:100%; height:auto; display:block; margin:0 auto; }
/* 산점도 — 작게/가운데(너무 두드러지지 않게) */
.scatter-wrap { max-width:380px; margin:12px auto 4px; }
.scatterchart { width:100%; height:auto; display:block; }

/* 인쇄용 툴바 */
.toolbar { display:flex; justify-content:flex-end; margin-bottom:14px; }
.toolbar button { background:#255c4a; color:#fff; border:none; border-radius:8px;
  padding:9px 16px; font-size:13px; font-weight:600; cursor:pointer;
  font-family:inherit; }

/* ── 인쇄 / PDF 저장 최적화 ── */
@page { size: A4; margin: 16mm 14mm; }
@media print {
  /* 배경 강제 출력(도넛·롤리팝·표 헤더 등 색이 사라지지 않게) */
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  body { background:#fff; }
  /* 인쇄 레이아웃 폭을 A4 인쇄영역(210−14×2=182mm)에 정확히 고정 →
     브라우저가 화면 폭으로 레이아웃 후 페이지에 맞춰 비균등 축소(찌그러짐)하는 것을 차단.
     본문이 인쇄영역과 1:1이라 스케일 없이 그대로 출력됨. */
  html, body { width:182mm; }
  .report { width:182mm; max-width:182mm; margin:0; padding:0; }
  .no-print { display:none !important; }
  /* 섹션 카드는 한 페이지보다 클 수 있으므로 break-inside:avoid 금지
     (금지 시 큰 섹션이 통째로 다음 페이지로 밀려 앞 페이지에 큰 여백 발생).
     쪼개지면 안 되는 작은 요소(도넛·표·차트·이미지 박스)에만 적용. */
  /* 카드가 페이지 경계를 넘어 쪼개질 때, 각 페이지 조각이 자기 외곽선을
     온전히 갖도록(clone) → 페이지 끝/시작에서 테두리가 잘리지 않고 닫힘.
     (큰 섹션은 한 페이지에 못 담겨 쪼개질 수밖에 없으므로 avoid 대신 clone 사용) */
  .card { box-shadow:none; border:1px solid #e3e7df;
    -webkit-box-decoration-break:clone; box-decoration-break:clone; }
  .donut-grid, .donut-cell, .lolli, .tbl, .svgchart,
  .imgph, .space-block, .hbar-wrap, .scatter-wrap { break-inside:avoid; page-break-inside:avoid; }
  .sec-title { break-after:avoid; page-break-after:avoid; }
  /* 앞 2페이지 고정: 1p(포스터+I 전시 개요)·2p(II Executive Summary)는 각각
     한 페이지를 채우고, 다음 콘텐츠는 새 페이지에서 시작. 3p부터 자연 흐름.
     포스터(flex-grow)가 1p의 남는 세로 공간을 채워 큰 여백을 방지. */
  .rep-page { break-after:page; page-break-after:always; }
  /* 1p 고정: 헤더+포스터+개요가 정확히 한 페이지(260mm)를 채움.
     헤더·개요는 자연 높이, 포스터(flex:1 1 0)가 남는 공간을 채우거나
     개요가 커지면 줄어들어 한 페이지를 절대 넘지 않음. */
  .rep-page-1 { height:260mm; overflow:hidden; }
  .rep-page-1 > .rep-head, .rep-page-1 > .card { flex:0 0 auto; }
  .rep-page-1 .poster-ph { flex:1 1 0; min-height:0; }
  /* 2p = Executive Summary 한 페이지 채움(짧으면 하단 여백, 자르지 않음) */
  .rep-page-2 { min-height:260mm; }
}
</style></head>
<body><div class="report">
<div class="toolbar no-print"><button onclick="window.print()">인쇄 / PDF로 저장</button></div>
{{BODY}}</div></body></html>"""
