"""통합 탭: 전시 데이터 입력 (v5.3.23, 옵션 B)

기존 '기본 정보(B)' + '정량 데이터(A)' 두 탭을 단일 탭으로 통합.
- 상단: 엑셀 일괄 업로드 (예산·언론보도 4시트 템플릿)
- 본문: 섹션별 수동 입력
- 모든 입력 너비 정밀 적용 — 풀폭 강박 제거

섹션 순서:
  1. 전시 기본
  2. 전시 주제와 내용
  3. 전시실 구성
  4. 출품 작품
  5. 전시 연계 프로그램
  6. 운영 인력
  7. 예산 및 수입
  8. 관객
  9. 인쇄물 및 굿즈
  10. 홍보 방식
  11. 홍보 지표
  12. 언론보도 리스트
  13. 관객 후기
"""

import json
import streamlit as st
import pandas as pd
from datetime import date
from utils import add_item, remove_item
from ui_helpers import subsection
import excel_template


# ──────────────────────────────────────────────
# 공통 헬퍼
# ──────────────────────────────────────────────

def _add_remove_buttons(label_add, label_rm, key_add, key_rm, item_key, default_item, page_full=True):
    """추가/제거 버튼 한 쌍 — 페이지 ~15% 너비로 통일.

    page_full=True: 풀폭 컨텍스트, [1.5, 1.5, 7]
    page_full=False: 50% 부모 안 (i.e., col_mat·col_print 같은 컨텍스트), [3, 3, 4]
    """
    ratios = [1.5, 1.5, 7] if page_full else [3, 3, 4]
    c1, c2, _ = st.columns(ratios)
    with c1:
        if st.button(label_add, key=key_add, use_container_width=True):
            add_item(item_key, default_item)
            st.rerun()
    with c2:
        if st.button(label_rm, key=key_rm, use_container_width=True):
            remove_item(item_key, -1)
            st.rerun()


def _render_room(i: int, room: dict):
    """단일 전시실 — 헤더 + 참여 작가 + (도면 + 전경 사진 가로 1줄)."""
    st.markdown(
        f'<div style="font-size: 13px; font-weight: 700; color: #20231f; '
        f'margin: 8px 0 4px 0;">{room.get("name", f"{i+1}전시실")}</div>',
        unsafe_allow_html=True,
    )
    st.session_state.rooms[i]["artists"] = st.text_input(
        "참여 작가", value=room.get("artists", ""), key=f"room_artists_{i}")
    uc1, uc2 = st.columns(2, gap="small")
    # 라벨을 file_uploader 내부에서 분리 — Streamlit 기본 라벨은 dropzone과 묶여
    # 함께 클릭 가능해지므로, label_visibility="collapsed"로 숨기고 별도 markdown
    # 라벨을 두어 단순 텍스트로 표시.
    _label_style = (
        'font-size: 14px; font-weight: 500; color: #252a28; '
        'margin: 4px 0 4px 0; line-height: 1.3;'
    )
    with uc1:
        st.markdown(f'<div style="{_label_style}">도면</div>',
                    unsafe_allow_html=True)
        st.session_state.rooms[i]["floor_plan_file"] = st.file_uploader(
            "도면", type=["png", "jpg", "jpeg"], key=f"room_floor_{i}",
            label_visibility="collapsed")
    with uc2:
        st.markdown(f'<div style="{_label_style}">전경 사진</div>',
                    unsafe_allow_html=True)
        st.session_state.rooms[i]["photo_files"] = st.file_uploader(
            "전경 사진", type=["png", "jpg", "jpeg"],
            accept_multiple_files=True, key=f"room_photos_{i}",
            label_visibility="collapsed")


def _section_divider():
    """섹션 간 여백 + 가는 구분선."""
    st.markdown('<div style="margin-top: 18px;"></div>', unsafe_allow_html=True)
    st.divider()


