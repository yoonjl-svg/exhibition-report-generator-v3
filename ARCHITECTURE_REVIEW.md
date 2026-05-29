# 일민미술관 전시 워크스페이스 — 코드베이스 구조 검수 문서

> **목적**: 이 문서는 외부 검수(GPT 등)를 위한 것입니다. 프로젝트의 전체 구조, 데이터
> 흐름, 각 모듈의 책임, 알려진 한계를 세부적으로 공유합니다.
> **작성 시점 기준 버전**: v5.3.54
> **저장소(코드)**: `yoonjl-svg/exhibition-report-generator-v3` (현재 레포)
> **저장소(데이터)**: `yoonjl-svg/exhibition-report-generator-v5` (비공개, 전시 JSON 18건)

---

## 1. 제품 개요

일민미술관의 **전시 보고서 자동 생성기**이자 **전시 데이터 누적 관리 워크스페이스**.
Streamlit 웹앱(단일 프로세스)으로 구현. 큐레이터가 한 전시의 정량·정성 데이터를
입력하면, 과거 18개 전시와 비교 분석한 인사이트가 자동 생성되고, 이를 Word 보고서로
출력한다. 분석 문장은 선택적으로 Claude(LLM)가 신문 기사체 산문으로 재작성한다.

### 핵심 철학
- **입력 최소화, 분석 자동화**: 숫자를 넣으면 비교 분석이 자동 도출.
- **분석이 보고서에 인라인으로 녹아든다**: 인사이트가 별도 섹션이 아니라 보고서 각 장(章)에 배치.
- **미술관 맥락**: 영리 기업이 아니므로 "성패 판정"이 아니라 **중립적 사실 나열**(신문
  기사체)을 지향. 평가 어휘("성공적", "기대 미달")를 회피하고 헤지 표현("~로 확인됨")을 사용.

---

## 2. 아키텍처 개관

```
┌─────────────────────────────────────────────────────────────┐
│  Streamlit 앱 (app.py)                                       │
│                                                              │
│  ┌──────────────┐         ┌──────────────────────────────┐  │
│  │ Workspace 모드│  ◀────▶ │ Detail 모드 (3탭)            │  │
│  │ (전시 목록)   │         │ 전시 데이터 / 분석 및 평가 /  │  │
│  │ tab_workspace │         │ 보고서 생성                   │  │
│  └──────┬───────┘         └──────────────┬───────────────┘  │
│         │                                │                   │
│         ▼                                ▼                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ kb_session  (session_state ↔ KB 레코드 브리지)       │    │
│  └───────────────────────┬────────────────────────────┘    │
│                          ▼                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │ kb_store  (local 파일 ↔ GitHub API, 자동 모드 전환)  │    │
│  └───────────────────────┬────────────────────────────┘    │
└──────────────────────────┼──────────────────────────────────┘
                           ▼
        ┌──────────────────────────────────────┐
        │ v5 저장소: data/exhibitions/*.json    │
        │ (한 전시 = 한 JSON 파일, 18건)         │
        └──────────────────────────────────────┘

분석/보고서 파이프라인:
  utils.collect_analysis_data()  ──▶ analysis_engine.generate_all_insights()
       (session→Korean dict)            (레퍼런스 비교 → 인사이트/평가초안)
                                              │
                                              ▼
              llm_writer.rewrite_insights() (선택, Claude Opus)
                                              │
                                              ▼
                          report_generator.generate_report() → .docx
```

### 두 개의 저장소
- **코드 레포(v3)**: 앱 로직 전체. Streamlit Cloud가 이 레포를 배포.
- **데이터 레포(v5, 비공개)**: 전시 레코드 JSON만 보관. 코드와 데이터를 분리하여
  데이터 변경이 코드 배포와 무관하게 일어나도록 함.

