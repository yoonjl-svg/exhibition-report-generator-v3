"""
일민미술관 전시보고서 생성기 v3
B(기본 정보) → A(정량 데이터) → C(자동 분석) → 생성
"""

import os
from datetime import date
import streamlit as st
import pandas as pd

from tabs import tab_base, tab_data, tab_analysis, tab_generate
import reference_data as rd

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="전시보고서 생성기 v3",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────

st.markdown("""
<style>
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e0e0e0;
    }
    .insight-card {
        background: #f8f9fa;
        border-left: 4px solid #4a90d9;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
    }
    .eval-draft {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
    }
    .metric-badge {
        display: inline-block;
        background: #e8f4fd;
        color: #1a73e8;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        margin-left: 8px;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        font-size: 1rem;
        font-weight: 600;
    }
    .stNumberInput > div > div > input { text-align: right; }
</style>
""", unsafe_allow_html=True)


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
        # 사용자 추가 평가
        "eval_positive_custom": [""],
        "eval_negative_custom": [""],
        "eval_improvement_custom": [""],

        # ── 예산 상세 (보고서용) ──
        "budget_summary": [{"category": "", "planned": "", "actual": "", "note": ""}],
        "budget_details": [{"category": "", "subcategory": "", "detail": "", "amount": "", "note": ""}],
        "budget_breakdown_notes": [""],
        "budget_arrow_notes": [""],
        # 관객 분석 텍스트
        "visitor_ticket_analysis": [""],
        "visitor_analysis_text": "",
        "weekly_visitors": {},
    }

    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # ── pending JSON 적용 (위젯 렌더링 전에 실행) ──
    if "_pending_json" in st.session_state:
        data = st.session_state.pop("_pending_json")

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

@st.cache_data
def load_reference_data():
    """레퍼런스 Excel 로드 (캐싱)"""
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
    st.title("🎨 전시보고서 생성기")
    st.caption("v3.0 — 분석 통합형")
    st.divider()

    title = st.session_state.exhibition_title
    if title:
        st.markdown(f"**《{title}》**")
    else:
        st.markdown("*전시 제목을 입력해주세요*")

    st.divider()
    st.caption("© 일민미술관")


# ──────────────────────────────────────────────
# 탭 구조: B → A → C → 생성
# ──────────────────────────────────────────────

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
