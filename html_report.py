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
ACCENT = "#255c4a"
ACCENT2 = "#b4512a"
ACCENT3 = "#3f5e99"
INK = "#20231f"
MUTED = "#7a827a"
LINE = "#d9ddd4"
SOFT = "#eef2ea"
CAT = ["#255c4a", "#b4512a", "#3f5e99", "#8a6d3b", "#6d6a8c", "#4a7c59"]


def _esc(s):
    return _html.escape(str(s if s is not None else ""))


# ──────────────────────────────────────────────
# 컴포넌트
# ──────────────────────────────────────────────

def _lollipop(summary_metrics):
    """핵심 지표 롤리팝 (현재/기준×100)."""
    rows = []
    for m in (summary_metrics or []):
        cur, ref = m.get("current"), m.get("reference_avg")
        if cur is None or not ref:
            continue
        rows.append((m["label"], m.get("current_fmt", ""),
                     m.get("reference_avg_fmt", ""), cur / ref * 100,
                     m.get("reference_label", "기준")))
    if len(rows) < 2:
        return ""
    xmax = max(160.0, max(r[3] for r in rows) * 1.08)
    base_pct = 100 / xmax * 100  # 기준선 위치(%)

    items = []
    for label, cur_fmt, ref_fmt, ratio, ref_label in rows:
        val_pct = min(ratio, xmax) / xmax * 100
        above = ratio >= 100
        color = ACCENT if above else ACCENT2
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
            <div class="lolli-val" style="left:{val_pct:.1f}%;color:{color}">{ratio:.0f}</div>
          </div>
        </div>""")
    scale = f"""<div class="lolli-scale"><span>0</span>
        <span style="left:{base_pct:.1f}%">100</span>
        <span style="right:0">{xmax:.0f}</span></div>"""
    return f"""<div class="card">
      <div class="fig-title">기준 대비 핵심 지표</div>
      <div class="fig-sub">비교 기준 평균을 100으로 환산. 점이 본 전시 위치 · 기준 위=녹색, 아래=테라코타</div>
      <div class="lolli-wrap">{scale}{''.join(items)}</div>
    </div>"""


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


def _section(title, body):
    if not body:
        return ""
    return f'<div class="card"><div class="fig-title">{_esc(title)}</div>{body}</div>'


def _para(text):
    if not text:
        return ""
    paras = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    return "".join(f'<p class="body">{_esc(p)}</p>' for p in paras)


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def build_report_html(data):
    """전체 data dict → self-contained HTML 문서 문자열."""
    ov = data.get("overview", {})
    title = ov.get("title") or data.get("exhibition_title") or "(제목 미입력)"
    period = ov.get("period", "")
    artists = ov.get("artists", [])
    artists_str = ", ".join(artists) if isinstance(artists, list) else str(artists)

    blocks = []

    # ── 헤더 ──
    blocks.append(f"""<div class="rep-head">
      <div class="eyebrow">EXHIBITION REPORT</div>
      <div class="rep-title">《{_esc(title)}》</div>
      <div class="rep-meta">{_esc(period)}{(' · ' + _esc(artists_str)) if artists_str else ''}</div>
    </div>""")

    # ── 핵심 지표 롤리팝 ──
    blocks.append(_lollipop(data.get("summary_metrics", [])))

    # ── 전시 구성: 매체 + 신작 도넛 (2-up) ──
    art = data.get("artworks", {})
    media = {"회화": art.get("painting", 0), "조각": art.get("sculpture", 0),
             "사진": art.get("photo", 0), "설치": art.get("installation", 0),
             "미디어": art.get("media", 0), "기타": art.get("other", 0)}
    donuts = []
    md = _donut("출품 매체 구성", media, "점")
    if md:
        donuts.append(md)
    nw = art.get("new", 0) or 0
    od = art.get("old", 0) or 0
    nd = _donut("신작·구작 구성", {"신작": nw, "구작": od}, "점")
    if nd:
        donuts.append(nd)
    if donuts:
        total = art.get("total", 0)
        top = max(media.items(), key=lambda kv: kv[1]) if any(media.values()) else None
        cap = ""
        if top and total:
            cap = (f"출품작 {total}점의 매체 구성은 {top[0]}({top[1]}점, "
                   f"{top[1]/total*100:.0f}%) 비중이 가장 큼.")
            if nw or od:
                cap += f" 신작 {nw}점, 구작 {od}점."
        blocks.append(f"""<div class="card">
          <div class="fig-title">출품 작품 구성</div>
          <div class="donut-grid">{''.join(donuts)}</div>
          {('<p class="body">' + _esc(cap) + '</p>') if cap else ''}
        </div>""")

    # ── 관객: 주차별 추이(SVG) ──
    vc = data.get("visitor_composition", {})
    weekly = vc.get("weekly_visitors", {})
    comp = data.get("comparison", {})
    svg = _svg_weekly(weekly, comp.get("weekly_ref"))
    if svg:
        peak = max(weekly, key=weekly.get)
        wcap = f"주차별 관객은 {peak}에 최고 {max(weekly.values()):,}명을 기록함."
        wref = comp.get("weekly_ref", [])
        if wref:
            wcap += " 점선은 " + ", ".join(
                f"{lbl} 주당 {v:,.0f}명" for v, lbl, _ in wref) + "."
        blocks.append(f"""<div class="card">
          <div class="fig-title">주차별 관객 추이</div>{svg}
          <p class="body">{_esc(wcap)}</p>
        </div>""")

    # ── 관객: 입장권 + 유료무료 도넛 (2-up) ──
    tt = vc.get("ticket_type", {})
    if tt:
        free = tt.get("초대권", 0) or 0
        paid = sum(v for k, v in tt.items() if k != "초대권")
        cells = [_donut("입장권별 관객 구성", tt, "명")]
        pf = _donut("유료·무료 비율", {"유료": paid, "무료·초대": free}, "명")
        if pf:
            cells.append(pf)
        cells = [c for c in cells if c]
        top = max(tt, key=tt.get)
        tt_total = sum(tt.values()) or 1
        cap = (f"입장권별로는 {top}이(가) {tt[top]:,}명"
               f"({tt[top]/tt_total*100:.0f}%)으로 가장 큼.")
        if paid + free:
            cap += f" 유료 관객 {paid:,}명({paid/(paid+free)*100:.0f}%)."
        blocks.append(f"""<div class="card">
          <div class="fig-title">관객 구성</div>
          <div class="donut-grid">{''.join(cells)}</div>
          <p class="body">{_esc(cap)}</p>
        </div>""")

    # ── 종합 의견 (LLM/룰) ──
    llm = data.get("llm_sections", {}) or {}
    eval_text = (llm.get("evaluation") or "").strip()
    if not eval_text:
        si = data.get("section_insights", {}).get("evaluation", [])
        eval_text = "\n\n".join(i.get("text", "") for i in si)
    blocks.append(_section("종합 의견", _para(eval_text)))

    aud = (llm.get("audience_response") or "").strip()
    blocks.append(_section("관객 반응 종합", _para(aud)))

    body = "\n".join(b for b in blocks if b)
    return _DOC.replace("{{BODY}}", body)


# ──────────────────────────────────────────────
# 문서 셸 + 스타일
# ──────────────────────────────────────────────

_DOC = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<style>
* { box-sizing: border-box; }
body { margin:0; background:#f4f6f2; color:#20231f;
  font-family: -apple-system, "Noto Sans KR", "Malgun Gothic", sans-serif; }
.report { max-width: 860px; margin: 0 auto; padding: 24px 16px 60px; }
.rep-head { padding: 8px 4px 18px; border-bottom: 2px solid #255c4a; margin-bottom: 20px; }
.eyebrow { color:#255c4a; font-size:11px; font-weight:700; letter-spacing:.1em; }
.rep-title { font-size:26px; font-weight:800; margin:6px 0 4px; letter-spacing:-.01em; }
.rep-meta { color:#646b61; font-size:13px; }
.card { background:#fff; border:1px solid #e3e7df; border-radius:12px;
  padding:20px 22px; margin-bottom:18px; box-shadow:0 1px 3px rgba(32,35,31,.04); }
.fig-title { font-size:16px; font-weight:700; color:#20231f; margin-bottom:4px; }
.fig-title.sm { font-size:13px; text-align:center; margin-bottom:10px; }
.fig-sub { font-size:12px; color:#7a827a; margin-bottom:18px; }
.body { font-size:14px; line-height:1.7; color:#2c302b; margin:10px 0 0; }

/* 롤리팝 */
.lolli-wrap { position:relative; padding-top:22px; }
.lolli-scale { position:relative; height:16px; margin-bottom:8px;
  color:#9aa39a; font-size:11px; }
.lolli-scale span { position:absolute; transform:translateX(-50%); }
.lolli { display:grid; grid-template-columns:170px 1fr; align-items:center;
  gap:14px; margin:7px 0; }
.lolli-label { font-size:13px; font-weight:700; line-height:1.3; }
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
</style></head>
<body><div class="report">{{BODY}}</div></body></html>"""