### KB 이중 모드 (`kb_store.get_mode()`)
- `KB_GITHUB_PAT`(secrets/env)가 있으면 **github 모드**(배포), 없으면 **local 모드**(개발).
- `KB_MODE`로 명시적 강제 가능.
- 설정 키: `KB_MODE`, `KB_LOCAL_PATH`(기본 `../exhibition-report-generator-v5`),
  `KB_GITHUB_REPO`(기본 `yoonjl-svg/exhibition-report-generator-v5`), `KB_GITHUB_PAT`,
  `KB_GITHUB_BRANCH`(기본 `main`).
- 데이터 경로: `data/exhibitions/`. 메모리 캐시 TTL 30초.

---

## 3. 화면 구조

### Workspace 모드 (`tabs/tab_workspace.py`)
- 미술관 전체 KPI metric strip (7개: 누적 전시 수, 분석 대상 수, 평균 관객, 평균 일평균,
  평균 예산, 평균 수입 등).
- 액션 바: **새 전시 데이터 생성 / 가져오기(모달) / 새로고침**.
- 가져오기 모달(`@st.dialog`): Excel 템플릿 탭 + JSON 파일 탭. 6시트 표준 템플릿 사용.
- 전시 카드 그리드: 연도별 그룹(최신 2026 상단), 1줄 4개. 카드 하단 메트릭은 이모지 1줄.
- 하단 expander: "누적 흐름 & 다중 전시 비교"(`tab_trend.py`).

### Detail 모드 (3탭)
1. **전시 데이터** (`tabs/tab_input.py`) — B(서술)+A(정량) 통합 단일 탭.
2. **분석 및 평가** (`tabs/tab_analysis.py`) — 자동 인사이트 카드 + 근거(Evidence).
3. **보고서 생성** (`tabs/tab_generate.py`) — 완성도 체크 → 미리보기 → LLM 재작성 →
   웹 인라인 편집 → Word 다운로드 / JSON 저장·불러오기.

> **참고(레거시)**: `tabs/tab_base.py`(구 기본정보), `tabs/tab_data.py`(구 정량데이터)는
> v5.3.23에서 `tab_input.py`로 통합된 뒤 **더 이상 렌더되지 않음**. 롤백 안전망으로 보존.
> `tab_data.py`의 일부 함수(`_create_data_template`/`_process_data_excel`)도 미사용.

---

## 4. 파일별 책임 (라인 수는 대략치)

| 파일 | 라인 | 역할 |
|------|------|------|
| `app.py` | ~849 | 진입점. 전역 CSS(테마), `init_session()`, 레퍼런스 로드 캐시, 사이드바, 라우팅(workspace/detail) |
| `tabs/tab_input.py` | ~718 | **전시 데이터** 통합 입력 탭 (13개 섹션) + 가져오기 모달 |
| `tabs/tab_analysis.py` | ~246 | **분석 및 평가** — 인사이트 카드, 근거 expander, 유사 전시 비교 |
| `tabs/tab_generate.py` | ~592 | **보고서 생성** — 완성도/미리보기/LLM/인라인 편집/Word/JSON |
| `tabs/tab_workspace.py` | ~487 | 워크스페이스 목록, KPI, 카드 그리드, 가져오기 모달 |
| `tabs/tab_trend.py` | ~529 | 누적 흐름(시계열 라인) + 다중 전시 비교(정규화 막대), Altair |
| `analysis_engine.py` | ~857 | 분석 엔진 — 인사이트/평가초안/유사전시 생성 |
| `reference_data.py` | ~675 | 레퍼런스 통계(평균/순위/백분위), 파생지표, 유사도, 유형 필터, KB→DF 변환 |
| `report_generator.py` | ~654 | python-docx Word 보고서 생성 (I~VI장) |
| `llm_writer.py` | ~504 | Claude API 산문 재작성 + 프롬프트 캐싱 + 비용 추정 |
| `chart_generator.py` | ~442 | matplotlib 차트(주차별/관객 파이/유사 비교 막대) |
| `styles.py` | ~591 | Word 스타일 시스템(글꼴/여백/제목 체계) |
| `kb_store.py` | ~400 | KB 저장소 어댑터(local/github), GitHub API |
| `kb_session.py` | ~234 | session_state ↔ KB 레코드 브리지 |
| `schema.py` | ~255 | v5 레코드 스키마, slug/timestamp/validate |
| `excel_template.py` | ~466 | 6시트 Excel 템플릿 생성·파싱 |
| `ui_helpers.py` | ~111 | 공통 UI 헬퍼(eyebrow/chip/metric/subsection) |
| `utils.py` | ~124 | `collect_analysis_data()`, `add_item`/`remove_item` |
| `sample_data.py` | ~141 | 테스트용 (가)하이퍼 옐로우 샘플 (배포 시 제거 가능) |
| `migrate_xlsx_to_kb.py` | — | 일회성: xlsx 18건 → v5 JSON 마이그레이션 |

