"""탭 B: 기본 정보 — 전시의 서술적 정보 입력

v5.3.20 레이아웃 재구성:
- Row 1 (4단, 각 25%): 전시 기본 + 기획진 + 전시 디자인 + 여백
- Row 2 (2단, 40%+60%): 전시 주제와 내용(높이 3배) + 전시실 구성(수직 스택)
- 전시실 카드: 참여 작가 한 줄 + 도면·전경 사진 가로 나란히
- 인쇄물 종류 컬럼 50% 축소
- 관객 후기 내용 컬럼 80%로 축소
- 모든 add/remove 버튼: use_container_width=False 로 통일된 자동 크기
"""

import streamlit as st
from datetime import date
from utils import add_item, remove_item
from ui_helpers import subsection


# ──────────────────────────────────────────────
# 버튼 헬퍼 — 모든 추가/제거 버튼이 동일한 자동 크기로 정렬되도록
# ──────────────────────────────────────────────

def _add_remove_buttons(
    label_add: str, label_rm: str,
    key_add: str, key_rm: str,
    item_key: str, default_item: dict,
):
    """좌측 정렬된 작은 자동 크기 버튼 한 쌍. use_container_width=False."""
    c1, c2, _ = st.columns([1, 1, 8])
    with c1:
        if st.button(label_add, key=key_add):
            add_item(item_key, default_item)
            st.rerun()
    with c2:
        if st.button(label_rm, key=key_rm):
            remove_item(item_key, -1)
            st.rerun()


# ──────────────────────────────────────────────
# 전시실 카드 렌더
# ──────────────────────────────────────────────

def _render_room(i: int, room: dict):
    """단일 전시실 — 헤더 + 참여 작가 + (도면 + 전경 사진 가로 나란히)."""
    st.markdown(
        f'<div style="font-size: 13px; font-weight: 700; color: #20231f; '
        f'margin: 10px 0 4px 0;">{room.get("name", f"{i+1}전시실")}</div>',
        unsafe_allow_html=True,
    )
    st.session_state.rooms[i]["artists"] = st.text_input(
        "참여 작가", value=room.get("artists", ""), key=f"room_artists_{i}")
    uc1, uc2 = st.columns(2)
    with uc1:
        st.session_state.rooms[i]["floor_plan_file"] = st.file_uploader(
            "도면", type=["png", "jpg", "jpeg"], key=f"room_floor_{i}")
    with uc2:
        st.session_state.rooms[i]["photo_files"] = st.file_uploader(
            "전경 사진", type=["png", "jpg", "jpeg"],
            accept_multiple_files=True, key=f"room_photos_{i}")


# ──────────────────────────────────────────────
# 메인 렌더
# ──────────────────────────────────────────────

