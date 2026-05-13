"""
일민미술관 전시 워크스페이스 (v5)
워크스페이스 모드: 전시 목록 / 상세 모드: B → A → C → D
"""

import os
from datetime import date
import streamlit as st
import pandas as pd

from tabs import tab_base, tab_data, tab_analysis, tab_generate, tab_workspace
import reference_data as rd
import kb_session

# ── 샘플 데이터 토글 (공식 배포 시 False) ─────────────
ENABLE_SAMPLE_DATA = True

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="일민미술관 전시 워크스페이스",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────

st.markdown("""
<style>
    /* ═══════════════════════════════════════════════
       일민미술관 전시 워크스페이스 v5.1 — 미술관 톤 시스템
       GPT v4.1 디자인 언어 흡수 (시각만, 아키텍처는 우리 것)
       ═══════════════════════════════════════════════ */

    :root {
        --bg: #f7f8f5;
        --surface: #ffffff;
        --ink: #20231f;
        --muted: #646b61;
        --line: #d9ddd4;
        --accent: #255c4a;
        --accent-2: #b4512a;
        --accent-3: #3f5e99;
        --soft: #eef2ea;
        --warn: #8a4b15;
    }

    /* === Eyebrow 라벨 (모든 섹션 위에) === */
    .eyebrow {
        color: var(--accent);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 6px;
        line-height: 1.3;
    }

    /* === 메인 타이틀 (페이지 헤더) === */
    .main-title {
        font-size: 26px;
        font-weight: 700;
        color: var(--ink);
        margin: 0 0 4px 0;
        letter-spacing: -0.2px;
    }
    .main-subtitle {
        color: var(--muted);
        font-size: 13px;
        margin: 0 0 14px 0;
        line-height: 1.45;
    }

    /* === 섹션 헤더 (구버전 .section-header 갱신) === */
    .section-header {
        font-size: 20px;
        font-weight: 700;
        color: var(--ink);
        margin: 2px 0 8px 0;
        padding-bottom: 0;
        border-bottom: none;
        line-height: 1.25;
    }

    /* === Metric Strip (워크스페이스 상단 KPI) === */
    .metric-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 10px;
        margin: 8px 0 24px 0;
    }
    .metric-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px 16px;
        background: var(--soft);
    }
    .metric-card .metric-label {
        color: var(--muted);
        font-size: 12px;
        margin-bottom: 6px;
        line-height: 1.3;
    }
    .metric-card .metric-value {
        color: var(--ink);
        font-size: 22px;
        font-weight: 700;
        line-height: 1.1;
    }
    .metric-card .metric-context {
        color: var(--muted);
        font-size: 11px;
        margin-top: 4px;
    }

    /* === Chips (분류·상태·중요도) === */
    .chip {
        display: inline-flex;
        align-items: center;
        height: 22px;
        border-radius: 999px;
        padding: 0 10px;
        background: var(--soft);
        color: var(--muted);
        font-size: 11px;
        font-weight: 500;
        margin-right: 5px;
        white-space: nowrap;
        line-height: 1;
    }
    .chip.high, .chip.completed { background: #e7f1eb; color: var(--accent); }
    .chip.medium, .chip.in-progress { background: #f5eee8; color: var(--accent-2); }
    .chip.low, .chip.draft { background: #eef1f6; color: var(--accent-3); }
    .chip.archived { background: #ececea; color: var(--muted); }

    /* === Exhibition Card (워크스페이스 목록) === */
    .exhibition-card-title {
        font-size: 17px;
        font-weight: 700;
        color: var(--ink);
        margin: 6px 0 4px 0;
        line-height: 1.3;
    }
    .exhibition-card-meta {
        color: var(--muted);
        font-size: 12px;
        margin-bottom: 8px;
    }
    .exhibition-card-metrics {
        display: flex;
        gap: 14px;
        flex-wrap: wrap;
        color: var(--ink);
        font-size: 13px;
        margin-top: 4px;
    }
    .exhibition-card-metrics .metric-item {
        color: var(--muted);
    }
    .exhibition-card-metrics .metric-item strong {
        color: var(--ink);
        font-weight: 600;
    }

    /* === 기존 인사이트 카드 (분석 탭) — 미술관 톤 적용 === */
    .insight-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-left: 3px solid var(--accent);
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 6px;
    }
    .eval-draft {
        background: var(--surface);
        border: 1px solid var(--line);
        border-left: 3px solid var(--accent-2);
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 6px;
    }
    .metric-badge {
        display: inline-block;
        background: var(--soft);
        color: var(--accent);
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-left: 6px;
    }

    /* === Streamlit 위젯 미세 조정 === */
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        font-size: 14px;
        font-weight: 600;
    }
    .stNumberInput > div > div > input { text-align: right; }

    /* === Streamlit 기본 alert 색 미술관 톤 === */
    div[data-testid="stAlert"] {
        border-radius: 6px;
    }

    /* ═══════════════════════════════════════════════
       v5.2 컴팩트 레이아웃 — 광역 모니터 가독성
       ═══════════════════════════════════════════════ */

    /* 메인 콘텐츠 최대 너비 제한 (1920px 모니터 대응)
       GPT v4.1의 max-width 1320px 차용, 약간 더 타이트하게 1280px */
    .block-container,
    [data-testid="stMainBlockContainer"],
    [data-testid="block-container"] {
        max-width: 1280px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* 위젯 간 수직 간격 축소 (Streamlit 기본 1rem → 0.6rem) */
    [data-testid="stVerticalBlock"] {
        gap: 0.6rem;
    }

    /* 입력 위젯 라벨 — 작게, 뮤트 톤 */
    label[data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p {
        font-size: 12px !important;
        margin-bottom: 4px !important;
        color: var(--muted) !important;
        font-weight: 500 !important;
    }

    /* 입력 필드 자체의 vertical padding 축소 */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {
        padding-top: 6px !important;
        padding-bottom: 6px !important;
    }

    /* textarea 라인 높이 정리 */
    .stTextArea textarea {
        padding-top: 8px !important;
        padding-bottom: 8px !important;
        line-height: 1.5 !important;
    }

    /* selectbox 컴팩트 */
    .stSelectbox > div > div {
        min-height: 32px !important;
    }

    /* 캡션 / help 텍스트 작게 */
    [data-testid="stCaptionContainer"],
    .stCaption {
        font-size: 12px !important;
        color: var(--muted) !important;
    }

    /* 탭 패널 상단 패딩 축소 */
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 0.5rem !important;
    }

    /* 탭 자체 헤더 — 본문에 더 가깝게 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }

    /* st.divider — 마진 축소 */
    [data-testid="stMarkdownContainer"] hr,
    hr {
        margin: 1rem 0 !important;
    }

    /* 버튼 컴팩트 */
    .stButton button {
        min-height: 34px !important;
        padding: 0 14px !important;
    }
</style>
""", unsafe_allow_html=True)