---

## 5. 데이터 스키마 (`schema.py`)

`SCHEMA_VERSION = "1.0.0"`. **한 전시 = 한 JSON 파일**.

```jsonc
{
  "id": "2025-하이퍼-옐로우",          // slug = {연도}-{제목 슬러그}
  "version": "1.0.0",
  "status": "draft",                   // draft|in_progress|completed|archived
  "type": 1,                           // 0=분석제외, 1=정기기획전, 2=특별전, 3=기타
  "source": "form",                    // migration|form|excel|duplicate
  "created_at": "2026-05-29T...",      // ISO 8601
  "modified_at": "...",
  "finalized_at": null,
  "data": { /* 평면 dict: 모든 입력 필드 */ },
  "analysis_cache": null
}
```

- `make_slug(title, period_start)` → `"{year}-{슬러그}"`
- `validate(record)` → 문제 리스트(빈 리스트면 통과)
- 유형 분류: **0 분석제외 / 1 정기기획전 / 2 특별전 / 3 기타**. 비교 분석 시 동일 유형
  우선, 같은 유형 3건 미만이면 전체(유형 0 제외)로 폴백. 통계 기준은 **평균(mean)**.

### `data` 평면 dict 주요 키 (발췌)
- 서술: `exhibition_title`, `period_start/end`, `artists`, `chief_curator`/`curators`/
  `coordinators`/`curatorial_team`/`pr_person`/`sponsors`, `theme_text`,
  `graphic_designer`/`space_designer`, `rooms[]`, `related_programs[]`,
  `printed_materials[]`, `promo_*`, `press_print[]`/`press_online[]`, `visitor_reviews[]`.
- 정량(예산): `budget_exhibition`, `budget_supplementary`, `total_budget`(자동합),
  `budget_planned`, `ticket_revenue`, `other_revenue`, `total_revenue`(자동합).
- 정량(관객): `total_visitors`, `visitor_general/student/invitation/artpass/discover/
  discount`, `visitor_group`, `opening_attendance`, `weekly_visitors{}`.
- 정량(작품): `artwork_painting/sculpture/photo/installation/media/other`, `artwork_total`(자동합).
- 정량(프로그램): `program_count/sessions/participants`, `docent_regular/special`,
  `docent_total`(자동합).
- 정량(인력): `staff_paid`, `staff_volunteer`, `staff_total`(자동합 = 유급+봉사자).
- 정량(홍보): `press_count`, `web_invitation_count`, `newsletter_open_rate`,
  `sns_posts`, `sns_feedback`, `membership_count`, `sns_followers(_gained)`,
  `sns_avg_likes`(UI 라벨 "평균 피드백"), `sns_best_likes`(UI "최대 피드백"),
  `sns_best_post`(UI "최대 피드백 게시물 내용").

---

## 6. 입력 탭 (`tab_input.py`) — 13개 섹션 순서

1. **전시 기본** (4단: 기본정보 / 기획진 / 디자인 / 인력[유급·봉사자]) + 운영·예산을
   같은 헤더 아래 통합. 예산은 1행 5열(계획액→전시→부대→입장수입→기타수입).
