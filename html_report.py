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
ACCENT3 = "#5d7593"     # 보조 기준선 — 약간 채도 낮춘 블루
INK = "#20231f"
MUTED = "#7a827a"
LINE = "#d9ddd4"
SOFT = "#eef2ea"
# 컬러칩: 동계열(녹색–세이지–틸–토프) 저채도. 명도 교차로 인접 슬라이스 구분.
CAT = ["#2f5d4e", "#7c9c8b", "#4a7c6a", "#a7b3a0", "#5f8088", "#8c8270"]


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
        color = ACCENT if diff >= 0 else ACCENT2   # +(좋음)=녹색, -=테라코타
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


def _donut(title, data_dict, unit="점"):
    """conic-gradient 도넛 + 하단 범례."""
    data = [(k, v) for k, v in data_dict.items() if v and v > 0]
    if len(data) < 2:
        return ""
    total = sum(v for _, v in data)
    stops, legend, acc = [], [], 0.0
    for i, (k, v) in enumerate(data):
        c = CAT[i % len(CAT)]
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
        <div class="donut-hole">{total:,}{unit}</div>
      </div>
      <div class="legend">{''.join(legend)}</div>
    </div>"""


def _svg_weekly(weekly, ref_lines):
    """주차별 관객 추이 인라인 SVG 라인 + 비교 기준선."""
    if not weekly or len(weekly) < 2:
        return ""
    weeks = list(weekly.keys())
    vals = [float(v) for v in weekly.values()]
    W, H = 720, 240
    padL, padR, padT, padB = 44, 16, 20, 28
    refs = [(float(v), lbl) for (v, lbl, _c) in (ref_lines or []) if v]
    vmax = max(vals + [v for v, _ in refs] + [1]) * 1.12
    iw, ih = W - padL - padR, H - padT - padB

    def X(i):
        return padL + (iw * i / (len(vals) - 1) if len(vals) > 1 else 0)

    def Y(v):
        return padT + ih * (1 - v / vmax)

    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    area = f"{padL},{padT+ih} " + pts + f" {X(len(vals)-1):.1f},{padT+ih}"
    dots = "".join(
        f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.5" fill="#fff" '
        f'stroke="{ACCENT}" stroke-width="2"/>' for i, v in enumerate(vals))
    refsvg = ""
    rcolors = [ACCENT2, ACCENT3]
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
        for i, w in enumerate(weeks) if i % max(1, len(weeks)//8) == 0)
    return f"""<svg viewBox="0 0 {W} {H}" class="svgchart" preserveAspectRatio="xMidYMid meet">
      <polygon points="{area}" fill="{ACCENT}" opacity="0.10"/>
      {refsvg}
      <polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="2.2"/>
      {dots}{xlabels}
    </svg>"""


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


def _table(headers, rows, raw_cols=()):
    """간단 표 HTML. raw_cols에 든 열 인덱스는 이스케이프하지 않음(HTML 그대로 삽입)."""
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        return ""
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    trs = "".join(
        "<tr>" + "".join(
            f"<td>{c if j in raw_cols else _esc(c)}</td>" for j, c in enumerate(r)
        ) + "</tr>"
        for r in rows)
    return f'<table class="tbl"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


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


def _thumb():
    """표 안 섬네일 placeholder (인쇄물·굿즈 등). 세로형 3:4, 캡션 'image'."""
    return ('<div class="imgph imgph-thumb" style="aspect-ratio:3 / 4">'
            '<span class="imgph-label">image</span></div>')


def _img_grid2(count=4, ratio="4 / 3"):
    """한 줄에 2개씩(2열) 배치되는 placeholder 박스 그리드.
    콘텐츠 이미지는 가로형 4:3(=세로:가로 3:4). 캡션은 모두 'image'."""
    boxes = "".join(
        f'<div class="imgph" style="aspect-ratio:{ratio}">'
        f'<span class="imgph-label">image</span></div>'
        for _ in range(count)
    )
    return f'<div class="imgph-grid2">{boxes}</div>'


def _space_block(name):
    """전시 공간 1개의 도면(세로형 9:16 1개, 가운데)+전경(2×2 4개, 가로형) placeholder.
    공간 이름을 머리로 두어 어느 공간인지 표시. 캡션은 모두 'image'."""
    plan = ('<div class="imgph imgph-plan" style="aspect-ratio:9 / 16">'
            '<span class="imgph-label">image</span></div>')
    return (f'<div class="space-block">'
            f'<div class="space-name">{_esc(name)}</div>'
            f'<div class="imgph-plangrid">{plan}</div>'
            f'{_img_grid2(count=4)}'
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
    # 도면·전경 라벨용 공간 이름 (없으면 단일 fallback)
    room_names = ([(r.get("name") or f"{i+1}전시실") for i, r in enumerate(rooms)]
                  if rooms else ["1전시실", "2전시실", "3전시실"])
    # 1) 출품 작품 구성 (도넛 2-up) — 가장 먼저
    art = data.get("artworks", {})
    media = {"회화": art.get("painting", 0), "조각": art.get("sculpture", 0),
             "사진": art.get("photo", 0), "설치": art.get("installation", 0),
             "미디어": art.get("media", 0), "기타": art.get("other", 0)}
    donuts = [c for c in (
        _donut("출품 매체 구성", media, "점"),
        _donut("신작·구작 구성", {"신작": art.get("new", 0) or 0,
                                  "구작": art.get("old", 0) or 0}, "점"),
    ) if c]
    if donuts:
        iii.append(_subhead("출품 작품 구성"))
        iii.append(f'<div class="donut-grid">{"".join(donuts)}</div>')
        total = art.get("total", 0)
        if any(media.values()) and total:
            top = max(media.items(), key=lambda kv: kv[1])
            cap = (f"출품작 {total}점의 매체 구성은 {top[0]}({top[1]}점, "
                   f"{top[1]/total*100:.0f}%) 비중이 가장 큼.")
            nw, od = art.get("new", 0) or 0, art.get("old", 0) or 0
            if nw or od:
                cap += f" 신작 {nw}점, 구작 {od}점."
            iii.append(f'<p class="body">{_esc(cap)}</p>')
    # 2) 전시 도면 · 전경 — 공간별로 도면 1개(세로형) + 전경 2×2(4개)
    #    (전시실→참여 작가 표는 불필요하여 제거)
    iii.append(_subhead("전시 도면 및 전경"))
    for name in room_names:
        iii.append(_space_block(name))
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
        if progs:
            iii.append(_img_grid2(count=2))
    # 인쇄물 — 표 맨 왼쪽에 작은 섬네일 칸 추가(별도 placeholder 제거)
    mats = data.get("printed_materials", [])
    if mats:
        iii.append(_subhead("인쇄물 및 굿즈"))
        iii.append(_table(["이미지", "종류", "수량", "비고"],
                          [[_thumb(), m.get("type", ""), m.get("quantity", ""),
                            m.get("note", "")] for m in mats], raw_cols={0}))
    sec_compose = _section("전시 구성", "".join(iii), num="IV")

    # ── IV. 전시 결과 ──
    iv = []
    rev = data.get("revenue", {})
    iv.append(_kv([
        ("총 사용 예산", data.get("budget", {}).get("total_spent")),
        ("총 수입", rev.get("total_revenue")),
        ("총 관객수", rev.get("total_visitors")),
        ("일평균 관객", rev.get("daily_average")),
    ]))
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
        cells = [c for c in (
            _donut("입장권별 관객 구성", tt, "명"),
            _donut("유료·무료 비율", {"유료": paid, "무료·초대": free}, "명"),
        ) if c]
        if cells:
            iv.append(_subhead("관객 구성"))
            iv.append(f'<div class="donut-grid">{"".join(cells)}</div>')
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
    # 홍보물·언론 보도 캡처 (사진이 거의 확실히 들어가는 자리 — placeholder)
    v.append(_subhead("홍보물·언론 보도"))
    v.append(_img_grid2(count=2))
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
                v.append(_table(["내용", "출처"], crows))
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

    # 포스터 placeholder(세로형) — 1페이지 상단
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
.kv .v { color:#20231f; font-weight:400; }
.tbl { width:100%; border-collapse:collapse; font-size:13px; margin:6px 0; }
.tbl th { background:#f1f4ee; color:#4a5450; font-weight:600; text-align:left;
  padding:7px 10px; border-bottom:1px solid #e3e7df; }
.tbl td { padding:7px 10px; border-bottom:1px solid #eef1ec; color:#3c403a;
  vertical-align:middle; }
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
  gap:10px; margin:6px 0 2px; }
.imgph { border:1.5px dashed #c2ccc2; border-radius:6px; background:#f5f7f4;
  display:flex; align-items:center; justify-content:center; }
.imgph-label { font-size:11.5px; color:#9aa39a; letter-spacing:0.3px; text-align:center; }
/* 전시 전경 — 한 줄에 2개씩(2열) */
/* 한 줄 2개 이미지(3:4) — 90% 폭으로 10% 축소 + 가운데 정렬 */
.imgph-grid2 { display:grid; grid-template-columns:repeat(2, 1fr); gap:10px;
  margin:6px auto 2px; max-width:90%; }
@media (max-width:520px){ .imgph-grid2{ grid-template-columns:1fr; } }
/* 전시 도면 — 세로형(9:16) 박스, 가운데 정렬 */
.imgph-plangrid { display:flex; flex-wrap:wrap; justify-content:center;
  gap:12px; margin:6px 0 2px; }
.imgph-plan { width:210px; max-width:48%; }
/* 표 안 섬네일 (인쇄물·굿즈) — 세로형 3:4, 1.5배 확대, 셀 안 가운데 정렬 */
.imgph-thumb { width:117px; margin:0 auto; }
.imgph-thumb .imgph-label { font-size:10px; }
/* 전시 공간 블록 (공간별 도면+전경) */
.space-block { margin:6px 0 16px; }
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
.legend { display:flex; flex-wrap:wrap; justify-content:center; gap:4px 14px;
  margin-top:12px; font-size:12px; color:#3c403a; }
.legend .lg { display:inline-flex; align-items:center; gap:5px; white-space:nowrap; }
.legend i { width:10px; height:10px; border-radius:2px; display:inline-block; }

/* SVG */
.svgchart { width:100%; height:auto; display:block; }

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
  .report { max-width:none; padding:0; }
  .no-print { display:none !important; }
  /* 섹션 카드는 한 페이지보다 클 수 있으므로 break-inside:avoid 금지
     (금지 시 큰 섹션이 통째로 다음 페이지로 밀려 앞 페이지에 큰 여백 발생).
     쪼개지면 안 되는 작은 요소(도넛·표·차트·이미지 박스)에만 적용. */
  .card { box-shadow:none; border:1px solid #e3e7df; }
  .donut-grid, .donut-cell, .lolli, .tbl, .svgchart,
  .imgph, .space-block { break-inside:avoid; page-break-inside:avoid; }
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
