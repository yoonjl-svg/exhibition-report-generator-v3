"""
테스트용 샘플 데이터 — 공식 배포 시 이 파일과 app.py의 관련 라인을 제거하면 끝.

제거 절차:
  1) 이 파일 삭제
  2) app.py 최상단의 `ENABLE_SAMPLE_DATA = True`를 False로 바꾸거나 관련 블록 3줄 삭제
"""

import streamlit as st


# 하이퍼옐로우 사례를 토대로 작성한 가상 데이터. 제목 앞 (가) 표기로 실제 전시와 구분.
SAMPLE_DATA = {
    # ── B: 기본 정보 ──
    "exhibition_title": "(가)하이퍼 옐로우",
    "period_start": "2025-06-13",
    "period_end": "2025-08-17",
    "artists": "이강승, 박소현, 윤지영, 카타리나 그로세(Katharina Grosse), 올라퍼 엘리아슨(Olafur Eliasson), 김나영, 장태원, 하태범, 안드레아 거스키(Andreas Gursky), 무라카미 다카시(村上隆), 이불, 최정화",
    "chief_curator": "이서현",
    "curators": "박민지",
    "coordinators": "한지우, 김도연",
    "curatorial_team": "큐레토리얼팀",
    "pr_person": "정수빈",
    "sponsors": "일민문화재단, 한국문화예술위원회",
    "theme_text": (
        "《하이퍼 옐로우》는 노란색의 감각적·상징적 의미를 동시대 미술의 맥락에서 탐구하는 대규모 기획전이다. "
        "노란색은 경고와 환희, 금과 빛, 위험과 희망이라는 양가적 의미를 동시에 내포한다. "
        "참여 작가 12인은 회화, 설치, 사진, 미디어아트 등 다양한 매체를 통해 노란색이 촉발하는 감각적 경험과 사회적 함의를 탐색한다. "
        "이 전시는 색채가 단순한 시각적 요소를 넘어 문화적 코드이자 정치적 언어로 기능하는 방식을 조명한다."
    ),
    "rooms": [
        {"name": "1전시실", "artists": "이강승, 카타리나 그로세, 올라퍼 엘리아슨"},
        {"name": "2전시실", "artists": "박소현, 윤지영, 김나영, 장태원"},
        {"name": "3전시실", "artists": "하태범, 안드레아 거스키, 무라카미 다카시"},
        {"name": "프로젝트 룸", "artists": "이불, 최정화"},
    ],
    "related_programs": [
        {"category": "강연", "title": "색의 정치학: 노란색을 둘러싼 담론", "date": "2025-06-20", "participants": "95", "note": "큐레이터 토크"},
        {"category": "워크숍", "title": "노란 세계 만들기", "date": "2025-06-28", "participants": "25", "note": "어린이 대상"},
        {"category": "아티스트 토크", "title": "아티스트 토크: 색채와 물질", "date": "2025-07-05", "participants": "78", "note": "참여작가 4인"},
        {"category": "워크숍", "title": "컬러 필드 드로잉", "date": "2025-07-12", "participants": "30", "note": "성인 대상"},
        {"category": "스크리닝", "title": "옐로우 시네마: 영화 속 노란색", "date": "2025-07-19", "participants": "55", "note": "상영+토론"},
        {"category": "퍼포먼스", "title": "옐로우 라이브: 빛의 퍼포먼스", "date": "2025-07-26", "participants": "140", "note": "올라퍼 엘리아슨 협력"},
        {"category": "강연", "title": "클로징 라운드테이블: 색채의 미래", "date": "2025-08-09", "participants": "85", "note": "국제 패널"},
        {"category": "워크숍", "title": "가족과 함께하는 색 놀이", "date": "2025-08-16", "participants": "40", "note": "가족 대상"},
    ],
    "printed_materials": [
        {"type": "기타", "quantity": "1500", "note": "도록 (국영문 병행, 양장)"},
        {"type": "리플렛", "quantity": "8000", "note": "4단 접지"},
        {"type": "포스터", "quantity": "800", "note": "B1 사이즈, 형광 인쇄"},
        {"type": "초대장", "quantity": "500", "note": "특수 용지"},
        {"type": "굿즈", "quantity": "3000", "note": "엽서 세트 (작품 이미지 12종)"},
    ],

    # ── 홍보 (B - 서술) ──
    "promo_advertising": "지하철 광고(3호선 안국역, 1호선 종각역), 문화예술 전문지 광고(월간미술, 아트인컬처, 미술세계)",
    "promo_press_release": "전시 개막 3주 전 배포, 중간 보도자료 2회 추가 배포, 클로징 보도자료 1회",
    "promo_web_invitation": "개막 4주 전 1차 발송, 개막 1주 전 리마인더, VIP 별도 초청",
    "promo_newsletter": "전시 소개 뉴스레터 3회 발송 (개막 전, 진행 중, 클로징)",
    "promo_sns": "인스타그램 메인 채널, 페이스북 이벤트, 유튜브 전시 소개 영상 + 작가 인터뷰 시리즈",
    "promo_other": "네이버 문화콘텐츠 배너, 카카오 이모티콘 콜라보, 문화포털 전시 등록",
    "press_print": [
        {"outlet": "조선일보", "date": "2025-06-12", "title": "노란빛으로 물든 일민미술관, 12인의 색채 실험", "note": "문화면"},
        {"outlet": "한겨레", "date": "2025-06-15", "title": "색의 정치학, 노란색이 말하는 것", "note": "주말판"},
        {"outlet": "중앙일보", "date": "2025-07-02", "title": "올라퍼 엘리아슨의 빛, 서울에 오다", "note": ""},
        {"outlet": "동아일보", "date": "2025-07-20", "title": "여름을 채우는 노란 감각", "note": ""},
    ],
    "press_online": [
        {"outlet": "아트인컬처", "date": "2025-06-13", "title": "《하이퍼 옐로우》 개막 리포트", "url": "https://example.com/1"},
        {"outlet": "월간미술", "date": "2025-06-25", "title": "큐레이터 인터뷰: 노란색을 다시 묻다", "url": "https://example.com/2"},
        {"outlet": "퍼블릭아트", "date": "2025-07-10", "title": "참여 작가 12인 작품 리뷰", "url": "https://example.com/3"},
        {"outlet": "네오룩", "date": "2025-07-30", "title": "여름 전시 추천: 하이퍼 옐로우", "url": "https://example.com/4"},
    ],
    "membership_text": "일민 멤버십 대상 사전 관람 행사 개최, 멤버십 전용 도슨트 3회 운영, 도록 10% 할인",
    "visitor_reviews": [
        {"category": "긍정", "content": "전시장 전체가 노란빛으로 물든 경험이 압도적이었습니다. 올라퍼 엘리아슨의 빛 설치가 특히 인상적.", "source": "방명록"},
        {"category": "긍정", "content": "아이와 함께 왔는데 색채 워크숍이 너무 좋았어요. 또 오고 싶습니다.", "source": "SNS"},
        {"category": "긍정", "content": "카타리나 그로세의 대형 페인팅 앞에서 한참을 서 있었습니다. 색의 물질성이 느껴졌습니다.", "source": "설문"},
        {"category": "부정", "content": "인파가 많아 작품 감상이 쉽지 않았습니다. 사전예약제가 필요해 보입니다.", "source": "SNS"},
        {"category": "건의", "content": "굿즈가 더 다양했으면 좋겠습니다. 노란색 테마에 맞는 상품 구성이 아쉬웠습니다.", "source": "설문"},
    ],

    # ── A: 정량 데이터 ──
    "total_budget": 210000000,
    "budget_exhibition": 175000000,
    "budget_supplementary": 35000000,
    "budget_planned": 220000000,
    "total_revenue": 98000000,
    "ticket_revenue": 82000000,
    "other_revenue": 16000000,
    "total_visitors": 15200,
    "visitor_general": 6100,
    "visitor_student": 2800,
    "visitor_invitation": 3000,
    "visitor_artpass": 900,
    "visitor_discover": 700,
    "visitor_discount": 1700,
    "visitor_group": 2100,
    "opening_attendance": 420,
    "artwork_total": 68,
    "artwork_painting": 18,
    "artwork_sculpture": 8,
    "artwork_photo": 15,
    "artwork_installation": 14,
    "artwork_media": 9,
    "artwork_other": 4,
    "program_count": 8,
    "program_sessions": 65,
    "program_participants": 548,
    "docent_total": 2800,
    "docent_regular": 2200,
    "docent_special": 600,
    "staff_total": 14,
    "staff_paid": 8,
    "staff_volunteer": 6,
    "press_count": 32,
    "sns_posts": 24,
    "sns_feedback": 580,
    "web_invitation_count": 5200,
    "newsletter_open_rate": 32.7,
    "membership_count": 245,
    "weekly_visitors": {"1주": 1950, "2주": 2400, "3주": 2850, "4주": 2600, "5주": 2900, "6주": 2500},
}


def render_sample_button():
    """사이드바에 '샘플 데이터 채우기' 버튼을 렌더 (테스트 전용)."""
    with st.sidebar:
        st.divider()
        st.caption("🧪 테스트 도구")
        if st.button("샘플 채우기", use_container_width=True,
                     help="(가)하이퍼 옐로우 데이터로 모든 필드를 채웁니다. 자동으로 상세 작업 모드로 진입합니다."):
            # 기존 JSON 로드와 동일한 메커니즘 사용 (위젯 키 충돌 회피)
            st.session_state["_pending_json"] = {k: v for k, v in SAMPLE_DATA.items()}
            # v5: 워크스페이스 모드에서 호출되어도 자동으로 상세 모드로 전환
            st.session_state["app_mode"] = "detail"
            st.session_state["current_exhibition_id"] = None  # 신규로 처리
            st.session_state["current_exhibition_status"] = "draft"
            st.session_state["current_exhibition_type"] = 1   # 정기 기획전 기본
            st.rerun()
        st.caption("⚠️ 공식 배포 시 제거")
