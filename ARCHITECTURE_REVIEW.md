# 일민미술관 전시 워크스페이스 — 코드베이스 검수 문서

> **목적**: 외부 검수(GPT 등)가 구조·코드뿐 아니라 **설계 철학과 지향점**까지
> 이해하고 보완점을 제안할 수 있도록 작성한 자기완결 문서.
> **기준 버전**: v5.3.68
> **코드 저장소**: `yoonjl-svg/exhibition-report-generator-v3`
> **데이터 저장소**: `yoonjl-svg/exhibition-report-generator-v5` (비공개, 전시 JSON 18건)

---

## 0. 한 문단 요약

일민미술관의 전시 데이터를 **누적 관리**하고(워크스페이스), 한 전시의 정량·정성
데이터를 입력하면 **과거 18개 전시와 자동 비교 분석**해 인사이트를 만들고, 이를
**중립적 신문 기사체의 Word 보고서**로 출력하는 Streamlit 웹앱이다. 보고서는 생성
전 **HTML 웹 미리보기**(Word와 동일 내용)로 검토·편집할 수 있고, 선택적으로
**Claude(LLM)**가 분석 문단을 산문으로 재작성한다.

---

## 1. 설계 철학과 지향점 (가장 중요)

이 프로젝트의 모든 의사결정은 아래 원칙에서 파생된다. 검수자는 코드가 이 철학을
지키는지를 우선 봐 주길 바란다.

### 1.1 미술관의 보고서 = 중립적 문서, 대시보드가 아님
- 미술관은 영리 기업처럼 프로젝트의 "성패"를 단정하지 않는다. 디렉터는 보고서를
  **드라마틱한 요약이 아니라 신문 기사처럼 사실의 중립적 나열**로 받아들인다.
- 따라서 평가 어휘("성공적", "기대 미달")를 회피하고, 헤지 표현("~로 확인됨",
  "~으로 판단됨")과 사실·수치 중심 서술을 쓴다.
- 문체: 공문서체 **"~임 / ~하였음"** (구어체 "~니다", 논문체 "~이다" 금지).
- 비교는 "우열"이 아니라 "**역대 속 위치**"로 제시한다(예: 기준=100 대비 위치).

### 1.2 입력 최소화 · 분석 자동화 · 분석의 인라인 배치
- 숫자를 입력하면 과거 전시 비교가 자동 도출된다.
- 분석은 별도 장에 몰지 않고 **보고서 각 장(章)에 인라인**으로 녹인다.
- 평가 초안(긍정/부정/개선)도 데이터 패턴에서 자동 도출하고 큐레이터는 수정만.

### 1.3 UI: 절제·집중·일관 (CLAUDE.md에 명문화)
1. **가로 폭 상한** — 콘텐츠는 무한정 늘어나지 않는다. 읽기·편집 콘텐츠는 페이지의
   ~55–65%, 숫자·짧은 입력은 좁은 컬럼+spacer. "풀폭이 자연스러운가?"가 아니라
   "이 콘텐츠에 필요한 최소 너비는?"을 먼저 묻는다.
2. **이모지 금지** — 버튼·헤더·라벨·탭·메시지에 장식용 이모지를 쓰지 않는다.
   (예외: 워크스페이스 카드 하단 지표의 👥📊💰는 사용자 명시 요청, favicon 🎨)
3. **중복 정보 제거** — 탭명·섹션 헤더가 이미 전달하는 정보를 반복하지 않는다.

### 1.4 차트: 양이 아니라 가독성
- "이 데이터를 가장 빠르게 읽히게 하는 단 하나의 형식은?"을 매번 묻는다.
- 같은 비교를 막대·점·산점도로 반복하지 않는다(노이즈).
- 흐름=선, 구성=도넛, 비교=롤리팝/추세선. **목적별 다양성은 확보하되 수는 절제.**
- 차트를 넣기 전 "이게 빠지면 독자가 무엇을 못 읽나?"가 약하면 넣지 않는다.
- **차트는 연달아 두지 않는다**: 차트 → 그 차트에 대한 서술 → 다음 차트.