2. **관객** (총관객+일평균자동 / 입장권별 8칸 1줄 / 주차별 11주 1줄)
3. **전시 주제와 내용**(서문 textarea) + **전시실 구성**(2×2 그리드, 도면·전경사진 가로)
4. **출품 작품**(매체별 6칸)
5. **전시 연계 프로그램**(행 반복 + 요약 수치)
6. **인쇄물 및 굿즈** (단독 섹션)
7. **홍보 방식** (textarea 6종, 좌측 50%)
8. **홍보 지표** + SNS 상세
9. **언론보도 리스트** (일간지/월간지 + 온라인 2단)
10. **관객 후기** (분류 긍정/부정/기타 + 내용 + 출처)

- 상단에 **가져오기 모달**(`@st.dialog`) — 워크스페이스와 동일한 6시트 Excel + JSON.
  데이터 탭에서는 "현재 편집 중인 전시에 덮어쓰기"로 동작.
- 합계 필드(`total_budget`, `total_revenue`, `artwork_total`, `staff_total`,
  `docent_total`)는 입력값에서 자동 계산되어 session_state에 저장.

---

## 7. 분석 엔진 (`analysis_engine.py`)

### 진입점
```python
generate_all_insights(current_data, ref_df, exhibition_type=None) -> AnalysisResult
```
`AnalysisResult { insights[], eval_drafts[], similar_exhibitions[], similar_comparison_table }`

### Insight 데이터클래스(주요 필드)
`category, section, title, text, metric_name, current_value, reference_avg,
percentile, rank, total_count, priority(1~3), unit, is_ratio`

- `section ∈ {results, composition, promotion, evaluation}` → 보고서 배치 위치.
- `priority`: 1=중요(빨강), 2=보통(주황), 3=참고(노랑). diff·순위 기반 salience 자동 산출.
- `unit`/`is_ratio`: 근거(Evidence) 표시용 — 비율 지표는 ×100 %, 차이는 %p.

### 카테고리 분석 함수
| 함수 | 분석 내용 | 배치 |
|------|----------|------|
| `_analyze_visitors` | 총관객, 일평균, 유료비율, 학생, 예술인패스 | results |
| `_analyze_budget` | 총예산, 관객당비용, 예산구조(전시비/부대비), 회수율 | results |
| `_analyze_programs` | 프로그램 수, 참여인원, 참여율 | composition |
| `_analyze_artworks` | 총수, 매체별 구성 비율 | composition |
| `_analyze_promotion` | 보도건수, 보도건당관객, SNS | promotion |
| `_analyze_staff` | 인력당 관객 | composition |
| `_analyze_cross` | 예산vs관객 효율, 홍보vs관객, 수입회수 (priority=1 고정) | evaluation |

### 평가 초안 (`_generate_eval_drafts`)
- `EvalDraft { eval_type(positive/negative/improvement), text, source_metric, confidence }`
- 규칙: diff > 15% → 긍정 / diff < -15% → 부정 / diff < -20% → 개선 제안.
  (eval_type, source_metric) 중복 제거.

### 유형 필터
- `filter_by_type`: 동일 유형 ≥3건이면 동일 유형, 아니면 전체(유형0 제외) 폴백.
- `get_type_label`: 1/2/3 → "기존 기획전/특별전/전시", 폴백 시 "역대 전시".

---

## 8. 레퍼런스 통계 (`reference_data.py`)

- `load_reference(xlsx)` — Row2=컬럼명, Row3+=데이터. "-"/빈칸 → NaN.
- `compute_stats(df, col)` → `FieldStats`(mean/median/min/max/std/quartile/values).
- `compute_percentile(stats, v)` → 0~100. `compute_rank(stats, v, ascending)` → 순위.
- `compute_derived_metrics(df)` → 파생열 추가(`관객당_비용`, `수입_예산_비율`,
  `유료_비율`, `프로그램_참여율`, `보도건당_관객`).
