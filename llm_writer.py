"""
LLM 기반 분석 글쓰기 모듈 (하이브리드 방식)

- 인사이트 탭(C): 룰 기반 요약을 즉시 표시
- 보고서 생성(D): Claude API를 호출하여 보고서 문체로 재작성
- API 키가 없으면 룰 기반 텍스트로 자동 폴백
"""

import json
from dataclasses import dataclass

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096

# 보고서 섹션 한국어 매핑
SECTION_NAMES = {
    "results": "IV. 전시 결과",
    "composition": "III. 전시 구성",
    "promotion": "V. 홍보 방식 및 언론 보도",
    "evaluation": "VI. 평가 및 개선 방안",
}


# ──────────────────────────────────────────────
# Few-shot 예시: 일민미술관 보고서 분석 문체
# ──────────────────────────────────────────────

FEW_SHOT_EXAMPLES = """
아래는 일민미술관 전시보고서에서 발췌한 실제 분석 문단입니다. 이 문체와 구조를 충실히 따르세요.

<example section="results" source="《시대복장》">
→ 전시 예산의 114.6% 사용: 신작 프로덕션을 포함한 작품 제작비가 이번 전시 예산의 주요 지출 항목임. 워크룸과의 기획 협력 사항 외, 메인 그래픽 디자인에 대한 사례비를 계획 예산 보고 후 추가 책정함에 따라 인쇄물 제작비 항목이 계획 대비 초과하였음.

짧은 전시 기간(45일)이었지만, 관객 통계 집계 후(2021~) 진행된 전시의 일평균 관객(125명) 대비 260% 상승한 325명대를 기록하였음. [比 《하이퍼 옐로우》(전시운영일수 52일, 일평균 130명), 《포에버리즘》(전시 운영일수 63일, 일평균 190명), 《I Like To Watch》(전시 운영일수 57일, 일평균 166명)]
</example>

<example section="results" source="《히스테리아》">
→ 계획 예산의 121.9% 사용: 관객 증가로 인한 전시 인쇄물 추가 발주(리플릿 1회, 티켓 1회), 작품 보호를 위한 아트리움 유리창 틴팅 시공, 출품작 수 증가로 인한 작품 운송 및 설치비 증가, 아트상품 제작 등이 요인임. 전반적으로는 최근 원자재 가격 상승의 영향을 받았음.

동시대 구상 회화의 경향을 살핀 기획전으로 순수미술을 다룬 과거 전시 대비 높은 관객 수를 기록함. [比 《다시 그린 세계》(관객 수 총 7,421명, 일 평균 118명), 《IMA Picks 2021》(관객 수 총 5,166명, 일 평균 78명)]
</example>

<example section="results" source="《다시 그린 세계》">
전시 계획서 기준, 총 124,507,088원 예산 설정(자부담금 92,907,088원, 지원금 25,600,000원) → 계획 예산의 106.4% 사용: 자연 재해로 인한 현수막 재제작, 전시 연계 프로그램 추가 진행 등이 요인.

순수 미술의 예술성에 집중하는 하반기 기획전으로서 미술관 평균을 상회하는 것에 의미를 둠. [比 《IMA Picks 2021》(관객 수 총 5,166명, 일 평균 78명)]
</example>

<example section="results" source="《형상 회로》">
→ 전시 예산의 106.6% 사용: 국내 작품 운송비를 계획 대비 약 32% 초과 지출함. 세로 3m 이상 대형 작품 다수 출품으로 인한 5t 차량 사용, 원거리(대구, 군산, 인천) 반입·반출이 요인임.

→ 부대 예산의 109.6% 사용: 국외 체류 작가(심현빈, 호상근, 나디아 지와) 초대로 인한 국외 작품 운송비 지출로 국제교류 진행비를 약 17% 초과 지출하였으나, 전시 연계 프로그램 진행비, 홍보비, 아트상품 제작비 등은 격차 없이 지출 완료함.
</example>

<example section="promotion" source="《데코 데코》">
한강주조 겨울 에디션 게시물(좋아요 470개)이 가장 좋은 반응을 얻었으며 전시 콘텐츠 대비 미술관 콘텐츠의 관심도가 높게 나타남. 기존 SNS 팔로워의 성향 확인 및 타게팅 참고 지표가 되었음.

주요 홍보를 『엘르』 온라인 채널로 진행하였으나 현장 발권이 많았던 점은, 미술관의 대중적 인지도를 반영하는 결과로 긍정 평가할 수 있음.
</example>

<example section="promotion" source="《언커머셜》">
평균 31.65%의 오픈율(11월 16일 《IMA Picks 2021》오픈 뉴스레터 29.3%, 12월 25일 시즈널 티켓 뉴스레터 31.2% 등 오픈율 증가세 유지)
</example>

<example section="evaluation" source="《데코 데코》">
팔로워는 증가 추세이나 게시물 전반의 '좋아요' 수는 작년 대비 감소 추세임. SNS 주사용자인 2⋅30대가 기존의 '피드' 형식보다는 '스토리'나 '릴스' 등의 신규 게시 형식을 선호하는 것이 원인으로 추정됨. 이에 대응 방안을 모색하여 시대 흐름에 발맞춘 홍보 방안을 마련하고자 함.
</example>

<example section="evaluation" source="《시대복장》">
다소 쉽게 소비되거나 휘발될 수 있는 패션 전시를 학예실의 비평적 관점과 시각 디자인, 출판이라는 새로운 접근을 통해 조명함으로써 각 스튜디오의 디자인 철학과 전시 맥락에 대한 깊이 있는 시사점을 제공하고 전시에 대한 이해를 확장하고자 했음. 이러한 시도는 관객 후기에서도 확인되듯, 참여자들로부터 높은 만족도를 얻음.
</example>

<example section="evaluation" source="《하이퍼 옐로우》">
제도적 기준을 제시하는 미술관에서 작가 임민욱의 개인전을 10년 만에 개최, 원숙기에 이른 중견 작가의 장기 연구 주제를 심화할 수 있도록 작품 활동을 지원하고 작업적 도약을 함께 모색함으로써 한국 미술계에 기여함.
</example>

<example section="evaluation" source="《포에버리즘》">
→ 계획 예산의 100.3% 사용: 영상 관람 환경을 개선하기 위한 공간조성비(가벽, 커텐 등) 지출, 정연두의 작품 복각을 위한 장비 구매비 지출(환등기, 컨트롤러 등)이 전시 예산 초과의 주요 요인임. 한편 홍보물(리플릿, 티켓) 실사용 수량 예측에 성공하여 낭비 없는 인쇄제작비의 계획적 운용, 연계 프로그램 간소화가 부대 예산 절감의 주요 요인임.

문화적 화두와 미술의 화두를 두루 포섭하며 대중성과 예술성 양자를 충족한 전시 기획의 결과로 판단됨.
</example>
"""


# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 일민미술관의 전시보고서 분석 문단을 작성하는 전문 에디터입니다.

## 일민미술관 보고서 문체 — 기본 규칙

아래 규칙은 17건의 실제 보고서를 분석하여 추출한 것입니다.

1. **종결어미**: "~임", "~하였음", "~요인임", "~확인함", "~의미를 둠", "~판단됨" 등 실무 보고서 투 사용. "~이다", "~분석된다" 같은 학술적 종결은 금지
2. **비교 표기 [比]**: 과거 전시와 비교 시 반드시 [比 《전시명》(구체적 수치)] 형식을 사용. ⚠️ 이 형식은 절대 변형하지 마세요. 괄호, 낫표(《》), [比] 표기를 그대로 유지하세요.
3. **예산 분석 패턴**: "→ 계획 예산의 X% 사용: (이유 나열)" — 이 패턴도 그대로 유지. 화살표(→)로 시작, 콜론(:) 뒤 원인 나열
4. **팩트 중심 간결체**: 사실 전달에 집중. 한 문장에 하나의 팩트. 불필요한 수식어 배제
5. **원인-결과 연결**: "~로 인한", "~가 요인임" 등 인과 관계를 명시적으로 서술
6. **정량 + 정성**: 수치를 제시한 뒤 그것이 의미하는 바를 한 문장으로 해석. 과잉 해석 금지
7. **한 섹션당 2~5문장**: 간결하게. 각 문장은 구체적 수치나 사실을 포함

## 윤문 자율성 — 편집 권한과 한계

기존 보고서의 문체를 참고 범위로 삼되, 아래와 같은 **편집 자율성**을 부여합니다:

✅ **다듬어도 되는 것** (자연스럽고 간결한 표현 권장):
- "상회하다/하회하다" → "높다/낮다", "많다/적다" 등 간결한 표현으로 교체 가능
- "기록하였음" → "기록함" 등 불필요한 과거형 축약 가능
- "~에 달했습니다" → "~에 이름" 등 경직된 문어체를 자연스러운 보고서체로 전환 가능
- 같은 구문의 반복을 피하고 문장 변주를 줄 수 있음
- 긍정/부정 평가 시 "~에 의미를 둠", "~긍정적으로 평가할 수 있음" 등 절제된 어조 유지하되, 자연스러운 표현 선택 가능