### 1.5 차트의 두 범주 (분석 자산 활용)
- **자기완결형**: 그 전시의 숫자만으로 특성이 읽히는 차트(예: 출품 매체 구성 도넛,
  신작/구작 도넛). 비교 불필요.
- **비교형**: 다른 전시와 견줘야 의미가 분명해지는 차트(예: 주차별 관객 추이, 핵심
  지표). 반드시 **비교 기준**을 함께 제시한다.
- **비교 기준 규칙**: ① `같은 유형 평균` ② `같은 유형 마지막(직전) 전시`. 둘 다
  가능한 곳은 둘 다, 어려운 곳은 평균만. 라벨은 "같은 유형"이 아니라 **정확한 유형명
  ("기존 기획전" 등)과 실제 직전 전시명**을 적시한다.

### 1.6 Word(정식 아카이브) ↔ HTML(보는 즐거움)의 통일
- 정식 산출물은 Word(.docx). HTML 웹 리포트는 화면용 미리보기.
- 단 둘은 **동일 내용·동일 차트 디자인**이어야 한다("Word로 생성될 내용을 미리본다"는
  목적). 같은 섹션(I~VI)·같은 차트(롤리팝·도넛·주차 SVG)·같은 텍스트·같은 표.

### 1.7 검증 문화
- 차트는 생성한 PNG/HTML을 **Claude Preview로 직접 눈으로 확인**한다.
- 보고서는 세션 상태를 모사해 **헤드리스로 .docx를 실제 생성**해 검증한다.
- 추측 대신 실제 DOM/출력을 확인하고 고친다.

---

## 2. 아키텍처 개관

```
┌───────────────────────────────────────────────────────────┐
│ Streamlit 앱 (app.py)                                       │
│  Workspace 모드(전시 목록) ◀──▶ Detail 모드(3탭)            │
│   tab_workspace            전시 데이터 / 분석 및 평가 / 보고서 생성 │
│        │                                │                   │
│        └──── kb_session (세션 ↔ KB 레코드) ────┘            │
│                     │                                       │
│              kb_store (local 파일 ↔ GitHub API, 자동 모드)   │
└─────────────────────┼───────────────────────────────────────┘
                      ▼
        v5 저장소: data/exhibitions/*.json (한 전시 = 한 JSON, 18건)

분석·보고서 파이프라인:
  utils.collect_analysis_data()         (세션 → 한국어 키 dict)
        │
        ▼
  analysis_engine.generate_all_insights()   (레퍼런스 비교 → 인사이트/평가초안/유사전시)
        │
        ├─▶ llm_writer.rewrite_insights()  (선택, Claude Opus 산문화 + 프롬프트 캐싱)
        │
        ├─▶ report_generator.generate_report()  → .docx  (matplotlib 차트 임베드)
        └─▶ html_report.build_report_html()     → HTML 미리보기(새 창, CSS/SVG)
```

### 이중 저장소 / KB 이중 모드
- 코드(v3)와 데이터(v5)를 분리 → 데이터 변경이 코드 배포와 무관.
- `kb_store.get_mode()`: `KB_GITHUB_PAT` 있으면 **github**(배포), 없으면 **local**(개발).
- 설정 키: `KB_MODE`, `KB_LOCAL_PATH`, `KB_GITHUB_REPO`, `KB_GITHUB_PAT`,
  `KB_GITHUB_BRANCH`. 경로 `data/exhibitions/`. 메모리 캐시 TTL 30초.
- GitHub 오류는 `_gh_check()`가 401(토큰 만료)/403/404로 구분해 안내.

---

## 3. 화면 구조

