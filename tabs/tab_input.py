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
from kb_session import DERIVED_TOTALS
import excel_template


# ──────────────────────────────────────────────
# 공통 헬퍼
# ──────────────────────────────────────────────

def _derived_total(total_key: str) -> int:
    """파생 합계 계산 — 왕복 무결성 보장.

    로드된 레코드의 구성요소가 그대로면(기준선과 동일) 저장된 합계를 보존하고,
    사용자가 구성요소를 한 번이라도 바꾸면 구성요소 합으로 재계산한다.
    신규 입력(기준선 없음)은 항상 구성요소 합. 결과를 session_state에 기록.
    """
    comp_keys = DERIVED_TOTALS[total_key]
    comp = tuple(st.session_state.get(k) or 0 for k in comp_keys)
    baseline = st.session_state.get(f"_baseline_{total_key}")
    stored = st.session_state.get(total_key)
    if baseline is not None and comp == baseline and stored is not None:
        total = stored                  # 구성요소 미변경 → 저장값 보존
    else:
        total = sum(comp)               # 신규/변경 → 구성요소 합
    st.session_state[total_key] = total
    return total


def _comma_reformat(dkey: str, key: str):
    """text_input on_change 콜백 — 숫자만 추출해 정수 저장 + 천 단위 쉼표 재표시."""
    raw = str(st.session_state.get(dkey, ""))
    digits = "".join(ch for ch in raw if ch.isdigit())
    val = int(digits) if digits else 0
    st.session_state[key] = val
    st.session_state[dkey] = f"{val:,}" if val else ""