# ──────────────────────────────────────────────
# 가져오기 (워크스페이스와 동일 모달 다이얼로그)
# 동일: 모달 형식, Excel/JSON 2탭, 6시트 템플릿, 파서
# 차이: 적용 대상 — 워크스페이스 = 새 전시, 본 탭 = 현재 전시에 덮어쓰기
# ──────────────────────────────────────────────

@st.dialog("가져오기")
def _show_data_import_modal():
    """워크스페이스 _show_import_modal과 동일 구조의 모달."""
    import_tabs = st.tabs(["Excel 템플릿", "JSON 파일"])
    with import_tabs[0]:
        _render_excel_import()
    with import_tabs[1]:
        _render_json_import()


def _show_import_warnings_if_any():
    """이전 import 경고가 있으면 표시 후 소거."""
    warnings = st.session_state.pop("_excel_import_warnings", None)
    if warnings:
        for w in warnings:
            st.warning(f"⚠️ {w}")


def _apply_imported_data(data: dict, exhibition_type=None):
    """파싱된 평면 dict을 현재 세션에 적용.

    init_session의 _pending_json 처리가 dates·중첩 list dates를 자동 변환하므로
    그대로 위임. rerun 후 위젯들이 새 값으로 다시 그려짐.
    """
    st.session_state["_pending_json"] = data
    if exhibition_type is not None:
        st.session_state["current_exhibition_type"] = exhibition_type