- `get_similar_exhibitions(df, cur, top_n)` — 가중 유사도(예산 35%, 기간 25%, 관객 25%,
  작가수 15%).
- `kb_records_to_reference_df(records)` — v5 KB 레코드 리스트 → 분석엔진 호환 DataFrame.
  (앱은 KB 우선 로드, 실패 시 `exhibition_reference_data.xlsx` 폴백.)

---

## 9. 보고서 생성 (`report_generator.py`)

`generate_report(data, output_path)` → `ExhibitionReportGenerator(data).generate()` → .docx

### 보고서 구조 (장 순서)
- **I. 전시 개요**
- **II. 전시 주제와 내용**
- **III. 전시 구성** (전시실 / 연계 프로그램 / 운영 인력 / 인쇄물·굿즈)
- **IV. 전시 결과** (예산·지출 / 관객수·수익 결산 / 관객 구성) — 차트 삽입(주차별, 관객 파이)
- **V. 홍보 방식 및 언론 보도** (데이터 있을 때만)
- **VI. Executive Summary** (핵심 수치 종합 / 종합 의견 / 관객 반응 종합 / 유사 전시 비교 / 데이터 도출 평가)

### 인사이트 주입
- `data["section_insights"]`(규칙 기반)과 `data["llm_sections"]`(LLM 산문)을 받음.
- `_insert_section_insights(section_key)`: **llm_sections 우선**, 없으면 규칙 기반 불릿.
- 인사이트 채택 여부 계약: `insight_selections[f"ins_{section}_{i}"]`(bool),
  `insight_texts[key]`(편집 텍스트). 이 key 포맷은 분석 탭↔생성 탭 간 고정 계약.

---

## 10. LLM 재작성 (`llm_writer.py`)

- 진입: `rewrite_insights(...) -> LLMWriterResult`
  (`sections, model_used, is_fallback, input/output/cache 토큰, error`)
- **모델**: `MODEL = "claude-opus-4-7"`.
- **프롬프트 캐싱**: 시스템 메시지 2블록 — `SYSTEM_PROMPT`(기본 캐시) + few-shot 예시
  블록에 `cache_control: ephemeral`. `cache_creation/read_input_tokens` 추적.
- **톤 규칙(SYSTEM_PROMPT 요지)**: 공문서체 "~임/~하였음"(구어체 "~니다", 논문체 "~이다"
  금지), 신문 기사처럼 사실 중심 간결, 평가 어휘 금지, 헤지 표현 사용, 비교는
  `[比 《전시명》(수치)]` 각주식, 없는 수치 날조 금지.
- 5개 섹션 산문화: results→IV, composition→III, promotion→V, evaluation→VI 종합 의견,
  audience_response→VI 관객 반응 종합.
- API 키 없으면 규칙 기반 인사이트로 폴백(`is_fallback=True`).

---

## 11. 보고서 생성 탭 (`tab_generate.py`) 흐름

1. **완성도 체크** — 9개 필수 항목 프로그레스 바.
2. **구조 미리보기** — 6개 장 트리.
3. **AI 작성 설정** — Anthropic API 키 입력·검증.
4. **생성** — `_collect_report_data()` → `ae.compute_summary_metrics()` →
   (키 있으면) `llm_writer.rewrite_insights()` → `st.session_state["report_state"]`.
5. **웹 인라인 편집** — 각 LLM 섹션을 text_area로 편집(`preview_edit_*`). 편집분이
   다운로드 시 `final_data["llm_sections"]`로 병합. "원본으로 되돌리기" 버튼.
6. **Word 다운로드 / JSON 저장·불러오기** (`_pending_json` 패턴으로 위젯 충돌 회피).

---

## 12. Word 스타일 (`styles.py`)
- 글꼴 Noto Sans CJK KR(본문 10pt, 제목 16pt), A4, 여백 2cm.
- 제목 체계 I. → 1. → 1) → ① ② ③. 차트 matplotlib 한국어 폰트 폴백.

---