def comma_int_input(label, key, help=None, label_visibility="visible"):
    """천 단위 쉼표로 표시되는 정수 입력칸(st.number_input 대체).

    HTML number 입력은 쉼표를 못 보여주므로 text_input으로 구현한다.
    - 데이터는 정수로 st.session_state[key]에 저장(분석·파생 합계 파이프라인 호환).
    - 표시 문자열은 _disp_{key}에 쉼표 포맷으로 보관.
    - 레코드 로드·엑셀 업로드 등으로 데이터 키가 바뀌면 표시를 자동 동기화.
    """
    dkey = f"_disp_{key}"
    data_val = int(st.session_state.get(key) or 0)
    cur = str(st.session_state.get(dkey, ""))
    cur_val = int("".join(ch for ch in cur if ch.isdigit()) or "0")
    if cur_val != data_val:          # 외부 변경 동기화(위젯 생성 전이라 대입 가능)
        st.session_state[dkey] = f"{data_val:,}" if data_val else ""
    st.text_input(label, key=dkey, help=help, label_visibility=label_visibility,
                  placeholder="0", on_change=_comma_reformat, args=(dkey, key))
    # 방어적 동기화: 표시 문자열을 항상 정수로 파싱해 데이터 키에 반영
    # (on_change가 어떤 이유로 누락돼도 데이터는 정확히 유지).
    final = str(st.session_state.get(dkey, ""))
    st.session_state[key] = int("".join(ch for ch in final if ch.isdigit()) or "0")
    return st.session_state[key]


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
            st.warning(f"{w}")


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
                st.info(f"전시 일수: **{days}일**")

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
            st.text_input("공간 조성", key="space_designer",
                          placeholder="예: 석운동")

        with c_staff:
            # 인력: 유급 스태프 + 봉사자 (운영 인력 총원은 자동 합산)
            # 박스 너비 50% (사람 수는 작은 숫자라 좁아도 충분) — 우측 50% 여백
            sc, _ = st.columns([1, 1])
            with sc:
                st.number_input("유급 스태프", min_value=0, key="staff_paid", format="%d")
                st.number_input("봉사자", min_value=0, key="staff_volunteer", format="%d")
        # staff_total — 구성요소 합(왕복 무결성: 미변경 시 저장값 보존)
        _derived_total("staff_total")

        # ── 예산 — '전시 기본' 헤더 아래, 1행 5열로 통일 ──
        # 순서: 예산 계획액 → 전시 사용 → 부대 사용 → 입장 수입 → 기타 수입
        cols = st.columns([1.3, 1.3, 1.3, 1.3, 1.3, 3.5], gap="small")
        with cols[0]:
            comma_int_input("예산 계획액 (원)", "budget_planned")
        with cols[1]:
            comma_int_input("전시 사용 예산 (원)", "budget_exhibition")
        with cols[2]:
            comma_int_input("부대 사용 예산 (원)", "budget_supplementary")
        with cols[3]:
            comma_int_input("입장 수입 (원)", "ticket_revenue")
        with cols[4]:
            comma_int_input("기타 수입 (원)", "other_revenue")

        total_budget = _derived_total("total_budget")
        total_revenue = _derived_total("total_revenue")

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

        # 저장된 합계 보존 안내 (구성요소 합과 다를 때만)
        _pres = []
        if (st.session_state.get("_baseline_total_revenue") is not None and
                total_revenue != st.session_state.ticket_revenue + st.session_state.other_revenue):
            _pres.append("총수입")
        if (st.session_state.get("_baseline_total_budget") is not None and
                total_budget != st.session_state.budget_exhibition + st.session_state.budget_supplementary):
            _pres.append("총예산")
        if _pres:
            nc, _ = st.columns([3, 7])
            with nc:
                st.caption(f"{' · '.join(_pres)}: 저장된 값 유지 중 — 입장·기타 수입 또는 "
                           f"전시·부대 예산을 입력하면 합산값으로 자동 갱신됩니다.")

        # 업로드된 예산 미리보기 (있을 때만)
        if st.session_state.get("budget_summary") and any(
                x.get("category") for x in st.session_state.budget_summary):
            with st.expander("업로드된 예산 집행 내역", expanded=False):
                summary_df = pd.DataFrame(st.session_state.budget_summary)
                summary_df = summary_df[summary_df["category"].astype(bool)]
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

        if st.session_state.get("budget_details") and any(
                x.get("subcategory") or x.get("detail") for x in st.session_state.budget_details):
            with st.expander("업로드된 예산 세부 내역", expanded=False):
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
            comma_int_input("총 관객수", "total_visitors")
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
        # 라벨 길이에 맞춘 너비 — 예술인패스·디스커버서울패스 라벨이 한 줄에
        # 들어가도록 해당 칸을 넓힘. 우측 spacer로 좌측 클러스터 유지.
        cols = st.columns([1, 1, 1.1, 1.5, 2.2, 1.3, 1.2, 1.3, 4], gap="small")
        with cols[0]:
            comma_int_input("일반", "visitor_general")
        with cols[1]:
            comma_int_input("학생", "visitor_student")
        with cols[2]:
            comma_int_input("초대권", "visitor_invitation")
        with cols[3]:
            comma_int_input("예술인패스", "visitor_artpass")
        with cols[4]:
            comma_int_input("디스커버서울패스", "visitor_discover")
        with cols[5]:
            comma_int_input("기타 할인", "visitor_discount")
        with cols[6]:
            comma_int_input("단체 관객", "visitor_group")
        with cols[7]:
            comma_int_input("오프닝 참석", "opening_attendance")

        ticket_sum = (st.session_state.visitor_general + st.session_state.visitor_student +
                      st.session_state.visitor_invitation + st.session_state.visitor_artpass +
                      st.session_state.visitor_discover + st.session_state.visitor_discount)
        if ticket_sum > 0 and st.session_state.total_visitors > 0:
            if ticket_sum != st.session_state.total_visitors:
                st.warning(f"입장권별 합계({ticket_sum:,}명)와 총 관객수({st.session_state.total_visitors:,}명)가 다릅니다.")
            else:
                st.success(f"입장권별 합계 일치: {ticket_sum:,}명")

        # 주차별 관객 — 11주차, 1줄 배치 (좌측 클러스터 + gap small)
        st.markdown("**주차별 관객 수**")
        week_cols = st.columns([1] * 11 + [6], gap="small")
        weekly = st.session_state.get("weekly_visitors", {}) or {}
        # 로드 동기화: weekly_visitors 딕셔너리가 외부에서 바뀌면(레코드 로드 등)
        # 개별 weekly_i 데이터 키를 다시 시드. (내 재구성으로 인한 무한 reseed는
        # 아래에서 _weekly_sig를 재구성값으로 맞춰 방지)
        sig = tuple(sorted((k, int(v or 0)) for k, v in weekly.items()))
        if st.session_state.get("_weekly_sig") != sig:
            for i in range(11):
                st.session_state[f"weekly_{i}"] = int(weekly.get(f"{i+1}주", 0) or 0)
                st.session_state.pop(f"_disp_weekly_{i}", None)
            st.session_state["_weekly_sig"] = sig
        new_weekly = {}
        for i in range(11):
            with week_cols[i]:
                v = comma_int_input(f"{i+1}주", f"weekly_{i}")
                if v > 0:
                    new_weekly[f"{i+1}주"] = v
        st.session_state.weekly_visitors = new_weekly
        st.session_state["_weekly_sig"] = tuple(
            sorted((k, int(v or 0)) for k, v in new_weekly.items()))

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
                "전시실 추가", "마지막 제거",
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

        media_sum = (st.session_state.artwork_painting + st.session_state.artwork_sculpture +
                     st.session_state.artwork_photo + st.session_state.artwork_installation +
                     st.session_state.artwork_media + st.session_state.artwork_other)
        # 합계 보존(왕복 무결성): 매체 구성이 로드값 그대로면 저장된 총작품수 유지,
        # 사용자가 매체를 바꾸면 매체 합으로 재계산.
        artwork_total = _derived_total("artwork_total")

        # 신작 수 (구작 = 총 - 신작 자동) — 신작/구작 도넛용
        nc1, nc2, _ = st.columns([1, 1, 8], gap="small")
        with nc1:
            st.number_input("신작 수", min_value=0, max_value=artwork_total or None,
                            key="artwork_new", format="%d",
                            help="새로 제작·커미션된 작품 수. 구작은 총 작품 수에서 자동 차감.")
        st.session_state.artwork_old = max(0, artwork_total - st.session_state.get("artwork_new", 0))

        if artwork_total > 0:
            mc, _ = st.columns([1, 9])
            with mc:
                st.metric("총 작품 수", f"{artwork_total}점")

        # 저장된 총합이 매체 합과 다르면(로드된 레코드) 보존 사실을 알리고
        # 매체 합으로 맞출 수 있는 버튼 제공.
        if st.session_state.get("_baseline_artwork_total") is not None and media_sum != artwork_total:
            rc, _ = st.columns([3, 7])
            with rc:
                st.caption(f"저장된 총합 {artwork_total}점 유지 중 "
                           f"(매체 구성 합 {media_sum}점)")
                if st.button("매체 구성 합으로 재계산", key="artwork_resync",
                             use_container_width=True):
                    st.session_state.pop("_baseline_artwork_total", None)
                    st.rerun()

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
            "프로그램 추가", "마지막 제거",
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
            comma_int_input("총 참여", "program_participants")
        with cols[3]:
            st.number_input("도슨트 정기", min_value=0, key="docent_regular", format="%d")
        with cols[4]:
            st.number_input("도슨트 특별", min_value=0, key="docent_special", format="%d")
        # docent_total — 구성요소 합(왕복 무결성: 미변경 시 저장값 보존)
        _derived_total("docent_total")

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
            "인쇄물 추가", "마지막 제거",
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
            comma_int_input("웹 초청장 발송", "web_invitation_count")
        with cols[2]:
            st.number_input("뉴스레터 오픈율 (%)", min_value=0.0, max_value=100.0,
                            step=0.1, key="newsletter_open_rate", format="%.1f")

        cols = st.columns([1.2, 1.2, 1.2, 6.4], gap="small")
        with cols[0]:
            st.number_input("SNS 게시", min_value=0, key="sns_posts", format="%d")
        with cols[1]:
            comma_int_input("SNS 피드백", "sns_feedback")
        with cols[2]:
            comma_int_input("멤버십 회원수", "membership_count")

        st.markdown("**SNS 상세 통계**")
        st.caption("인스타그램 기준 정량 지표.")
        cols = st.columns([1, 1, 1, 1, 6], gap="small")
        with cols[0]:
            comma_int_input("팔로워", "sns_followers")
        with cols[1]:
            comma_int_input("팔로워 증가", "sns_followers_gained", help="전시 기간 중 순증가")
        with cols[2]:
            comma_int_input("평균 피드백", "sns_avg_likes")
        with cols[3]:
            comma_int_input("최대 피드백", "sns_best_likes")
        bc, _ = st.columns([4, 6])
        with bc:
            st.text_input("최대 피드백 게시물 내용", key="sns_best_post",
                          placeholder="예: 한강주조 겨울 에디션 게시물")

        _section_divider()

        # ════════════════════════════════════════
        # 12. 언론보도 리스트 — 일간지/월간지 + 온라인 각 50%
        # ════════════════════════════════════════
        subsection("", "언론보도 리스트")
        _has_press_data = any(p.get("outlet") for p in st.session_state.press_print) or \
                          any(p.get("outlet") for p in st.session_state.press_online)
        if _has_press_data:
            st.info("엑셀로 업로드한 언론보도 데이터가 있습니다. 아래에서 수정·추가 가능합니다.")
        else:
            st.caption("상단의 '가져오기'로 일괄 입력도 가능합니다.")

        # 보도 건수 자동 동기화 제안
        print_count = len([p for p in st.session_state.press_print if p.get("outlet")])
        online_count = len([p for p in st.session_state.press_online if p.get("outlet")])
        list_total = print_count + online_count
        if list_total > 0 and st.session_state.press_count == 0:
            sc, _ = st.columns([3, 7])
            with sc:
                if st.button(f"보도 건수를 {list_total}건으로 자동 입력",
                             key="sync_press", use_container_width=True):
                    st.session_state.press_count = list_total
                    st.rerun()

        col_print, col_online = st.columns(2, gap="large")

        with col_print:
            st.markdown("**일간지 및 월간지**")
            for i, item in enumerate(st.session_state.press_print):
                # 일자 칸 넓혀 날짜+달력 아이콘 겹침 방지
                cols = st.columns([1.4, 1.8, 3.3, 1.8])
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
                "일간지 추가", "마지막 제거",
                "add_pp", "rm_pp",
                "press_print", {"outlet": "", "date": None, "title": "", "note": ""},
                page_full=False,
            )

        with col_online:
            st.markdown("**온라인 매체**")
            for i, item in enumerate(st.session_state.press_online):
                # 일자 칸 넓혀 날짜+달력 아이콘 겹침 방지
                cols = st.columns([1.4, 1.8, 2.8, 3])
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
                "온라인 추가", "마지막 제거",
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
                _rev_opts = ["긍정", "부정", "기타"]
                _rev_cur = review.get("category", "긍정")
                # 구 데이터의 '건의'는 '기타'로 매핑
                if _rev_cur == "건의":
                    _rev_cur = "기타"
                st.session_state.visitor_reviews[i]["category"] = st.selectbox(
                    "분류", _rev_opts, key=f"rev_cat_{i}",
                    index=_rev_opts.index(_rev_cur) if _rev_cur in _rev_opts else 0)
            with cols[1]:
                st.session_state.visitor_reviews[i]["content"] = st.text_input(
                    "내용", value=review.get("content", ""), key=f"rev_content_{i}")
            with cols[2]:
                st.session_state.visitor_reviews[i]["source"] = st.text_input(
                    "출처", value=review.get("source", ""), key=f"rev_source_{i}")

        _add_remove_buttons(
            "후기 추가", "마지막 제거",
            "add_rev", "rm_rev",
            "visitor_reviews", {"category": "긍정", "content": "", "source": ""},
        )

        # 마지막 섹션 하단 여백 — 다른 섹션의 _section_divider 간격과 동일하게
        st.markdown('<div style="margin-top: 18px;"></div>', unsafe_allow_html=True)
