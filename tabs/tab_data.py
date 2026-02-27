"""탭 A: 정량 데이터 — 분석의 대상이 되는 모든 숫자"""

import streamlit as st


def render(tab):
    with tab:
        st.markdown('<div class="section-header">📊 정량 데이터</div>', unsafe_allow_html=True)
        st.caption("숫자를 입력하면 다음 탭에서 과거 전시와의 비교 분석이 자동 생성됩니다.")

        # ════════════════════════════════════════
        # 1. 예산
        # ════════════════════════════════════════
        st.subheader("💰 예산 및 수입")

        col1, col2 = st.columns(2)
        with col1:
            st.number_input("전시 사용 예산 (원)", min_value=0, step=1_000_000,
                            key="budget_exhibition", format="%d")
        with col2:
            st.number_input("부대 사용 예산 (원)", min_value=0, step=100_000,
                            key="budget_supplementary", format="%d")

        # 총 사용 예산 자동 합산
        total_budget = st.session_state.budget_exhibition + st.session_state.budget_supplementary
        st.session_state.total_budget = total_budget
        if total_budget > 0:
            st.metric("총 사용 예산", f"{total_budget:,}원")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("예산 계획액 (원)", min_value=0, step=1_000_000,
                            key="budget_planned", format="%d")
        with col2:
            st.number_input("입장 수입 (원)", min_value=0, step=100_000,
                            key="ticket_revenue", format="%d")
        with col3:
            st.number_input("기타 수입 (원)", min_value=0, step=100_000,
                            key="other_revenue", format="%d")

        # 총수입 자동 합산
        total_revenue = st.session_state.ticket_revenue + st.session_state.other_revenue
        st.session_state.total_revenue = total_revenue
        if total_revenue > 0:
            st.metric("총수입", f"{total_revenue:,}원")

        # 자동 계산 표시
        if total_budget > 0:
            metrics = st.columns(3)
            with metrics[0]:
                if st.session_state.budget_exhibition and st.session_state.budget_supplementary:
                    ratio = st.session_state.budget_exhibition / total_budget * 100
                    st.metric("전시비 비율", f"{ratio:.1f}%")
            with metrics[1]:
                if total_revenue:
                    recovery = total_revenue / total_budget * 100
                    st.metric("예산 회수율", f"{recovery:.1f}%")
            with metrics[2]:
                if st.session_state.budget_planned:
                    exec_rate = total_budget / st.session_state.budget_planned * 100
                    st.metric("집행률", f"{exec_rate:.1f}%")

        st.divider()

        # ════════════════════════════════════════
        # 2. 관객
        # ════════════════════════════════════════
        st.subheader("👥 관객")

        col1, col2 = st.columns(2)
        with col1:
            st.number_input("총 관객수", min_value=0, step=100,
                            key="total_visitors", format="%d")
        with col2:
            # 일평균 자동 계산
            days = None
            if st.session_state.period_start and st.session_state.period_end:
                days = (st.session_state.period_end - st.session_state.period_start).days + 1
            if st.session_state.total_visitors and days and days > 0:
                daily_avg = st.session_state.total_visitors // days
                st.metric("일평균 관객수 (자동)", f"{daily_avg:,}명")
            else:
                st.caption("일평균 관객수: 전시 기간 입력 시 자동 계산")

        st.markdown("**입장권별 관객 구성**")
        cols = st.columns(6)
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

        # 합계 자동 검증
        ticket_sum = (st.session_state.visitor_general + st.session_state.visitor_student +
                      st.session_state.visitor_invitation + st.session_state.visitor_artpass +
                      st.session_state.visitor_discover + st.session_state.visitor_discount)
        if ticket_sum > 0 and st.session_state.total_visitors > 0:
            if ticket_sum != st.session_state.total_visitors:
                st.warning(f"⚠️ 입장권별 합계({ticket_sum:,}명)와 총 관객수({st.session_state.total_visitors:,}명)가 다릅니다.")
            else:
                st.success(f"✅ 입장권별 합계 일치: {ticket_sum:,}명")

        col1, col2 = st.columns(2)
        with col1:
            st.number_input("단체 관객수", min_value=0, key="visitor_group", format="%d")
        with col2:
            st.number_input("오프닝 참석 인원", min_value=0, key="opening_attendance", format="%d")

        st.divider()

        # ════════════════════════════════════════
        # 3. 출품 작품
        # ════════════════════════════════════════
        st.subheader("🎨 출품 작품")

        cols = st.columns(6)
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

        # 출품 작품 수 자동 합산
        artwork_total = (st.session_state.artwork_painting + st.session_state.artwork_sculpture +
                         st.session_state.artwork_photo + st.session_state.artwork_installation +
                         st.session_state.artwork_media + st.session_state.artwork_other)
        st.session_state.artwork_total = artwork_total
        if artwork_total > 0:
            st.metric("출품 작품 수 (총)", f"{artwork_total}점")

        st.divider()

        # ════════════════════════════════════════
        # 4. 프로그램
        # ════════════════════════════════════════
        st.subheader("🎯 프로그램 & 도슨트")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("프로그램 총 수", min_value=0, key="program_count", format="%d")
        with col2:
            st.number_input("프로그램 총 회차", min_value=0, key="program_sessions", format="%d")
        with col3:
            st.number_input("프로그램 참여 인원", min_value=0, key="program_participants", format="%d")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("도슨트 참여 인원 (총)", min_value=0, key="docent_total", format="%d")
        with col2:
            st.number_input("정기 도슨트", min_value=0, key="docent_regular", format="%d")
        with col3:
            st.number_input("특별 도슨트", min_value=0, key="docent_special", format="%d")

        st.divider()

        # ════════════════════════════════════════
        # 5. 운영 인력
        # ════════════════════════════════════════
        st.subheader("👷 운영 인력")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("운영 인력 총원", min_value=0, key="staff_total", format="%d")
        with col2:
            st.number_input("유급 스태프", min_value=0, key="staff_paid", format="%d")
        with col3:
            st.number_input("봉사자", min_value=0, key="staff_volunteer", format="%d")

        st.divider()

        # ════════════════════════════════════════
        # 6. 홍보 지표
        # ════════════════════════════════════════
        st.subheader("📢 홍보 지표")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("언론 보도 건수", min_value=0, key="press_count", format="%d",
                            help="일간지+온라인 합계. '기반 정보' 탭의 보도 리스트와 연동됩니다.")
        with col2:
            st.number_input("웹 초청장 발송 수", min_value=0, key="web_invitation_count", format="%d")
        with col3:
            st.number_input("뉴스레터 오픈율 (%)", min_value=0.0, max_value=100.0,
                            step=0.1, key="newsletter_open_rate", format="%.1f")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("SNS 게시 건수", min_value=0, key="sns_posts", format="%d")
        with col2:
            st.number_input("SNS 피드백 합계", min_value=0, key="sns_feedback", format="%d")
        with col3:
            st.number_input("멤버십 회원수", min_value=0, key="membership_count", format="%d")

        # ── 보도 건수 자동 동기화 제안 ──
        print_count = len([p for p in st.session_state.press_print if p.get("outlet")])
        online_count = len([p for p in st.session_state.press_online if p.get("outlet")])
        list_total = print_count + online_count
        if list_total > 0 and st.session_state.press_count == 0:
            st.info(f"💡 '기반 정보' 탭에 보도 {list_total}건이 입력되어 있습니다. 언론 보도 건수를 {list_total}으로 설정하시겠습니까?")
            if st.button("자동 입력", key="sync_press"):
                st.session_state.press_count = list_total
                st.rerun()