## 13. UI 설계 원칙 (CLAUDE.md에 명문화, 반드시 준수)
1. **가로 폭 상한**: 콘텐츠는 무한정 늘어나지 않음. 읽기·편집 콘텐츠는 페이지 ~55–65%,
   숫자·짧은 입력은 좁은 컬럼 + spacer. 풀폭 강박 금지.
2. **이모지 금지**: 버튼·헤더·라벨·카드 제목.
3. **중복 정보 제거**: 탭명·섹션 헤더가 이미 전달하는 정보 반복 금지.

### 타이포그래피 위계(CSS 변수)
L5 12px(라벨/캡션/칩) · L4 13px · L3 14px(입력값·위젯 라벨·하위섹션) · L2 16px(섹션) ·
L1 22px(페이지 타이틀) · Display 19px(metric 값). 색: `--accent #255c4a`(녹색),
`--accent-2 #b4512a`(테라코타), `--accent-3 #3f5e99`(블루).

### 입력창 스타일(v5.3.52, DOM 실측 후 확정)
- 테두리·라운드는 BaseWeb 바깥 컨테이너에만(이중 테두리 제거), 내부 input 투명.
- text/number/date/select 높이 **38px 통일**. number 스테퍼(±) 제거.

---

## 14. 알려진 한계 / 검수 요청 포인트

1. **이미지 업로드 비영속**: `st.file_uploader`로 받은 도면·사진은 세션 종료 시 소실.
   KB JSON에는 이미지가 저장되지 않음(텍스트·숫자만). → 영속화 방안 검토 필요.
2. **레거시 사문화 파일**: `tab_base.py`, `tab_data.py`는 미사용이나 잔존. 정리 시점 판단 필요.
3. **평가 초안 다양성**: 규칙 기반이라 문장 다양성 제한적(LLM 미사용 시).
4. **조사 처리**: "은/는", "으로/로" 한국어 조사 자동 처리(`_postposition`)가 일부
   매체명·수치에서 어색할 수 있음.
5. **GitHub PAT 만료**: fine-grained PAT 만료 시 워크스페이스 401. 코드로 복구 불가
   (secrets 교체 필요). v5.3.44에서 에러 메시지 명확화.
6. **유사도 가중치**: `get_similar_exhibitions`의 가중치(예산35/기간25/관객25/작가15)는
   휴리스틱. 도메인 타당성 검토 여지.
7. **표본 수 임계**: 통계는 유효표본 ≥3건일 때만 인사이트 생성. 18건 중 유형 분할 시
   유형별 표본이 작아질 수 있음(특별전 5건, 기타 2건).
8. **단일 프로세스 동시성**: KB 캐시는 프로세스 메모리(30초 TTL). 다중 사용자 동시 편집
   시 충돌 가능성(현재 단일 큐레이터 가정).

---

## 15. 배포 / 실행

- Streamlit Cloud, Python 3.9+. `requirements.txt`(anthropic 포함), `packages.txt`(fonts-noto-cjk).
- secrets에 `KB_GITHUB_PAT`(Contents R/W, v5 레포 접근) 필요 → github 모드.
- 로컬 개발: PAT 없이 `../exhibition-report-generator-v5` 클론을 local 모드로 사용.
- 테스트: 사이드바 "샘플 채우기"((가)하이퍼 옐로우) → detail 모드 자동 진입.

---

## 16. 버전 메모(요약)
- **v3**: 4탭(기본정보/정량/분석/생성). 분석을 보고서 인라인 배치, 매체별 작품 등 신규.
- **v5**: KB(별도 저장소) 도입, 워크스페이스(전시 목록) 모드, Excel/JSON 가져오기,
  누적 흐름·다중 비교(Altair).
- **v5.3.x**: UI 정밀화(가로폭 원칙·이모지 제거·입력창 통일), 4탭→3탭(데이터 통합),
  분석 탭 '근거' 패턴, 가져오기 일원화, GitHub 에러 진단 등.