# UI 헬퍼는 ui_helpers.py에 통합 (모든 탭에서 import 가능)
from ui_helpers import eyebrow, section_header, chip, chip_row, metric_card, metric_strip, status_chip, type_chip


# ──────────────────────────────────────────────
# 세션 초기화
# ──────────────────────────────────────────────

def init_session():
    """세션 상태 기본값 설정"""
    defaults = {
        # ── B: 기본 정보 ──
        "exhibition_title": "",
        "period_start": None,
        "period_end": None,
        "artists": "",
        "chief_curator": "",
        "curators": "",
        "coordinators": "",
        "curatorial_team": "",
        "pr_person": "",
        "sponsors": "",
        "theme_text": "",
        "graphic_designer": "",
        "space_designer": "",
        "rooms": [{"name": "1전시실", "artists": ""}],
        "related_programs": [{"category": None, "title": "", "date": None, "participants": "", "note": ""}],
        "printed_materials": [{"type": None, "quantity": "", "note": ""}],
        # 홍보 방식 (B — 서술)
        "promo_advertising": "",
        "promo_press_release": "",
        "promo_web_invitation": "",
        "promo_newsletter": "",
        "promo_sns": "",
        "promo_other": "",
        # 언론보도 리스트 (B — 서술)
        "press_print": [{"outlet": "", "date": None, "title": "", "note": ""}],
        "press_online": [{"outlet": "", "date": None, "title": "", "url": ""}],
        "membership_text": "",
        # 관객 후기 (B — 정성)
        "visitor_reviews": [{"category": "긍정", "content": "", "source": ""}],

        # ── A: 정량 데이터 ──
        "total_budget": 0,
        "budget_exhibition": 0,
        "budget_supplementary": 0,
        "budget_planned": 0,
        "total_revenue": 0,
        "ticket_revenue": 0,
        "other_revenue": 0,
        "total_visitors": 0,
        "visitor_general": 0,
        "visitor_student": 0,
        "visitor_invitation": 0,
        "visitor_artpass": 0,
        "visitor_discover": 0,
        "visitor_discount": 0,
        "visitor_group": 0,
        "opening_attendance": 0,
        "artwork_total": 0,
        "artwork_painting": 0,
        "artwork_sculpture": 0,
        "artwork_photo": 0,
        "artwork_installation": 0,
        "artwork_media": 0,
        "artwork_other": 0,
        "program_count": 0,
        "program_sessions": 0,
        "program_participants": 0,
        "docent_total": 0,
        "docent_regular": 0,
        "docent_special": 0,
        "staff_total": 0,
        "staff_paid": 0,
        "staff_volunteer": 0,
        "press_count": 0,
        "sns_posts": 0,
        "sns_feedback": 0,
        "sns_followers": 0,
        "sns_followers_gained": 0,
        "sns_avg_likes": 0,
        "sns_best_likes": 0,
        "sns_best_post": "",
        "web_invitation_count": 0,
        "newsletter_open_rate": 0.0,
        "membership_count": 0,

        # ── 분석 설정 ──
        "exhibition_type": None,

        # ── C: 분석 결과 ──
        "analysis_result": None,
        "insight_selections": {},
        "insight_texts": {},
        "eval_positive_drafts": [],
        "eval_negative_drafts": [],
        "eval_improvement_drafts": [],

        # ── 예산 상세 (보고서용) ──
        "budget_summary": [{"category": "", "planned": "", "actual": "", "note": ""}],
        "budget_details": [{"category": "", "subcategory": "", "detail": "", "amount": "", "note": ""}],
        "budget_breakdown_notes": [""],
        "budget_arrow_notes": [""],
        # 관객 분석 텍스트
        "visitor_ticket_analysis": [""],
        "visitor_analysis_text": "",
        "weekly_visitors": {},

        # ── v5: 워크스페이스 모드 ──
        "app_mode": "workspace",            # "workspace" | "detail"
        "current_exhibition_id": None,      # 편집 중인 전시 slug (None = 신규)
        "current_exhibition_status": "draft",
        "current_exhibition_type": None,
        "current_exhibition_meta": {},
    }

    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # ── pending JSON 적용 (위젯 렌더링 전에 실행) ──
    if "_pending_json" in st.session_state:
        data = st.session_state.pop("_pending_json")
        # 이전 보고서 미리보기 상태 무효화 (전시 데이터가 교체되었으므로)
        st.session_state.pop("report_state", None)
        for _sec in ("composition", "results", "promotion", "evaluation", "audience_response"):
            st.session_state.pop(f"preview_edit_{_sec}", None)

        # 중첩 리스트 안의 날짜 문자열 → date 객체 변환
        for list_key in ("related_programs", "press_print", "press_online"):
            if list_key in data and isinstance(data[list_key], list):
                for item in data[list_key]:
                    if isinstance(item, dict) and "date" in item:
                        d = item["date"]
                        if isinstance(d, str) and d:
                            try:
                                item["date"] = date.fromisoformat(d)
                            except ValueError:
                                item["date"] = None
                        elif not isinstance(d, date):
                            item["date"] = None

        date_keys = {"period_start", "period_end"}
        for key, val in data.items():
            # 위젯 키 소유권 해제 후 새 값 설정
            if key in st.session_state:
                del st.session_state[key]
            if key in date_keys:
                st.session_state[key] = date.fromisoformat(val) if val else None
            else:
                st.session_state[key] = val


