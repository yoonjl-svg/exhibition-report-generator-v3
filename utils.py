"""v3 공통 헬퍼"""

import os
import tempfile
import streamlit as st
from datetime import date


def add_item(key, template):
    st.session_state[key].append(template.copy())


def remove_item(key, index):
    if len(st.session_state[key]) > 1:
        st.session_state[key].pop(index)


def parse_num(s):
    """범용 숫자 파싱"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s) if s != 0 else None
    s = str(s).replace(",", "").replace("명", "").replace("원", "")
    s = s.replace("%", "").replace("약 ", "").replace("개", "").replace("회", "").strip()
    try:
        v = float(s)
        return v if v != 0 else None
    except (ValueError, TypeError):
        return None


def fmt_number(v, unit=""):
    """숫자를 한국어 포맷으로"""
    if v is None or v == 0:
        return ""
    v = int(v)
    return f"{v:,}{unit}"


def fmt_money(v):
    """금액 포맷"""
    if v is None or v == 0:
        return ""
    v = int(v)
    if v >= 100_000_000:
        eok = v // 100_000_000
        remainder = v % 100_000_000
        if remainder >= 10_000_000:
            man = remainder // 10_000
            return f"약 {eok}억 {man:,}만 원({v:,}원)"
        return f"약 {eok}억 원({v:,}원)"
    elif v >= 10_000_000:
        man = v // 10_000
        return f"약 {man:,}만 원({v:,}원)"
    return f"{v:,}원"


def save_uploaded_images_to_temp(uploaded_files, prefix="img"):
    paths = []
    if uploaded_files:
        for i, f in enumerate(uploaded_files):
            path = os.path.join(tempfile.gettempdir(), f"{prefix}_{i}.png")
            with open(path, "wb") as out:
                out.write(f.getvalue())
            paths.append(path)
    return paths


def collect_analysis_data() -> dict:
    """세션 상태에서 분석용 flat dict 생성 (레퍼런스 컬럼명 기준)"""
    s = st.session_state

    # 전시 일수 자동 계산
    exhibition_days = None
    if s.period_start and s.period_end:
        delta = s.period_end - s.period_start
        exhibition_days = delta.days + 1

    # 참여 작가 수
    artist_count = len([a.strip() for a in s.artists.split(",") if a.strip()]) if s.artists else None

    return {
        "전시 제목": s.exhibition_title,
        "전시 일수": exhibition_days,
        "참여 작가 수_총(팀)": artist_count,
        "총 사용 예산": s.total_budget or None,
        "전시 사용 예산": s.budget_exhibition or None,
        "부대 사용 예산": s.budget_supplementary or None,
        "예산 계획액": s.budget_planned or None,
        "총수입": s.total_revenue or None,
        "입장 수입": s.ticket_revenue or None,
        "총 관객수": s.total_visitors or None,
        "일평균 관객수": (s.total_visitors // exhibition_days) if (s.total_visitors and exhibition_days and exhibition_days > 0) else None,
        "유료 관객수": (s.visitor_general + s.visitor_student) or None,
        "무료/초대 관객수": s.visitor_invitation or None,
        "학생 관객수(만 24세 이하)": s.visitor_student or None,
        "단체 관객수": s.visitor_group or None,
        "디스커버서울패스 관객수": s.visitor_discover or None,
        "예술인패스 관객수": s.visitor_artpass or None,
        "오프닝 참석 인원": s.opening_attendance or None,
        "운영 인력_총": s.staff_total or None,
        "스태프 수": s.staff_paid or None,
        "봉사자 수": s.staff_volunteer or None,
        "프로그램 총 수": s.program_count or None,
        "프로그램 총 회차": s.program_sessions or None,
        "프로그램 참여 인원": s.program_participants or None,
        "도슨트 참여 인원": s.docent_total or None,
        "정기 도슨트 참여 인원": s.docent_regular or None,
        "특별 도슨트 참여 인원": s.docent_special or None,
        "출품 작품 수_총": s.artwork_total or None,
        "출품 작품 수_회화": s.artwork_painting or None,
        "출품 작품 수_조각": s.artwork_sculpture or None,
        "출품 작품 수_사진": s.artwork_photo or None,
        "출품 작품 수_설치": s.artwork_installation or None,
        "출품 작품 수_미디어": s.artwork_media or None,
        "출품 작품 수_기타": s.artwork_other or None,
        "언론 보도 건수": s.press_count or None,
        "웹 초청장 발송 수": s.web_invitation_count or None,
        "뉴스레터 오픈율": (s.newsletter_open_rate / 100) if s.newsletter_open_rate else None,
        "SNS 게시 건수": s.sns_posts or None,
        "SNS 피드백 합계": s.sns_feedback or None,
        "멤버십 회원수": s.membership_count or None,
    }