def _render_excel_import():
    """워크스페이스와 동일한 Excel 가져오기 UI — 단, 적용 대상만 다름."""
    st.markdown(
        "큐레이터가 외부에서 데이터를 정리한 뒤 한 번에 업로드할 수 있는 표준 템플릿입니다. "
        "폼 입력의 대체가 아니라 **보조 경로**이며, 업로드 후에도 검수·수정이 가능합니다."
    )
    col_dl, col_ul = st.columns([1, 2])
    with col_dl:
        try:
            tpl_bytes = excel_template.generate_template_xlsx()
            st.download_button(
                "템플릿 다운로드",
                data=tpl_bytes,
                file_name="ilmin_exhibition_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="input_dl_template",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"템플릿 생성 실패: {e}")

    with col_ul:
        uploaded = st.file_uploader(
            "작성 완료된 템플릿 업로드", type=["xlsx", "xls"], key="input_xlsx_upload",
        )

    if uploaded:
        if st.button("가져와서 현재 전시에 적용", type="primary",
                     use_container_width=True, key="input_do_xlsx_import"):
            try:
                result = excel_template.parse_template_xlsx(uploaded)
                if result["warnings"]:
                    st.session_state["_excel_import_warnings"] = result["warnings"]
                _apply_imported_data(result["data"], result.get("type"))
                st.rerun()
            except Exception as e:
                st.error(f"가져오기 실패: {e}")
                import traceback
                st.code(traceback.format_exc())


def _render_json_import():
    """워크스페이스와 동일한 JSON 가져오기 UI — 단, 적용 대상만 다름."""
    st.markdown(
        "이전에 저장한 v3 또는 v5 JSON 파일에서 데이터를 복원합니다. "
        "두 형식 모두 자동 인식되며, 업로드 후 검수·수정이 가능합니다."
    )
    uploaded = st.file_uploader(
        "JSON 파일 선택", type=["json"], key="input_json_upload",
        help="v3 형식(평면 data) 또는 v5 형식({data: {...}}) 모두 인식",
    )
    if uploaded is None:
        return
    if st.button("불러와서 현재 전시에 적용", type="primary",
                 use_container_width=True, key="input_do_json_import"):
        try:
            raw = json.loads(uploaded.read())
            # v5 형식이면 data만 추출, v3 형식이면 그대로
            data = raw["data"] if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
            exhibition_type = raw.get("type") if isinstance(raw, dict) else None
            _apply_imported_data(data, exhibition_type)
            st.rerun()
        except Exception as e:
            st.error(f"가져오기 실패: {e}")


# ──────────────────────────────────────────────
# 메인 렌더
# ──────────────────────────────────────────────

def render(tab):
    with tab:
        # ────────────────────────────────────────
        # 0. 상단 — 가져오기 (워크스페이스와 동일 모달 다이얼로그)
        # ────────────────────────────────────────
        _show_import_warnings_if_any()
        ib, _ = st.columns([1, 9])
        with ib:
            if st.button("가져오기", key="data_import_btn",
                         type="primary", use_container_width=True):
                _show_data_import_modal()

        _section_divider()

        # ════════════════════════════════════════
        # 1. 전시 기본 (기획진·전시 디자인을 하위 항목으로 통합)
        # ════════════════════════════════════════
        subsection("", "전시 기본")
        # 4단 + 미세 spacer: 기본(25%) / 기획진(31.625% = 1×1.15×1.10) /
        # 디자인(17% = 1×0.80×0.85) / 인력(25%) / spacer(1.375%)
        c_basic, c_team, c_design, c_staff, _sp = st.columns(
            [1, 1.265, 0.68, 1, 0.055], gap="large")

        with c_basic:
            st.text_input("전시 제목", key="exhibition_title")
            d1, d2 = st.columns(2)
            with d1:
                st.date_input("시작일", key="period_start", value=None)
            with d2:
                st.date_input("종료일", key="period_end", value=None)
            # 참여 작가: 다수의 작가명 입력을 위해 3배 높이의 textarea
            st.text_area("참여 작가 (쉼표 구분)", key="artists", height=120,
                         placeholder="구정연, 이미래, 장서영")
            if st.session_state.period_start and st.session_state.period_end:
                days = (st.session_state.period_end - st.session_state.period_start).days + 1
                st.info(f"📅 전시 일수: **{days}일**")

        with c_team:
            r1c1, r1c2 = st.columns(2)
            with r1c1:
                st.text_input("책임기획", key="chief_curator")
            with r1c2:
                st.text_input("기획", key="curators")
            r2c1, r2c2 = st.columns(2)
            with r2c1:
                st.text_input("진행", key="coordinators")
            with r2c2:
                st.text_input("홍보", key="pr_person")
            st.text_input("학예팀", key="curatorial_team")
            st.text_input("후원", key="sponsors")

        with c_design:
            st.text_input("그래픽 디자인", key="graphic_designer",
                          placeholder="예: 페이퍼프레스")
            st.text_input("공간 구성", key="space_designer",
                          placeholder="예: 석운동")

        with c_staff:
            # 인력: 유급 스태프 + 봉사자 (운영 인력 총원은 자동 합산)
            # 박스 너비 50% (사람 수는 작은 숫자라 좁아도 충분) — 우측 50% 여백
            sc, _ = st.columns([1, 1])
            with sc:
                st.number_input("유급 스태프", min_value=0, key="staff_paid", format="%d")
                st.number_input("봉사자", min_value=0, key="staff_volunteer", format="%d")
        # staff_total은 자동 합산 (KB 저장·분석 호환)
        st.session_state.staff_total = st.session_state.staff_paid + st.session_state.staff_volunteer

        # ── 예산 — '전시 기본' 헤더 아래, 1행 5열로 통일 ──
        # 순서: 예산 계획액 → 전시 사용 → 부대 사용 → 입장 수입 → 기타 수입
        cols = st.columns([1.3, 1.3, 1.3, 1.3, 1.3, 3.5], gap="small")
        with cols[0]:
            st.number_input("예산 계획액 (원)", min_value=0, step=1_000_000,
                            key="budget_planned", format="%d")
        with cols[1]:
            st.number_input("전시 사용 예산 (원)", min_value=0, step=1_000_000,
                            key="budget_exhibition", format="%d")
        with cols[2]:
            st.number_input("부대 사용 예산 (원)", min_value=0, step=100_000,
                            key="budget_supplementary", format="%d")
        with cols[3]:
            st.number_input("입장 수입 (원)", min_value=0, step=100_000,
                            key="ticket_revenue", format="%d")
        with cols[4]:
            st.number_input("기타 수입 (원)", min_value=0, step=100_000,
                            key="other_revenue", format="%d")

        total_budget = st.session_state.budget_exhibition + st.session_state.budget_supplementary
        st.session_state.total_budget = total_budget
        total_revenue = st.session_state.ticket_revenue + st.session_state.other_revenue
        st.session_state.total_revenue = total_revenue

        # 자동 계산 표시
        if total_budget > 0 or total_revenue > 0:
            mc1, mc2, mc3, mc4, _ = st.columns([1.3, 1.3, 1.3, 1.3, 4.8])
            with mc1:
                if total_budget > 0:
                    st.metric("총 예산", f"{total_budget:,}원")
            with mc2:
                if total_revenue > 0:
                    st.metric("총 수입", f"{total_revenue:,}원")
            with mc3:
                if st.session_state.budget_exhibition and st.session_state.budget_supplementary:
                    ratio = st.session_state.budget_exhibition / total_budget * 100
                    st.metric("전시비 비율", f"{ratio:.1f}%")
            with mc4:
                if total_revenue and total_budget:
                    recovery = total_revenue / total_budget * 100
                    st.metric("회수율", f"{recovery:.1f}%")

        # 업로드된 예산 미리보기 (있을 때만)
        if st.session_state.get("budget_summary") and any(
                x.get("category") for x in st.session_state.budget_summary):
            with st.expander("📋 업로드된 예산 집행 내역", expanded=False):
                summary_df = pd.DataFrame(st.session_state.budget_summary)
                summary_df = summary_df[summary_df["category"].astype(bool)]
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

        if st.session_state.get("budget_details") and any(
                x.get("subcategory") or x.get("detail") for x in st.session_state.budget_details):
            with st.expander("📋 업로드된 예산 세부 내역", expanded=False):
                details_df = pd.DataFrame(st.session_state.budget_details)
                details_df = details_df[details_df["subcategory"].astype(bool) | details_df["detail"].astype(bool)]
                st.dataframe(details_df, use_container_width=True, hide_index=True)

        _section_divider()

        # ════════════════════════════════════════
        # 2. 관객 (전시 기본 직후로 이동 — v5.3.35)
        # ════════════════════════════════════════
        subsection("", "관객")

        cols = st.columns([1.2, 1.2, 7.6])
        with cols[0]:
            st.number_input("총 관객수", min_value=0, step=100,
                            key="total_visitors", format="%d")
        with cols[1]:
            days = None
            if st.session_state.period_start and st.session_state.period_end:
                days = (st.session_state.period_end - st.session_state.period_start).days + 1
            if st.session_state.total_visitors and days and days > 0:
                daily_avg = st.session_state.total_visitors // days
                st.metric("일평균 (자동)", f"{daily_avg:,}명")
            else:
                st.caption("일평균: 기간 입력 시 자동")

        st.markdown("**입장권별 구성**")
        # 8개 칸 균일 + 좌측 클러스터 (우측 spacer 7) — 더 조밀하게.
        cols = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 7], gap="small")
        with cols[0]:
            st.number_input("일반", min_value=0, key="visitor_general", format="%d")
        with cols[1]:
            st.number_input("학생", min_value=0, key="visitor_student", format="%d")
        with cols[2]:
            st.number_input("초대권", min_value=0, key="visitor_invitation", format="%d")
        with cols[3]:
            st.number_input("예술인패스", min_value=0, key="visitor_artpass", format="%d")
        with cols[4]:
            st.number_input("디스커버서울패스", min_value=0, key="visitor_discover", format="%d")
        with cols[5]:
            st.number_input("기타 할인", min_value=0, key="visitor_discount", format="%d")
        with cols[6]:
            st.number_input("단체 관객", min_value=0, key="visitor_group", format="%d")
        with cols[7]:
            st.number_input("오프닝 참석", min_value=0, key="opening_attendance", format="%d")

        ticket_sum = (st.session_state.visitor_general + st.session_state.visitor_student +
                      st.session_state.visitor_invitation + st.session_state.visitor_artpass +
                      st.session_state.visitor_discover + st.session_state.visitor_discount)
        if ticket_sum > 0 and st.session_state.total_visitors > 0:
            if ticket_sum != st.session_state.total_visitors:
                st.warning(f"⚠️ 입장권별 합계({ticket_sum:,}명)와 총 관객수({st.session_state.total_visitors:,}명)가 다릅니다.")
            else:
                st.success(f"✅ 입장권별 합계 일치: {ticket_sum:,}명")

        # 주차별 관객 — 11주차, 1줄 배치 (좌측 클러스터 + gap small)
        st.markdown("**주차별 관객 수**")
        week_cols = st.columns([1] * 11 + [6], gap="small")
        weekly = st.session_state.get("weekly_visitors", {})
        new_weekly = {}
        for i in range(11):
            with week_cols[i]:
                label = f"{i+1}주"
                val = weekly.get(label, 0)
                entered = st.number_input(label, min_value=0, value=val,
                                          key=f"weekly_{i}", format="%d")
                if entered > 0:
                    new_weekly[label] = entered
        st.session_state.weekly_visitors = new_weekly

        _section_divider()

        # ════════════════════════════════════════
        # 3. 전시 주제와 내용 + 4. 전시실 구성
        # ════════════════════════════════════════
        col_theme, col_rooms = st.columns([2, 3], gap="large")

        with col_theme:
            subsection("", "전시 주제와 내용")
            st.text_area("전시 서문", key="theme_text", height=300)

        with col_rooms:
            # 헤더 + 업로더 안내 한 번만 (각 dropzone의 중복 안내는 CSS로 숨김)
            st.markdown(
                '<div style="margin: 18px 0 6px 0; display: flex; '
                'align-items: baseline; gap: 12px;">'
                '<div style="font-size: 14px; font-weight: 700; '
                'color: #20231f; line-height: 1.3;">전시실 구성</div>'
                '<div style="font-size: 12px; color: #646b61;">'
                '※ 업로드: 200MB 이하 · PNG · JPG · JPEG</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            # 2x2 그리드: 1줄에 2개씩 배치 (기본 4개 = 1·2·3·프로젝트 룸)
            rooms = st.session_state.rooms
            for start in range(0, len(rooms), 2):
                cols = st.columns(2, gap="medium")
                for offset, col in enumerate(cols):
                    idx = start + offset
                    if idx >= len(rooms):
                        break
                    with col:
                        _render_room(idx, rooms[idx])
            _add_remove_buttons(
                "➕ 전시실 추가", "➖ 마지막 제거",
                "add_room", "rm_room",
                "rooms",
                {"name": f"{len(st.session_state.rooms) + 1}전시실", "artists": ""},
                page_full=False,
            )

        _section_divider()

        # ════════════════════════════════════════
        # 4. 출품 작품 — 6 매체 × 좁은 컬럼
        # ════════════════════════════════════════
        subsection("", "출품 작품 (매체별)")
        # 6개 narrow + 큰 spacer — 더 조밀하게
        cols = st.columns([1, 1, 1, 1, 1, 1, 8], gap="small")
        with cols[0]:
            st.number_input("회화", min_value=0, key="artwork_painting", format="%d")
        with cols[1]:
            st.number_input("조각", min_value=0, key="artwork_sculpture", format="%d")
        with cols[2]:
            st.number_input("사진", min_value=0, key="artwork_photo", format="%d")
        with cols[3]:
            st.number_input("설치", min_value=0, key="artwork_installation", format="%d")
        with cols[4]:
            st.number_input("미디어", min_value=0, key="artwork_media", format="%d")
        with cols[5]:
            st.number_input("기타", min_value=0, key="artwork_other", format="%d")

        artwork_total = (st.session_state.artwork_painting + st.session_state.artwork_sculpture +
                         st.session_state.artwork_photo + st.session_state.artwork_installation +
                         st.session_state.artwork_media + st.session_state.artwork_other)
        st.session_state.artwork_total = artwork_total
        if artwork_total > 0:
            mc, _ = st.columns([1, 9])
            with mc:
                st.metric("총 작품 수", f"{artwork_total}점")

        _section_divider()

        # ════════════════════════════════════════
        # 5. 전시 연계 프로그램
        # ════════════════════════════════════════
        subsection("", "전시 연계 프로그램")

        # 상세 행 (반복)
        # 일자는 YYYY/MM/DD+달력 아이콘 폭 확보(1.3), 참여 인원은 라벨 한 줄(1.0)
        for i, prog in enumerate(st.session_state.related_programs):
            cols = st.columns([0.9, 3, 1.3, 1.0, 2, 1.8])
            with cols[0]:
                cat_options = ["아티스트 토크", "강연", "워크숍", "스크리닝", "퍼포먼스", "기타"]
                cat_val = prog.get("category")
                cat_idx = cat_options.index(cat_val) if cat_val in cat_options else None
                st.session_state.related_programs[i]["category"] = st.selectbox(
                    "구분", options=cat_options, index=cat_idx, key=f"prog_cat_{i}",
                    placeholder="선택")
            with cols[1]:
                st.session_state.related_programs[i]["title"] = st.text_input(
                    "제목", value=prog.get("title", ""), key=f"prog_title_{i}")
            with cols[2]:
                date_val = prog.get("date")
                if not isinstance(date_val, date):
                    date_val = None
                st.session_state.related_programs[i]["date"] = st.date_input(
                    "일자", value=date_val, key=f"prog_date_{i}")
            with cols[3]:
                st.session_state.related_programs[i]["participants"] = st.text_input(
                    "참여 인원", value=prog.get("participants", ""), key=f"prog_part_{i}")
            with cols[4]:
                st.session_state.related_programs[i]["note"] = st.text_input(
                    "비고", value=prog.get("note", ""), key=f"prog_note_{i}")

        _add_remove_buttons(
            "➕ 프로그램 추가", "➖ 마지막 제거",
            "add_prog", "rm_prog",
            "related_programs",
            {"category": None, "title": "", "date": None, "participants": "", "note": ""},
        )

        # 프로그램 요약 수치
        st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
        cols = st.columns([1, 1, 1, 1, 1, 5], gap="small")
        with cols[0]:
            st.number_input("프로그램 수", min_value=0, key="program_count", format="%d")
        with cols[1]:
            st.number_input("총 회차", min_value=0, key="program_sessions", format="%d")
        with cols[2]:
            st.number_input("총 참여", min_value=0, key="program_participants", format="%d")
        with cols[3]:
            st.number_input("도슨트 정기", min_value=0, key="docent_regular", format="%d")
        with cols[4]:
            st.number_input("도슨트 특별", min_value=0, key="docent_special", format="%d")
        st.session_state.docent_total = st.session_state.docent_regular + st.session_state.docent_special

        _section_divider()

        # ════════════════════════════════════════
        # 인쇄물 및 굿즈 (단독 섹션)
        # ════════════════════════════════════════
        subsection("", "인쇄물 및 굿즈")
        # col_mat이 사라졌으므로 컬럼은 풀폭 기준 — 우측 큰 여백으로 박스 좁게
        for i, mat in enumerate(st.session_state.printed_materials):
            cols = st.columns([0.6, 0.4, 1.5, 7.5])
            with cols[0]:
                mat_options = ["포스터", "리플렛", "초대장", "굿즈", "기타"]
                mat_val = mat.get("type")
                mat_idx = mat_options.index(mat_val) if mat_val in mat_options else None
                st.session_state.printed_materials[i]["type"] = st.selectbox(
                    "종류", options=mat_options, index=mat_idx, key=f"mat_type_{i}",
                    placeholder="선택")
            with cols[1]:
                st.session_state.printed_materials[i]["quantity"] = st.text_input(
                    "수량", value=mat.get("quantity", ""), key=f"mat_qty_{i}")
            with cols[2]:
                st.session_state.printed_materials[i]["note"] = st.text_input(
                    "비고", value=mat.get("note", ""), key=f"mat_note_{i}")

        _add_remove_buttons(
            "➕ 인쇄물 추가", "➖ 마지막 제거",
            "add_mat", "rm_mat",
            "printed_materials", {"type": None, "quantity": "", "note": ""},
        )

        _section_divider()

        # ════════════════════════════════════════
        # 홍보 방식 (단독 섹션)
        # ════════════════════════════════════════
        subsection("", "홍보 방식")
        # 풀폭에서 좌측 50%만 사용
        promo_l, _ = st.columns([1, 1])
        with promo_l:
            st.text_area("광고", key="promo_advertising", height=80)
            st.text_area("보도자료", key="promo_press_release", height=80)
            pc1, pc2 = st.columns(2)
            with pc1:
                st.text_area("웹 초청장", key="promo_web_invitation", height=80)
                st.text_area("뉴스레터", key="promo_newsletter", height=80)
            with pc2:
                st.text_area("SNS", key="promo_sns", height=80)
                st.text_area("그 외", key="promo_other", height=80)

        _section_divider()

        # ════════════════════════════════════════
        # 11. 홍보 지표
        # ════════════════════════════════════════
        subsection("", "홍보 지표")
        cols = st.columns([1.2, 1.2, 1.2, 6.4], gap="small")
        with cols[0]:
            st.number_input("언론 보도 건수", min_value=0, key="press_count", format="%d",
                            help="일간지+온라인 합계. 본 섹션 하단 보도 리스트와 연동.")
        with cols[1]:
            st.number_input("웹 초청장 발송", min_value=0, key="web_invitation_count", format="%d")
        with cols[2]:
            st.number_input("뉴스레터 오픈율 (%)", min_value=0.0, max_value=100.0,
                            step=0.1, key="newsletter_open_rate", format="%.1f")

        cols = st.columns([1.2, 1.2, 1.2, 6.4], gap="small")
        with cols[0]:
            st.number_input("SNS 게시", min_value=0, key="sns_posts", format="%d")
        with cols[1]:
            st.number_input("SNS 피드백", min_value=0, key="sns_feedback", format="%d")
        with cols[2]:
            st.number_input("멤버십 회원수", min_value=0, key="membership_count", format="%d")

        st.markdown("**SNS 상세 통계**")
        st.caption("인스타그램 기준 정량 지표.")
        cols = st.columns([1, 1, 1, 1, 6], gap="small")
        with cols[0]:
            st.number_input("팔로워", min_value=0, key="sns_followers", format="%d")
        with cols[1]:
            st.number_input("팔로워 증가", min_value=0, key="sns_followers_gained", format="%d",
                            help="전시 기간 중 순증가")
        with cols[2]:
            st.number_input("평균 좋아요", min_value=0, key="sns_avg_likes", format="%d")
        with cols[3]:
            st.number_input("최고 좋아요", min_value=0, key="sns_best_likes", format="%d")
        bc, _ = st.columns([4, 6])
        with bc:
            st.text_input("최고 반응 게시물 내용", key="sns_best_post",
                          placeholder="예: 한강주조 겨울 에디션 게시물")

        _section_divider()

        # ════════════════════════════════════════
        # 12. 언론보도 리스트 — 일간지/월간지 + 온라인 각 50%
        # ════════════════════════════════════════
        subsection("", "언론보도 리스트")
        _has_press_data = any(p.get("outlet") for p in st.session_state.press_print) or \
                          any(p.get("outlet") for p in st.session_state.press_online)
        if _has_press_data:
            st.info("💡 엑셀로 업로드한 언론보도 데이터가 있습니다. 아래에서 수정·추가 가능합니다.")
        else:
            st.caption("상단의 '엑셀 일괄 업로드'로 일괄 입력도 가능합니다.")

        # 보도 건수 자동 동기화 제안
        print_count = len([p for p in st.session_state.press_print if p.get("outlet")])
        online_count = len([p for p in st.session_state.press_online if p.get("outlet")])
        list_total = print_count + online_count
        if list_total > 0 and st.session_state.press_count == 0:
            sc, _ = st.columns([3, 7])
            with sc:
                if st.button(f"💡 보도 건수를 {list_total}건으로 자동 입력",
                             key="sync_press", use_container_width=True):
                    st.session_state.press_count = list_total
                    st.rerun()

        col_print, col_online = st.columns(2, gap="large")

        with col_print:
            st.markdown("**일간지 및 월간지**")
            for i, item in enumerate(st.session_state.press_print):
                cols = st.columns([1.5, 1.5, 4, 2])
                with cols[0]:
                    st.session_state.press_print[i]["outlet"] = st.text_input(
                        "매체명", value=item.get("outlet", ""), key=f"pp_outlet_{i}")
                with cols[1]:
                    pp_date_val = item.get("date")
                    if not isinstance(pp_date_val, date):
                        pp_date_val = None
                    st.session_state.press_print[i]["date"] = st.date_input(
                        "일자", value=pp_date_val, key=f"pp_date_{i}")
                with cols[2]:
                    st.session_state.press_print[i]["title"] = st.text_input(
                        "제목", value=item.get("title", ""), key=f"pp_title_{i}")
                with cols[3]:
                    st.session_state.press_print[i]["note"] = st.text_input(
                        "비고", value=item.get("note", ""), key=f"pp_note_{i}")

            _add_remove_buttons(
                "➕ 일간지 추가", "➖ 마지막 제거",
                "add_pp", "rm_pp",
                "press_print", {"outlet": "", "date": None, "title": "", "note": ""},
                page_full=False,
            )

        with col_online:
            st.markdown("**온라인 매체**")
            for i, item in enumerate(st.session_state.press_online):
                cols = st.columns([1.5, 1.5, 3, 3])
                with cols[0]:
                    st.session_state.press_online[i]["outlet"] = st.text_input(
                        "매체명", value=item.get("outlet", ""), key=f"po_outlet_{i}")
                with cols[1]:
                    po_date_val = item.get("date")
                    if not isinstance(po_date_val, date):
                        po_date_val = None
                    st.session_state.press_online[i]["date"] = st.date_input(
                        "일자", value=po_date_val, key=f"po_date_{i}")
                with cols[2]:
                    st.session_state.press_online[i]["title"] = st.text_input(
                        "제목", value=item.get("title", ""), key=f"po_title_{i}")
                with cols[3]:
                    st.session_state.press_online[i]["url"] = st.text_input(
                        "URL", value=item.get("url", ""), key=f"po_url_{i}")

            _add_remove_buttons(
                "➕ 온라인 추가", "➖ 마지막 제거",
                "add_po", "rm_po",
                "press_online", {"outlet": "", "date": None, "title": "", "url": ""},
                page_full=False,
            )

        _section_divider()

        # ════════════════════════════════════════
        # 13. 관객 후기
        # ════════════════════════════════════════
        subsection("", "관객 후기")
        for i, review in enumerate(st.session_state.visitor_reviews):
            cols = st.columns([0.75, 4.8, 1, 3.45])
            with cols[0]:
                st.session_state.visitor_reviews[i]["category"] = st.selectbox(
                    "분류", ["긍정", "부정", "건의"], key=f"rev_cat_{i}",
                    index=["긍정", "부정", "건의"].index(review.get("category", "긍정"))
                    if review.get("category", "긍정") in ["긍정", "부정", "건의"] else 0)
            with cols[1]:
                st.session_state.visitor_reviews[i]["content"] = st.text_input(
                    "내용", value=review.get("content", ""), key=f"rev_content_{i}")
            with cols[2]:
                st.session_state.visitor_reviews[i]["source"] = st.text_input(
                    "출처", value=review.get("source", ""), key=f"rev_source_{i}")

        _add_remove_buttons(
            "➕ 후기 추가", "➖ 마지막 제거",
            "add_rev", "rm_rev",
            "visitor_reviews", {"category": "긍정", "content": "", "source": ""},
        )
