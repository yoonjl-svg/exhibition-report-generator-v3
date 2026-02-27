"""
v3 보고서 생성기
- 분석 인사이트가 각 섹션에 인라인 배치
- 매체별 작품 구성 포함
- 평가 초안 자동 반영
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
import tempfile

from styles import (
    setup_document, set_run_font, add_paragraph, add_horizontal_rule,
    add_section_title, add_subsection_title, add_sub2_title,
    add_detail_title, add_bullet_main, add_bullet_sub, add_arrow_note,
    create_table, create_table_left_aligned,
    add_image, add_images_auto, add_images_2col,
    add_page_break, add_page_numbers_right,
    Colors, Fonts, CIRCLED_NUMBERS, ImageSize,
)
from chart_generator import (
    create_visitor_pie_chart,
    create_budget_comparison_chart,
    create_visitor_type_chart,
)


class ExhibitionReportGenerator:

    def __init__(self, data):
        self.data = data
        self.doc = Document()
        self.temp_files = []

    def generate(self, output_path):
        setup_document(self.doc)
        add_page_numbers_right(self.doc)

        self._create_toc_page()
        add_page_break(self.doc)

        self._section_1_overview()
        self._section_2_theme()
        add_page_break(self.doc)

        self._section_3_composition()
        add_page_break(self.doc)

        self._section_4_results()

        if self._has_promotion_data():
            add_page_break(self.doc)
            self._section_5_promotion()

        add_page_break(self.doc)
        self._section_6_evaluation()

        add_paragraph(self.doc, "")
        add_paragraph(self.doc, "끝.", size=Fonts.BODY, bold=False,
                      alignment=WD_ALIGN_PARAGRAPH.LEFT,
                      space_before=Pt(12), space_after=Pt(0), line_spacing=1.15)

        self.doc.save(output_path)
        self._cleanup()
        return output_path

    def _cleanup(self):
        for f in self.temp_files:
            try: os.remove(f)
            except OSError: pass

    # ─── 인라인 분석 삽입 헬퍼 ───

    def _insert_section_insights(self, section_key):
        """해당 섹션에 배치된 인사이트를 화살표 노트로 삽입"""
        insights = self.data.get("section_insights", {}).get(section_key, [])
        if not insights:
            return

        add_paragraph(self.doc, "", space_before=Pt(4))

        # 카테고리별 그룹핑
        grouped = {}
        for ins in insights:
            label = ins.get("category_label", ins.get("category", "분석"))
            grouped.setdefault(label, []).append(ins)

        for label, items in grouped.items():
            add_bullet_main(self.doc, None, f"[데이터 분석] {label}", bold_value=True)
            for item in items:
                add_arrow_note(self.doc, item["text"])

    # ─── 목차 ───

    def _create_toc_page(self):
        title = self.data.get("exhibition_title", "전시 제목")
        add_paragraph(self.doc, f"전시보고서 - 《{title}》",
                      size=Fonts.TOC_TITLE, bold=True,
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      space_before=Pt(12), space_after=Pt(4))
        add_horizontal_rule(self.doc)

        toc_items = [
            "I. 전시 개요",
            "II. 전시 주제와 내용",
            "III. 전시 구성",
            "IV. 전시 결과",
            "V. 홍보 방식 및 언론 보도",
            "VI. 평가 및 개선 방안",
        ]
        for item in toc_items:
            add_paragraph(self.doc, item, size=Fonts.TOC_ITEM, bold=True,
                          space_before=Pt(3), space_after=Pt(3), line_spacing=1.15)
            add_horizontal_rule(self.doc)

        poster = self.data.get("poster_image")
        if poster and os.path.exists(poster):
            add_paragraph(self.doc, "", space_before=Pt(10))
            add_image(self.doc, poster, width=ImageSize.POSTER_WIDTH)

    # ─── I. 전시 개요 ───

    def _section_1_overview(self):
        add_section_title(self.doc, "I", "전시 개요")
        ov = self.data.get("overview", {})

        fields = [
            ("title", "전시 제목", lambda v: f"《{v}》"),
            ("period", "전시 기간", None),
            ("exhibition_days", "전시 일수", None),
            ("artists", "참여 작가", lambda v: ", ".join(v) if isinstance(v, list) else v),
            ("chief_curator", "책임기획", None),
            ("curators", "기획", None),
            ("coordinators", "진행", None),
            ("curatorial_team", "학예팀", None),
            ("pr", "홍보", None),
            ("sponsors", "후원", None),
        ]
        for key, label, fmt in fields:
            val = ov.get(key)
            if val:
                display = fmt(val) if fmt else val
                add_bullet_main(self.doc, label, display)

        # 예산 (굵은 + 밑줄)
        if ov.get("total_budget"):
            add_bullet_main(self.doc, "총 사용 예산", ov["total_budget"],
                            bold_value=True, underline_value=True)
            for item in ov.get("budget_breakdown", []):
                add_bullet_sub(self.doc, item)

        if ov.get("total_revenue"):
            add_bullet_main(self.doc, "총수입", ov["total_revenue"])
        if ov.get("programs"):
            add_bullet_main(self.doc, "프로그램", ov["programs"])
        if ov.get("staff_count"):
            add_bullet_main(self.doc, "운영 인력", ov["staff_count"])
        if ov.get("visitors"):
            add_bullet_main(self.doc, "관객 수", ov["visitors"],
                            bold_value=True, underline_value=True)

        # 출품 작품 (v3 신규)
        artworks = self.data.get("artworks", {})
        if artworks.get("total"):
            media_parts = []
            for key, label in [("painting", "회화"), ("sculpture", "조각"), ("photo", "사진"),
                                ("installation", "설치"), ("media", "미디어"), ("other", "기타")]:
                v = artworks.get(key, 0)
                if v: media_parts.append(f"{label} {v}점")
            overview_text = f"{artworks['total']}점"
            if media_parts:
                overview_text += f" ({', '.join(media_parts)})"
            add_bullet_main(self.doc, "출품 작품", overview_text)

        add_paragraph(self.doc, "")

    # ─── II. 전시 주제와 내용 ───

    def _section_2_theme(self):
        add_section_title(self.doc, "II", "전시 주제와 내용")
        theme = self.data.get("theme_text", "")
        if theme:
            for p_text in theme.split("\n\n"):
                p_text = p_text.strip()
                if p_text:
                    add_paragraph(self.doc, p_text, size=Fonts.BODY,
                                  space_after=Pt(6), line_spacing=1.5,
                                  first_line_indent=Cm(0.5))

    # ─── III. 전시 구성 ───

    def _section_3_composition(self):
        add_section_title(self.doc, "III", "전시 구성")

        self._sub_rooms()
        self._sub_programs()
        self._sub_staff()
        self._sub_materials()

        # v3: 인라인 분석 (프로그램, 작품, 인력)
        self._insert_section_insights("composition")

    def _sub_rooms(self):
        add_subsection_title(self.doc, "1", "전시")
        rooms = self.data.get("rooms", [])
        for i, room in enumerate(rooms):
            add_sub2_title(self.doc, i + 1, room.get("name", f"{i+1}전시실"))
            artists = room.get("artists", "")
            if artists:
                if isinstance(artists, list): artists = ", ".join(artists)
                add_detail_title(self.doc, CIRCLED_NUMBERS[0], "참여 작가")
                add_paragraph(self.doc, artists, size=Fonts.BODY, left_indent=Cm(0.8))
            fp = room.get("floor_plan")
            if fp and os.path.exists(fp):
                add_detail_title(self.doc, CIRCLED_NUMBERS[1], "도면")
                add_image(self.doc, fp)
            photos = room.get("photos", [])
            valid = [p for p in photos if os.path.exists(p)]
            if valid:
                idx = 2 if (fp and os.path.exists(fp)) else 1
                add_detail_title(self.doc, CIRCLED_NUMBERS[idx], "전경 사진")
                add_images_auto(self.doc, valid)

    def _sub_programs(self):
        programs = self.data.get("related_programs", [])
        total_count = len(programs)
        total_part = sum(int(str(p.get("participants", "0")).replace(",", "").replace("명", ""))
                         for p in programs if p.get("participants"))

        suffix = ""
        if total_count > 0:
            suffix = f" - 총 {total_count}개 프로그램 진행"
            if total_part > 0:
                suffix += f", {total_part:,}명 참여"

        add_subsection_title(self.doc, "2", "전시 연계 프로그램", suffix=suffix)

        if programs:
            headers = ["구분", "제목", "일자", "참여 인원", "비고"]
            table_data = [[p.get("category", ""), p.get("title", ""), p.get("date", ""),
                           p.get("participants", ""), p.get("note", "")] for p in programs]
            create_table(self.doc, len(table_data), 5, data=table_data, headers=headers,
                         col_widths=[Cm(2), Cm(5.5), Cm(2.5), Cm(1.5), Cm(4)])

    def _sub_staff(self):
        add_subsection_title(self.doc, "3", "전시 운영 인력")
        staff = self.data.get("staff", {})
        if staff.get("main_staff"):
            add_sub2_title(self.doc, "1", "스태프")
            info = staff["main_staff"]
            if isinstance(info, dict):
                if info.get("count"):
                    add_detail_title(self.doc, CIRCLED_NUMBERS[0], "인원")
                    add_paragraph(self.doc, info["count"], left_indent=Cm(0.8))
                if info.get("role"):
                    add_detail_title(self.doc, CIRCLED_NUMBERS[1], "역할 및 활동 내용")
                    add_paragraph(self.doc, info["role"], left_indent=Cm(0.8))

    def _sub_materials(self):
        add_subsection_title(self.doc, "4", "인쇄물 및 굿즈")
        materials = self.data.get("printed_materials", [])
        if materials:
            headers = ["종류", "제작 수량", "비고"]
            table_data = [[m.get("type", ""), m.get("quantity", ""), m.get("note", "")] for m in materials]
            create_table(self.doc, len(table_data), 3, data=table_data, headers=headers,
                         col_widths=[Cm(5.5), Cm(3), Cm(6.5)])

    # ─── IV. 전시 결과 ───

    def _section_4_results(self):
        add_section_title(self.doc, "IV", "전시 결과")
        self._sub_budget()
        self._sub_revenue()
        self._sub_visitor_composition()

        # v3: 인라인 분석 (예산, 관객)
        self._insert_section_insights("results")

    def _sub_budget(self):
        add_subsection_title(self.doc, "1", "예산 및 지출")
        budget = self.data.get("budget", {})
        if budget.get("total_spent"):
            add_bullet_main(self.doc, "지출 총액", budget["total_spent"],
                            bold_value=True, underline_value=True)
        for note in budget.get("breakdown_notes", []):
            add_bullet_sub(self.doc, note)

        summary = budget.get("summary", [])
        if summary:
            add_paragraph(self.doc, "", space_before=Pt(6))
            headers = ["사업", "계획 예산(원)", "집행 예산(원)", "계획 대비 집행"]
            table_data = [[s.get("category", ""), s.get("planned", ""),
                           s.get("actual", ""), s.get("note", "")] for s in summary]
            create_table(self.doc, len(table_data), 4, data=table_data, headers=headers,
                         col_widths=[Cm(2.5), Cm(4.5), Cm(4.5), Cm(4)])

        for note in budget.get("arrow_notes", []):
            add_arrow_note(self.doc, note)

    def _sub_revenue(self):
        add_subsection_title(self.doc, "2", "총 관객 수 및 수익 결산")
        rev = self.data.get("revenue", {})
        if rev.get("total_visitors"):
            add_sub2_title(self.doc, "1", f"총 관객 수 {rev['total_visitors']}")
            if rev.get("daily_average"):
                add_bullet_main(self.doc, "일평균 관객", rev["daily_average"])

        if rev.get("total_revenue"):
            add_sub2_title(self.doc, "2", f"총 수입 {rev['total_revenue']}")
            if rev.get("ticket_revenue"):
                add_bullet_main(self.doc, "입장 수입", rev["ticket_revenue"])

    def _sub_visitor_composition(self):
        add_subsection_title(self.doc, "3", "관객 구성")
        vc = self.data.get("visitor_composition", {})

        ticket_type = vc.get("ticket_type", {})
        if ticket_type:
            chart_path = create_visitor_pie_chart(ticket_type, title="입장권별 관객 구성")
            self.temp_files.append(chart_path)
            add_image(self.doc, chart_path, is_chart=True)

        for item in vc.get("ticket_analysis", []):
            if item.startswith("→"):
                add_arrow_note(self.doc, item[1:].strip())
            elif item.startswith("-"):
                add_bullet_sub(self.doc, item[1:].strip())
            else:
                add_bullet_main(self.doc, None, item, bold_value=True, underline_value=True)

    # ─── V. 홍보 ───

    def _has_promotion_data(self):
        promo = self.data.get("promotion", {})
        has_promo = any(promo.get(k, "") for k in ["advertising", "press_release", "web_invitation", "newsletter", "sns", "other"])
        press = self.data.get("press_coverage", {})
        has_press = bool(press.get("print_media")) or bool(press.get("online_media"))
        has_membership = bool(self.data.get("membership", ""))
        return has_promo or has_press or has_membership

    def _section_5_promotion(self):
        add_section_title(self.doc, "V", "홍보 방식 및 언론 보도")

        # 홍보 방식
        add_subsection_title(self.doc, "1", "홍보 방식")
        promo = self.data.get("promotion", {})
        num = 1
        for key, label in [("advertising", "광고"), ("press_release", "보도자료"),
                           ("web_invitation", "웹 초청장"), ("newsletter", "뉴스레터"),
                           ("sns", "SNS"), ("other", "그 외")]:
            content = promo.get(key, "")
            if content:
                add_sub2_title(self.doc, num, label)
                for line in content.split("\n"):
                    line = line.strip()
                    if line:
                        add_bullet_main(self.doc, None, line)
                num += 1

        # 언론보도
        add_subsection_title(self.doc, "2", "언론보도 리스트")
        press = self.data.get("press_coverage", {})
        if press.get("print_media"):
            add_sub2_title(self.doc, "1", "일간지 및 월간지")
            headers = ["매체명", "일자", "제목", "비고"]
            table_data = [[i.get("outlet", ""), i.get("date", ""), i.get("title", ""), i.get("note", "")]
                          for i in press["print_media"]]
            create_table(self.doc, len(table_data), 4, data=table_data, headers=headers,
                         col_widths=[Cm(1.3), Cm(1.3), Cm(9), Cm(4.4)])

        if press.get("online_media"):
            add_sub2_title(self.doc, "2", "온라인 매체")
            headers = ["매체명", "일자", "제목", "URL"]
            table_data = [[i.get("outlet", ""), i.get("date", ""), i.get("title", ""), i.get("url", "")]
                          for i in press["online_media"]]
            create_table(self.doc, len(table_data), 4, data=table_data, headers=headers,
                         col_widths=[Cm(1.5), Cm(1.5), Cm(7.5), Cm(5.5)])

        # 멤버십
        if self.data.get("membership"):
            add_subsection_title(self.doc, "3", "멤버십 커뮤니케이션")
            add_paragraph(self.doc, self.data["membership"], size=Fonts.BODY, line_spacing=1.4)

        # v3: 인라인 분석 (홍보)
        self._insert_section_insights("promotion")

    # ─── VI. 평가 ───

    def _section_6_evaluation(self):
        add_section_title(self.doc, "VI", "평가 및 개선 방안")

        # v3: 교차 분석 인사이트
        self._insert_section_insights("evaluation")

        # 유사 전시 비교표
        sim_headers = self.data.get("similar_comparison_headers")
        sim_data = self.data.get("similar_comparison_table")
        if sim_headers and sim_data:
            add_paragraph(self.doc, "", space_before=Pt(8))
            add_bullet_main(self.doc, None, "유사 전시 비교", bold_value=True)
            add_paragraph(self.doc, "", space_before=Pt(2))
            num_rows = len(sim_data)
            num_cols = len(sim_headers)
            total_w = 15
            first_w = 4.5
            other_w = (total_w - first_w) / max(num_cols - 1, 1)
            col_widths = [Cm(first_w)] + [Cm(other_w)] * (num_cols - 1)
            create_table_left_aligned(self.doc, num_rows, num_cols, data=sim_data,
                                      headers=sim_headers, col_widths=col_widths, first_col_bold=True)

        # 평가
        eval_num = "1"
        add_subsection_title(self.doc, eval_num, "평가")

        evaluation = self.data.get("evaluation", {})
        reviews = self.data.get("visitor_reviews", [])
        positive_reviews = [r for r in reviews if r.get("category", "").strip() in ("긍정", "긍정적")]
        negative_reviews = [r for r in reviews if r.get("category", "").strip() in ("부정", "부정적", "건의", "불만")]

        sub_num = 1

        positive = evaluation.get("positive", [])
        if positive or positive_reviews:
            add_sub2_title(self.doc, sub_num, "긍정 평가")
            for item in positive:
                add_bullet_main(self.doc, None, item)
            if positive_reviews:
                add_paragraph(self.doc, "", space_before=Pt(4))
                headers = ["분류", "상세 내용(인용)", "출처"]
                table_data = [[r.get("category", "긍정"), r.get("content", ""), r.get("source", "")]
                              for r in positive_reviews]
                create_table(self.doc, len(table_data), 3, data=table_data, headers=headers,
                             col_widths=[Cm(1.25), Cm(11.75), Cm(2)])
            sub_num += 1

        negative = evaluation.get("negative", [])
        if negative or negative_reviews:
            add_sub2_title(self.doc, sub_num, "부정 평가")
            for item in negative:
                add_bullet_main(self.doc, None, item)
            if negative_reviews:
                add_paragraph(self.doc, "", space_before=Pt(4))
                headers = ["분류", "상세 내용(인용)", "출처"]
                table_data = [[r.get("category", "부정"), r.get("content", ""), r.get("source", "")]
                              for r in negative_reviews]
                create_table(self.doc, len(table_data), 3, data=table_data, headers=headers,
                             col_widths=[Cm(1.25), Cm(11.75), Cm(2)])
            sub_num += 1

        improvements = evaluation.get("improvements", [])
        if improvements:
            add_sub2_title(self.doc, sub_num, "개선 방안")
            for item in improvements:
                add_bullet_main(self.doc, None, item)


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────

def generate_report(data, output_path):
    generator = ExhibitionReportGenerator(data)
    return generator.generate(output_path)
