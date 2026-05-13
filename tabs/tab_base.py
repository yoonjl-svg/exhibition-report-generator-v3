"""탭 B: 기본 정보 — 전시의 서술적 정보 입력"""

import streamlit as st
from datetime import date
from utils import add_item, remove_item
from ui_helpers import section_header, subsection


def render(tab):
    with tab:
        section_header(
            "EXHIBITION INPUT · BASIC",
            "기본 정보",
            "보고서의 뼈대가 되는 서술 정보를 입력합니다. 숫자는 다음 탭에서 입력합니다.",
        )

        # ── 본문 영역 2단 레이아웃: 전시 기본 (좌) + 기획진 (우) ──
        col_left, col_right = st.columns(2, gap="large")

        with col_left:
            subsection("BASIC", "전시 기본")
            st.text_input("전시 제목", key="exhibition_title")
            # 시작일 + 종료일은 내부에서 2열
            c1, c2 = st.columns(2)
            with c1:
                st.date_input("전시 시작일", key="period_start", value=None)
            with c2:
                st.date_input("전시 종료일", key="period_end", value=None)
            st.text_input("참여 작가 (쉼표 구분)", key="artists",
                          placeholder="구정연, 이미래, 장서영")
            # 자동 전시 일수 표시
            if st.session_state.period_start and st.session_state.period_end:
                days = (st.session_state.period_end - st.session_state.period_start).days + 1
                st.info(f"📅 전시 일수: **{days}일**")

        with col_right:
            subsection("CURATORIAL TEAM", "기획진")
            # 6개 필드를 2열×3행 (외부 컬럼이 좁아 6열은 무리)
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("책임기획", key="chief_curator")
                st.text_input("기획", key="curators")
                st.text_input("진행", key="coordinators")
            with c2:
                st.text_input("학예팀", key="curatorial_team")
                st.text_input("홍보", key="pr_person")
                st.text_input("후원", key="sponsors")

        st.divider()

        # ── 전시 주제와 내용 ──
        subsection("THEME", "전시 주제와 내용")
        st.text_area(
            "전시 에세이",
            key="theme_text",
            height=250,
            placeholder="전시의 주제, 기획 의도, 내용을 서술합니다.\n\n단락 사이에 빈 줄을 넣으면 보고서에서도 단락이 구분됩니다."
        )

        st.divider()

        # ── 전시 디자인 ──
        subsection("DESIGN", "전시 디자인")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("그래픽 디자인", key="graphic_designer",
                          placeholder="예: 페이퍼프레스")
        with c2:
            st.text_input("공간 구성", key="space_designer",
                          placeholder="예: 석운동")

        st.divider()

        # ── 전시실 구성 ──
        subsection("ROOMS", "전시실 구성")
        for i, room in enumerate(st.session_state.rooms):
            with st.expander(f"🏛️ {room.get('name', f'{i+1}전시실')}", expanded=(i == 0)):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.session_state.rooms[i]["name"] = st.text_input(
                        "전시실명", value=room.get("name", ""), key=f"room_name_{i}")
                with c2:
                    st.session_state.rooms[i]["artists"] = st.text_input(
                        "참여 작가", value=room.get("artists", ""), key=f"room_artists_{i}")

                st.session_state.rooms[i]["floor_plan_file"] = st.file_uploader(
                    "도면 이미지", type=["png", "jpg", "jpeg"], key=f"room_floor_{i}")
                st.session_state.rooms[i]["photo_files"] = st.file_uploader(
                    "전경 사진", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"room_photos_{i}")

        col_add, col_rm = st.columns(2)
        with col_add:
            if st.button("➕ 전시실 추가", key="add_room"):
                n = len(st.session_state.rooms) + 1
                add_item("rooms", {"name": f"{n}전시실", "artists": ""})
                st.rerun()
        with col_rm:
            if st.button("➖ 마지막 전시실 제거", key="rm_room"):
                remove_item("rooms", -1)
                st.rerun()

        st.divider()

        # ── 프로그램 (서술 정보) ──
        subsection("PROGRAMS", "전시 연계 프로그램")
        st.caption("프로그램 총 수와 참여 인원 합계는 '정량 데이터' 탭에서 입력합니다.")
        for i, prog in enumerate(st.session_state.related_programs):
            cols = st.columns([1.5, 3, 2, 1.5, 2.5])
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

        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ 프로그램 추가", key="add_prog"):
                add_item("related_programs", {"category": None, "title": "", "date": None, "participants": "", "note": ""})
                st.rerun()
        with c2:
            if st.button("➖ 마지막 프로그램 제거", key="rm_prog"):
                remove_item("related_programs", -1)
                st.rerun()

        st.divider()

        # ── 인쇄물 ──
        subsection("MATERIALS", "인쇄물 및 굿즈")
        for i, mat in enumerate(st.session_state.printed_materials):
            cols = st.columns([3, 2, 4])
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

        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ 인쇄물 추가", key="add_mat"):
                add_item("printed_materials", {"type": None, "quantity": "", "note": ""})
                st.rerun()
        with c2:
            if st.button("➖ 마지막 인쇄물 제거", key="rm_mat"):
                remove_item("printed_materials", -1)
                st.rerun()

        st.divider()

        # ── 홍보 방식 ──
        subsection("PROMOTION", "홍보 방식")
        st.text_area("광고", key="promo_advertising", height=80)
        st.text_area("보도자료", key="promo_press_release", height=80)
        c1, c2 = st.columns(2)
        with c1:
            st.text_area("웹 초청장", key="promo_web_invitation", height=80)
            st.text_area("뉴스레터", key="promo_newsletter", height=80)
        with c2:
            st.text_area("SNS", key="promo_sns", height=80)
            st.text_area("그 외", key="promo_other", height=80)

        st.divider()

        # ── 언론보도 리스트 ──
        subsection("PRESS", "언론보도 리스트")
        st.caption("보도 총 건수는 '정량 데이터' 탭에서 자동 집계됩니다.")

        # 엑셀 업로드 안내
        _has_press_data = any(p.get("outlet") for p in st.session_state.press_print) or \
                          any(p.get("outlet") for p in st.session_state.press_online)
        if _has_press_data:
            st.info("💡 '정량 데이터' 탭에서 엑셀로 업로드한 언론보도 데이터가 있습니다. 아래에서 수정하거나 추가 입력할 수 있습니다.")
        else:
            st.info("💡 '정량 데이터' 탭에서 전시 데이터 엑셀을 업로드하면 언론보도 리스트를 일괄 입력할 수 있습니다.")

        st.markdown("**일간지 및 월간지**")
        for i, item in enumerate(st.session_state.press_print):
            cols = st.columns([1.5, 1.5, 5, 2])
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

        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ 일간지 추가", key="add_pp"):
                add_item("press_print", {"outlet": "", "date": None, "title": "", "note": ""})
                st.rerun()
        with c2:
            if st.button("➖ 마지막 일간지 제거", key="rm_pp"):
                remove_item("press_print", -1)
                st.rerun()

        st.markdown("**온라인 매체**")
        for i, item in enumerate(st.session_state.press_online):
            cols = st.columns([1.5, 1.5, 4, 3])
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

        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ 온라인 매체 추가", key="add_po"):
                add_item("press_online", {"outlet": "", "date": None, "title": "", "url": ""})
                st.rerun()
        with c2:
            if st.button("➖ 마지막 온라인 매체 제거", key="rm_po"):
                remove_item("press_online", -1)
                st.rerun()

        st.divider()

        # ── 멤버십 ──
        subsection("MEMBERSHIP", "멤버십 커뮤니케이션")
        st.text_area("멤버십 관련 내용", key="membership_text", height=100)

        st.divider()

        # ── 관객 후기 ──
        subsection("AUDIENCE REVIEWS", "관객 후기")
        for i, review in enumerate(st.session_state.visitor_reviews):
            cols = st.columns([1.5, 6, 2])
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

        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ 후기 추가", key="add_rev"):
                add_item("visitor_reviews", {"category": "긍정", "content": "", "source": ""})
                st.rerun()
        with c2:
            if st.button("➖ 마지막 후기 제거", key="rm_rev"):
                remove_item("visitor_reviews", -1)
                st.rerun()