### Workspace 모드 (`tabs/tab_workspace.py`)
- 미술관 전체 KPI metric strip(누적/분석대상/평균 관객·일평균·예산·수입).
- 액션 바: 새 전시 데이터 생성 / 가져오기(모달) / 새로고침.
- 가져오기 모달(`@st.dialog`): Excel 6시트 템플릿 + JSON. 신규 전시 생성.
- 전시 카드: 연도별 그룹(최신 상단), 1줄 4개. 카드 하단 지표는 이모지 1줄(예외),
  우측에 컴팩트 "편집" 버튼.
- 하단 expander: "누적 흐름 & 다중 전시 비교"(`tab_trend.py`, Altair).

### Detail 모드 (3탭)
1. **전시 데이터** (`tabs/tab_input.py`) — 서술+정량 통합 단일 입력 탭.
   상단에 "가져오기" 모달(워크스페이스와 동일 규격, 현재 전시에 덮어쓰기).
2. **분석 및 평가** (`tabs/tab_analysis.py`) — 인사이트 카드(근거 expander) +
   유사 전시 시간순 추세선 + 비교표.
3. **보고서 생성** (`tabs/tab_generate.py`) — 완성도 체크 → 구조 미리보기 →
   AI 글쓰기 설정 → 생성 → **웹 미리보기(새 창)** + 분석 문단 편집 + Word 다운로드.

> 레거시(미렌더, 롤백 안전망): `tabs/tab_base.py`, `tabs/tab_data.py`.

---

## 4. 파일별 책임

| 파일 | 역할 |
|------|------|
| `app.py` | 진입점·전역 CSS(테마/입력창/탭/사이드바)·`init_session()`·레퍼런스 로드 캐시·라우팅 |
| `tabs/tab_input.py` | 전시 데이터 통합 입력(섹션별) + 가져오기 모달 |
| `tabs/tab_analysis.py` | 인사이트 카드·근거·유사 전시 시간순 추세선·비교표 |
| `tabs/tab_generate.py` | 완성도·미리보기·LLM·웹 미리보기(새 창)·Word·데이터 수집 |
| `tabs/tab_workspace.py` | 전시 목록·KPI·카드 그리드·가져오기 모달 |
| `tabs/tab_trend.py` | 누적 흐름(시계열)·다중 전시 비교(정규화 막대), Altair |
| `analysis_engine.py` | 인사이트·평가초안·유사전시·종합표 생성 |
| `reference_data.py` | 레퍼런스 통계(평균/순위/백분위)·파생지표·유사도·유형필터·KB→DF |
| `report_generator.py` | python-docx Word 보고서(I~VI) |
| `html_report.py` | **HTML 웹 리포트(Word 미러링, CSS/SVG)** |
| `llm_writer.py` | Claude API 산문 재작성·프롬프트 캐싱·비용 추정 |
| `chart_generator.py` | matplotlib 차트(미술관 톤 팔레트+공통 스타일) |
| `styles.py` | Word 스타일 시스템(글꼴/여백/제목 체계/이미지 배치) |
| `kb_store.py` / `kb_session.py` / `schema.py` | KB 저장소·세션 브리지·레코드 스키마 |
| `excel_template.py` | 6시트 Excel 템플릿 생성·파싱 |
| `ui_helpers.py` | eyebrow/chip/subsection/metric 등 공통 UI |
| `utils.py` | `collect_analysis_data()`·`add_item`/`remove_item`·포맷 헬퍼 |
| `sample_data.py` | 테스트용 (가)하이퍼 옐로우 — 모든 입력 필드 완비(배포 시 제거) |

---

## 5. 데이터 스키마 (`schema.py`)

`SCHEMA_VERSION = "1.0.0"`. 한 전시 = 한 JSON 파일.

```jsonc
{
  "id": "2025-하이퍼-옐로우",   // {연도}-{슬러그}
  "status": "draft",            // draft|in_progress|completed|archived
  "type": 1,                    // 0=분석제외, 1=정기기획전, 2=특별전, 3=기타
  "source": "form",             // migration|form|excel|duplicate
  "created_at": "...", "modified_at": "...", "finalized_at": null,
  "data": { /* 평면 dict: 모든 입력 */ },
  "analysis_cache": null
}
```
- 유형: 0 분석제외 / 1 정기기획전 / 2 특별전 / 3 기타. 비교 시 **동일 유형 우선**,
  같은 유형 3건 미만이면 전체(0 제외) 폴백. 통계 기준 **평균(mean)**.