def render(tab):
    with tab:
        # ────────────────────────────────────────
        # Row 1: 전시 기본 + 기획진 + 전시 디자인 (각 25%, 우측 25% 여백)
        # ────────────────────────────────────────
        c_basic, c_team, c_design, _spacer = st.columns([1, 1, 1, 1], gap="large")

        with c_basic:
            subsection("", "전시 기본")
            st.text_input("전시 제목", key="exhibition_title")
            d1, d2 = st.columns(2)
            with d1:
                st.date_input("전시 시작일", key="period_start", value=None)
            with d2:
                st.date_input("전시 종료일", key="period_end", value=None)
            st.text_input("참여 작가 (쉼표 구분)", key="artists",
                          placeholder="구정연, 이미래, 장서영")
            if st.session_state.period_start and st.session_state.period_end:
                days = (st.session_state.period_end - st.session_state.period_start).days + 1
                st.info(f"📅 전시 일수: **{days}일**")

        with c_team:
            subsection("", "기획진")
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
            subsection("", "전시 디자인")
            st.text_input("그래픽 디자인", key="graphic_designer",
                          placeholder="예: 페이퍼프레스")
            st.text_input("공간 구성", key="space_designer",
                          placeholder="예: 석운동")

        st.divider()

        # ────────────────────────────────────────
        # Row 2: 전시 주제와 내용 (40%) + 전시실 구성 (60%)
        # ────────────────────────────────────────
        col_theme, col_rooms = st.columns([2, 3], gap="large")

        with col_theme:
            subsection("", "전시 주제와 내용")
            st.text_area(
                "전시 에세이",
                key="theme_text",
                height=750,  # 기존 250 × 3
                placeholder=(
                    "전시의 주제, 기획 의도, 내용을 서술합니다.\n\n"
                    "단락 사이에 빈 줄을 넣으면 보고서에서도 단락이 구분됩니다."
                ),
            )

        with col_rooms:
            subsection("", "전시실 구성")
            for i, room in enumerate(st.session_state.rooms):
                _render_room(i, room)
            _add_remove_buttons(
                "➕ 전시실 추가", "➖ 마지막 제거",
                "add_room", "rm_room",
                "rooms", {"name": f"{len(st.session_state.rooms) + 1}전시실", "artists": ""},
            )

        st.divider()

        # ────────────────────────────────────────
        # 전시 연계 프로그램 — 구분/일자/참여인원 50% 축소
        # ────────────────────────────────────────
        subsection("", "전시 연계 프로그램")
        st.caption("프로그램 총 수와 참여 인원 합계는 '정량 데이터' 탭에서 입력합니다.")
        for i, prog in enumerate(st.session_state.related_programs):
            cols = st.columns([0.75, 3, 1, 0.75, 2.5])
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

        st.divider()

        # ────────────────────────────────────────
        # 인쇄물 + 홍보 방식 (각 50%) — 인쇄물 종류 50% 축소
        # ────────────────────────────────────────
        col_mat, col_promo = st.columns(2, gap="large")

        with col_mat:
            subsection("", "인쇄물 및 굿즈")
            for i, mat in enumerate(st.session_state.printed_materials):
                # 기존 [2, 1.5, 3] → 종류 50% 축소: [1.0, 1.5, 3]
                cols = st.columns([1.0, 1.5, 3])
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

        with col_promo:
            subsection("", "홍보 방식")
            st.text_area("광고", key="promo_advertising", height=80)
            st.text_area("보도자료", key="promo_press_release", height=80)
            pc1, pc2 = st.columns(2)
            with pc1:
                st.text_area("웹 초청장", key="promo_web_invitation", height=80)
                st.text_area("뉴스레터", key="promo_newsletter", height=80)
            with pc2:
                st.text_area("SNS", key="promo_sns", height=80)
                st.text_area("그 외", key="promo_other", height=80)

        st.divider()

        # ────────────────────────────────────────
        # 언론보도 — 일간지/월간지 + 온라인 2단 (각 50%)
        # ────────────────────────────────────────
        subsection("", "언론보도 리스트")
        st.caption("보도 총 건수는 '정량 데이터' 탭에서 자동 집계됩니다.")
        _has_press_data = any(p.get("outlet") for p in st.session_state.press_print) or \
                          any(p.get("outlet") for p in st.session_state.press_online)
        if _has_press_data:
            st.info("💡 '정량 데이터' 탭에서 엑셀로 업로드한 언론보도 데이터가 있습니다. 아래에서 수정·추가 가능합니다.")
        else:
            st.info("💡 '정량 데이터' 탭에서 전시 데이터 엑셀을 업로드하면 언론보도 리스트를 일괄 입력할 수 있습니다.")

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
            )

        st.divider()

        # ────────────────────────────────────────
        # 관객 후기 — 분류·출처 50% 축소(기존), 내용 80%로 축소(신규)
        # ────────────────────────────────────────
        subsection("", "관객 후기")
        for i, review in enumerate(st.session_state.visitor_reviews):
            # 기존 [0.75, 6, 1] → 내용 80%: [0.75, 4.8, 1]
            cols = st.columns([0.75, 4.8, 1])
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