🚫 **절대 변형 금지** (형식적 일관성 보호):
- [比 《전시명》(수치)] — 이 형식은 반드시 그대로 유지
- → 계획 예산의 X% 사용: — 이 패턴은 반드시 그대로 유지
- 수치 자체를 변경하거나 반올림/가공하는 것은 금지
- 없는 수치를 만들어내는 것은 금지
- "~임", "~하였음" 종결어미 체계를 "~이다", "~했다" 등으로 바꾸는 것은 금지

## 중요: 인사이트 데이터의 활용

당신에게 제공되는 "인사이트"는 룰 기반 엔진이 생성한 수치 비교 결과입니다. 이 수치와 비교 데이터를 정확히 유지하면서, 위 규칙에 맞게 보고서 문단으로 통합 재작성하세요.

## 출력 형식

반드시 아래 JSON 형식으로 출력하세요. 다른 텍스트는 포함하지 마세요.

```json
{
  "results": "IV. 전시 결과 섹션에 삽입할 분석 문단",
  "composition": "III. 전시 구성 섹션에 삽입할 분석 문단",
  "promotion": "V. 홍보 섹션에 삽입할 분석 문단",
  "evaluation": "VI. 평가 섹션에 삽입할 종합 분석 문단"
}
```

비어있는 섹션은 빈 문자열("")로 두세요.
"""


# ──────────────────────────────────────────────
# 사용자 프롬프트 구성
# ──────────────────────────────────────────────

def _build_user_prompt(
    exhibition_title: str,
    insights_by_section: dict,
    analysis_data: dict,
    eval_drafts: list = None,
) -> str:
    """API에 보낼 사용자 프롬프트를 구성"""

    # 1. 전시 기본 정보
    prompt = f"## 전시 정보\n전시 제목: 《{exhibition_title}》\n\n"

    # 핵심 수치 요약
    key_metrics = []
    metric_map = {
        "총 관객수": ("명", True),
        "일평균 관객수": ("명", True),
        "총 사용 예산": ("원", True),
        "전시 사용 예산": ("원", True),
        "총수입": ("원", True),
        "입장 수입": ("원", True),
        "전시 일수": ("일", True),
        "출품 작품 수_총": ("점", True),
        "프로그램 총 수": ("개", True),
        "프로그램 참여 인원": ("명", True),
        "언론 보도 건수": ("건", True),
        "운영 인력_총": ("명", True),
        "SNS 게시 건수": ("건", True),
    }
    for field, (unit, _) in metric_map.items():
        val = analysis_data.get(field)
        if val:
            key_metrics.append(f"- {field}: {val:,.0f}{unit}" if isinstance(val, (int, float)) else f"- {field}: {val}")

    if key_metrics:
        prompt += "## 핵심 수치\n" + "\n".join(key_metrics) + "\n\n"

    # 2. 섹션별 인사이트 (룰 기반)
    prompt += "## 섹션별 인사이트 (룰 기반 분석 결과)\n\n"
    prompt += "아래 인사이트들을 보고서 문체로 재작성하세요. 수치와 비교 데이터는 정확히 유지하되, 문장을 자연스러운 보고서 문체로 통합하세요.\n\n"

    for section_key, section_name in SECTION_NAMES.items():
        section_insights = insights_by_section.get(section_key, [])
        if section_insights:
            prompt += f"### {section_name}\n"
            for ins in section_insights:
                prompt += f"- {ins['text']}\n"
            prompt += "\n"

    # 3. 사용자 평가 메모
    if eval_drafts:
        prompt += "## 담당자 평가 메모\n"
        prompt += "아래는 담당 큐레이터가 직접 작성한 평가 메모입니다. VI. 평가 섹션 작성 시 이 내용을 반드시 반영하세요.\n\n"
        for ed in eval_drafts:
            type_label = {"positive": "긍정", "negative": "부정/한계", "improvement": "개선 방안"}.get(ed.get("eval_type", ""), "")
            prompt += f"- [{type_label}] {ed['text']}\n"
        prompt += "\n"

    # 4. 문체 예시
    prompt += f"## 참고: 일민미술관 보고서 문체 예시\n{FEW_SHOT_EXAMPLES}\n"

    return prompt


# ──────────────────────────────────────────────
# API 호출
# ──────────────────────────────────────────────

@dataclass
class LLMWriterResult:
    """LLM 글쓰기 결과"""
    sections: dict          # {section_key: 분석 문단 텍스트}
    model_used: str         # 사용된 모델명
    is_fallback: bool       # 룰 기반 폴백 여부
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""


def rewrite_insights(
    api_key: str,
    exhibition_title: str,
    insights_by_section: dict,
    analysis_data: dict,
    eval_drafts: list = None,
) -> LLMWriterResult:
    """
    선택된 인사이트를 보고서 문체로 재작성

    Parameters:
        api_key: Anthropic API 키
        exhibition_title: 전시 제목
        insights_by_section: {section_key: [{"text": ..., "category": ...}, ...]}
        analysis_data: collect_analysis_data()의 결과
        eval_drafts: 선택된 평가 초안 리스트

    Returns:
        LLMWriterResult
    """

    # API 키 없으면 폴백
    if not api_key or not api_key.strip():
        return _fallback_result(insights_by_section)

    # anthropic 패키지 없으면 폴백
    if not HAS_ANTHROPIC:
        return LLMWriterResult(
            sections={},
            model_used="none",
            is_fallback=True,
            error="anthropic 패키지가 설치되지 않았습니다. pip install anthropic 실행 후 재시도하세요."
        )

    try:
        client = anthropic.Anthropic(api_key=api_key.strip())

        user_prompt = _build_user_prompt(
            exhibition_title, insights_by_section, analysis_data, eval_drafts
        )

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # 응답 파싱
        raw_text = response.content[0].text.strip()

        # JSON 블록 추출 (```json ... ``` 감싸진 경우 처리)
        if "```json" in raw_text:
            start = raw_text.index("```json") + 7
            end = raw_text.index("```", start)
            raw_text = raw_text[start:end].strip()
        elif "```" in raw_text:
            start = raw_text.index("```") + 3
            end = raw_text.index("```", start)
            raw_text = raw_text[start:end].strip()

        sections = json.loads(raw_text)

        return LLMWriterResult(
            sections=sections,
            model_used=MODEL,
            is_fallback=False,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    except json.JSONDecodeError as e:
        return LLMWriterResult(
            sections={},
            model_used=MODEL,
            is_fallback=True,
            error=f"API 응답 파싱 오류: {e}\n원문: {raw_text[:500]}"
        )
    except anthropic.AuthenticationError:
        return LLMWriterResult(
            sections={},
            model_used=MODEL,
            is_fallback=True,
            error="API 키가 유효하지 않습니다. 올바른 Anthropic API 키를 입력해주세요."
        )
    except anthropic.RateLimitError:
        return LLMWriterResult(
            sections={},
            model_used=MODEL,
            is_fallback=True,
            error="API 호출 한도를 초과했습니다. 잠시 후 재시도해주세요."
        )
    except Exception as e:
        return LLMWriterResult(
            sections={},
            model_used=MODEL,
            is_fallback=True,
            error=f"API 호출 오류: {str(e)}"
        )


def _fallback_result(insights_by_section: dict) -> LLMWriterResult:
    """API 없이 룰 기반 텍스트를 그대로 반환"""
    sections = {}
    for section_key, insights in insights_by_section.items():
        if insights:
            texts = [ins["text"] for ins in insights if ins.get("text")]
            sections[section_key] = " ".join(texts)
        else:
            sections[section_key] = ""

    return LLMWriterResult(
        sections=sections,
        model_used="rule-based",
        is_fallback=True,
    )


# ──────────────────────────────────────────────
# 비용 추정 유틸리티
# ──────────────────────────────────────────────

def estimate_cost(input_tokens: int, output_tokens: int) -> dict:
    """Sonnet 기준 비용 추정 (USD)"""
    # Claude Sonnet 가격 (2025년 기준)
    input_price_per_mtok = 3.0    # $3 per 1M input tokens
    output_price_per_mtok = 15.0  # $15 per 1M output tokens

    input_cost = (input_tokens / 1_000_000) * input_price_per_mtok
    output_cost = (output_tokens / 1_000_000) * output_price_per_mtok
    total_cost = input_cost + output_cost

    # 원화 환산 (대략적)
    krw_rate = 1350
    total_krw = total_cost * krw_rate

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(total_cost, 4),
        "cost_krw": round(total_krw, 1),
    }


# ──────────────────────────────────────────────
# API 키 검증
# ──────────────────────────────────────────────

def validate_api_key(api_key: str) -> tuple[bool, str]:
    """API 키 형식 및 유효성 간이 검증"""
    if not api_key or not api_key.strip():
        return False, "API 키가 비어있습니다."

    key = api_key.strip()
    if not key.startswith("sk-ant-"):
        return False, "Anthropic API 키는 'sk-ant-'로 시작해야 합니다."

    if len(key) < 40:
        return False, "API 키가 너무 짧습니다."

    return True, "형식이 올바릅니다."