- `data` 주요 키(발췌): 서술(title/period/artists/curators…/theme_text/rooms[]/
  related_programs[]/printed_materials[]/promo_*/press_print[]/press_online[]/
  visitor_reviews[]), 예산(budget_exhibition/supplementary/planned, ticket/other_revenue,
  total_*), 관객(total_visitors, visitor_general/student/invitation/artpass/discover/
  discount/group, opening_attendance, weekly_visitors{}), 작품(artwork_painting…other,
  **artwork_new/old**, artwork_total), 프로그램·인력·홍보(SNS 상세 포함).

---

## 6. 입력 탭 (`tab_input.py`) 섹션 순서

1. **전시 기본** — 4단(기본정보 / 기획진 / 디자인 / 인력[유급·봉사자]) + 운영·예산
   (예산 1행 5열). 참여 작가는 textarea.
2. **관객** — 총관객+일평균(자동) / 입장권별 8칸 1줄 / 주차별 11주 1줄.
3. **전시 주제와 내용**(서문) + **전시실 구성**(2×2, 도면·전경 가로) [2단].
4. **출품 작품**(매체 6칸 + **신작 수**; 구작 자동).
5. **전시 연계 프로그램**(행 + 요약 수치).
6. **인쇄물 및 굿즈** / **홍보 방식** (각 단독 섹션).
7. **홍보 지표** + SNS 상세.
8. **언론보도**(일간지/월간지 + 온라인 2단).
9. **관객 후기**(긍정/부정/**기타**).

- 합계(예산/수입/작품/인력/도슨트/구작)는 자동 계산.
- 입력창: BaseWeb 래퍼에만 테두리(이중 테두리 제거), text/number/date/select **높이
  38px 통일**, number 스테퍼(±) 제거. (DOM 실측으로 확정)

---

## 7. 분석 엔진 (`analysis_engine.py`)

- 진입: `generate_all_insights(current, ref_df, exhibition_type) -> AnalysisResult`
  `{insights[], eval_drafts[], similar_exhibitions[], similar_comparison_table}`.
- `Insight`: category/section/title/text/metric_name/current_value/reference_avg/
  percentile/rank/total_count/priority(1중요·2보통·3참고)/**unit/is_ratio**.
- 카테고리 분석: 관객·예산·프로그램·작품·홍보·인력·교차(예산vs관객/홍보vs관객/회수).
  section ∈ {results, composition, promotion, evaluation} → 보고서 배치.
- `_generate_eval_drafts`: diff>15% 긍정 / <-15% 부정 / <-20% 개선.
- `compute_summary_metrics`: 6개 핵심 지표의 현재값·기준평균·차이(롤리팝/표 원천).
- `SimilarExhibitionRow`에 **start(시작일)** 보유 → 시간순 정렬·추세선.
- 유형 라벨: `get_type_label` → "기존 기획전/특별전/전시", 폴백 "역대 전시".

---

## 8. 레퍼런스 통계 (`reference_data.py`)
- `load_reference(xlsx)`: Row2 컬럼명/Row3+ 데이터, "-"·빈칸 NaN.
- `compute_stats/percentile/rank`, `compute_derived_metrics`(관객당비용·수입예산비율·
  유료비율·프로그램참여율·보도건당관객), `get_similar_exhibitions`(가중 유사도
  예산35/기간25/관객25/작가15), `filter_by_type`, `kb_records_to_reference_df`.
- 앱은 **KB 우선 로드**, 실패 시 xlsx 폴백. KB df도 분석/차트에 필요한 한국어 컬럼
  (총 관객수·총 사용 예산·일평균 관객수·전시 기간_시작 등)을 생성.

---

## 9. Word 보고서 (`report_generator.py`)

`generate_report(data, path)` → `ExhibitionReportGenerator(data).generate()`.

### 구조 (장)
- **I. 전시 개요**
- **II. 전시 주제와 내용**
- **III. 전시 구성** — 전시실 / **출품 작품 구성(매체 도넛 + 신작·구작 도넛, 2-up)+서술**
  / 프로그램 / 인력 / 인쇄물 / (인라인 분석, 작품 카테고리는 도넛이 전담하여 제외)
- **IV. 전시 결과** — 예산 / 관객(**주차별 추이 선+비교 기준선** → 서술 → **입장권 도넛
  + 유료·무료 도넛 2-up** → 서술) / (인라인 분석)
- **V. 홍보 방식 및 언론 보도** — 방식 / 일간지·온라인 표 / 멤버십 / (인라인 분석)
- **VI. Executive Summary** — **기준 대비 핵심 지표(롤리팝)** → 종합 의견(LLM) →
  관객 반응 종합(LLM) → 데이터 도출 평가 항목

### 인사이트 주입 계약
- `insight_selections[f"ins_{section}_{i}"]`(bool), `insight_texts[key]`(편집 텍스트).
  분석 탭과 생성 탭이 공유하는 **고정 key 포맷**.
- `_insert_section_insights`: **llm_sections 우선**, 없으면 룰 기반 불릿.

---

## 10. HTML 웹 리포트 (`html_report.py`) — Word 미러링

- `build_report_html(data) -> str`: 임베드 CSS 포함 self-contained HTML.
- **Word의 I~VI를 같은 순서·같은 내용으로** 렌더(동일 차트 디자인):
  - 핵심 지표: **CSS 롤리팝**(기준=100 점선, 위 녹색/아래 테라코타).
  - 구성: **conic-gradient 도넛** 2-up(매체·신작/입장권·유료무료) + 하단 범례.
  - 주차별 추이: **인라인 SVG 라인**(영역+마커) + 비교 기준선.
  - 개요/주제/프로그램/인쇄물/홍보/언론/평가: 키-값·표·서술.
  - 분석 서술: Word와 동일 규칙(LLM 산문 우선, 없으면 룰 불릿).
- 표시: `tab_generate`에서 "웹 미리보기 열기(새 창)" 버튼 → `window.open` +
  `document.write`로 새 탭에 자체 페이지로 렌더(본문 길이 보존). 편집 내용 반영.

---

## 11. LLM 재작성 (`llm_writer.py`)
- `rewrite_insights() -> LLMWriterResult`. 모델 `MODEL = "claude-opus-4-7"`.
- 프롬프트 캐싱: SYSTEM_PROMPT + few-shot(ephemeral cache_control), 캐시 토큰 추적.
- 톤: 공문서체 "~임/~하였음", 신문 기사식 사실 중심, 평가어 금지, 헤지 표현,
  `[比 《전시명》(수치)]` 각주식 비교, 없는 수치 날조 금지.
- 5개 섹션 산문화(results→IV, composition→III, promotion→V, evaluation→VI 종합의견,
  audience_response→VI 관객 반응). 키 없으면 룰 기반 폴백.

---

## 12. 차트 모듈 (`chart_generator.py`) 현황
- 공통: 미술관 팔레트(녹색 #255c4a / 테라코타 #b4512a / 블루 #3f5e99), 공통 폰트·
  크기 헬퍼(`_fp`), 한국어 폰트 폴백 체인.
- **현재 보고서·분석에서 사용**:
  - `create_media_composition_chart`(도넛, 하단 범례; 매체/신작/입장권/유료무료 공용)
  - `create_weekly_visitors_chart`(영역+라인, `ref_lines` 비교 기준선)
  - `create_keymetrics_lollipop`(핵심 지표 롤리팝; Word VI)
  - `create_similar_trend_chart`(유사 전시 시간순 추세선; 분석 탭)
- **정의돼 있으나 현재 미사용(보존, 재도입 즉시 가능)**: `create_budget_structure_chart`,
  `create_efficiency_scatter_chart`, `create_trend_chart`, `create_comparison_bar`,
  `create_financial_panel`, `create_similar_bar_chart`, `create_visitor_pie_chart`.

---

## 13. 알려진 한계 / 검수 요청 포인트
1. **이미지 비영속**: 도면·전경 사진은 세션 종료 시 소실(KB JSON엔 텍스트·숫자만).
2. **주차별 레퍼런스 없음**: 18개 전시의 주차 데이터 미보유 → 주차 추이 비교는
   일평균×7 환산 기준선으로만(절대 주차 비교 불가).
3. **입장권 카테고리 불일치**: 현재 입력(일반/초대권/기타할인 등)과 레퍼런스(유료/무료·
   초대 등)가 1:1 아님 → 입장권은 자기완결 도넛, 비교는 유료비율 등 일부만.
4. **신작/구작**: 레퍼런스는 거의 비어 있음(1/17) → 신작 도넛은 본 전시 입력값만.
5. **유사 전시 추세선의 해석**: 유사도로 선정된 군이라 시간 연속 추세가 아님("비교군
   추이"로 캡션 명시). 라인 6개로 다소 밀집.
6. **HTML↔Word 완전 일치의 한계**: 같은 내용·디자인을 지향하나 렌더 엔진이 달라
   (CSS/SVG vs matplotlib) 픽셀 동일은 아님. 룸 사진 등 일부 요소는 웹에 미표시.
7. **평가 초안 다양성**: 규칙 기반이라 문장 다양성 제한(LLM 미사용 시).
8. **조사 처리**: "은/는", "이/가" 자동 처리가 일부 어색할 수 있음.
9. **GitHub PAT 만료**: fine-grained 토큰 만료 시 워크스페이스 401 → secrets 교체 필요.
10. **미사용 차트 함수 잔존**: chart_generator에 보존된 미사용 함수(정리 여부 판단 필요).
11. **단일 사용자 가정**: KB 캐시는 프로세스 메모리(30초). 동시 편집 충돌 가능.

---

## 14. 배포 / 실행
- Streamlit Cloud, Python 3.9+. `requirements.txt`(anthropic 포함), `packages.txt`
  (fonts-noto-cjk). secrets `KB_GITHUB_PAT`(Contents R/W, v5 레포) → github 모드.
- 테스트: 사이드바 "샘플 채우기"((가)하이퍼 옐로우, 전 필드 완비) → detail 진입.
- 검증 도구: Claude Preview(차트 PNG/HTML 시각 확인), 헤드리스 .docx 생성.

---

## 15. 버전 메모 (v5.3.x 주요 흐름)
- **v5.3.16–22**: section_header 제거, 입력 14px 통일, 입력 탭 레이아웃 재구성, 텍스트
  크기·너비 정밀화.
- **v5.3.23–25**: 4탭 → 3탭(전시 데이터 통합), 가져오기 일원화(모달).
- **v5.3.44**: GitHub 오류 메시지 명확화(401 등).
- **v5.3.45–47**: 분석 탭 '근거' 패턴(카드+evidence), 주목도 칩(중요/보통/참고).
- **v5.3.48–52**: 입력창 '쫀쫀한 그리드'(스테퍼 제거·높이 38px 통일, 이중 테두리 제거,
  DOM 실측 검증).
- **v5.3.55**: UI 원칙(가로폭/이모지/중복) 전 탭 일관 적용.
- **v5.3.59–62**: 차트 과잉 → 절제(가독성 원칙 명문화).
- **v5.3.63–64**: 차트 두 범주(자기완결/비교형), 차트↔서술 교차, 입장권 2도넛,
  정확한 유형명·직전 전시명.
- **v5.3.65–67**: HTML 웹 리포트 도입 → 새 창 버튼 → **Word와 전 섹션 통일**.
- **v5.3.68**: 유사 전시 비교 = 시간순 추세선 + 표 시간 정렬.