init_session()


# ──────────────────────────────────────────────
# 레퍼런스 데이터 로드
# ──────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_reference_data():
    """레퍼런스 데이터 로드.

    v5 전환: KB(v5 저장소) 우선, 실패 시 xlsx 폴백.
      1. kb_store에서 모든 전시 레코드 로드
      2. analysis_engine 호환 DataFrame으로 변환
      3. KB 비어 있거나 오류 시 xlsx 폴백
    """
    # 1. KB 시도
    try:
        import kb_store
        records = kb_store.list_exhibitions()
        if records:
            df = rd.kb_records_to_reference_df(records)
            if len(df) > 0:
                return df
    except Exception as e:
        # KB 사용 불가 시 조용히 xlsx 폴백 (개발 환경 호환)
        st.caption(f"⚠️ KB 로드 실패 — xlsx 폴백 사용 ({type(e).__name__})")

    # 2. xlsx 폴백
    xlsx_path = os.path.join(os.path.dirname(__file__), "exhibition_reference_data.xlsx")
    if not os.path.exists(xlsx_path):
        return None
    try:
        return rd.load_reference(xlsx_path)
    except Exception as e:
        st.error(f"레퍼런스 로드 오류: {e}")
        return None


# ──────────────────────────────────────────────
# 사이드바
# ──────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        '<div class="eyebrow">ILMIN EXHIBITION WORKSPACE</div>'
        '<div class="main-title" style="font-size: 20px;">전시 워크스페이스</div>'
        '<p class="main-subtitle" style="font-size: 12px; margin-bottom: 16px;">v5.1 — KB 통합형</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # 모드 표시 + 워크스페이스 복귀 버튼
    app_mode = st.session_state.get("app_mode", "workspace")
    if app_mode == "detail":
        current_id = st.session_state.get("current_exhibition_id")
        title = st.session_state.get("exhibition_title", "")
        status = st.session_state.get("current_exhibition_status", "draft")
        type_num = st.session_state.get("current_exhibition_type")

        eyebrow("작업 중인 전시")
        if title:
            st.markdown(f'<div class="exhibition-card-title">《{title}》</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="exhibition-card-title">(제목 미입력)</div>',
                        unsafe_allow_html=True)

        # 상태·유형 chip
        chips_html = status_chip(status) + " " + type_chip(type_num)
        st.markdown(chips_html, unsafe_allow_html=True)

        if current_id:
            st.caption(f"id: `{current_id}`")
        else:
            st.caption("⚠️ 미저장 (신규)")

        st.divider()

        # 워크스페이스에 저장
        if st.button("💾 워크스페이스에 저장", type="primary", use_container_width=True,
                     help="현재 작업 중인 전시 데이터를 KB에 영구 저장합니다."):
            try:
                saved = kb_session.save_current_to_kb()
                st.success(f"✅ 저장됨\n\n`{saved['id']}`\n\n{saved['modified_at']}")
            except Exception as e:
                st.error(f"저장 오류: {e}")
                import traceback
                st.code(traceback.format_exc())

        # 목록으로 돌아가기
        if st.button("📚 워크스페이스 목록", use_container_width=True,
                     help="목록 화면으로 돌아갑니다. 저장하지 않은 변경은 메모리에 유지됩니다."):
            kb_session.enter_workspace_mode()
            st.rerun()
    else:
        eyebrow("WORKSPACE MODE")
        st.caption("저장된 전시를 선택해 편집하거나 새로 만드세요.")

    st.divider()
    st.caption("© 일민미술관")

# ── 샘플 데이터 버튼 (테스트 전용) ─────────────
if ENABLE_SAMPLE_DATA:
    from sample_data import render_sample_button
    render_sample_button()


# ──────────────────────────────────────────────
# 라우팅: 워크스페이스 모드 / 상세 모드
# ──────────────────────────────────────────────

app_mode = st.session_state.get("app_mode", "workspace")

if app_mode == "workspace":
    # 워크스페이스만 단독 렌더 (전시 목록 + 신규)
    tab_workspace.render(st.container(), load_reference_data)
else:
    # 상세 모드: 기존 4탭 (B/A/C/D)
    tab_b, tab_a, tab_c, tab_d = st.tabs([
        "📋 기본 정보",
        "📊 정량 데이터",
        "🔍 분석 & 평가",
        "📄 보고서 생성",
    ])

    tab_base.render(tab_b)
    tab_data.render(tab_a)
    tab_analysis.render(tab_c, load_reference_data)
    tab_generate.render(tab_d, load_reference_data)
