import re


# ---------------------------------------------------------
# ORION Event Understanding Engine v1
#
# 목적:
# 단순히 AI, 투자, 반도체 같은 단어가 있다고 사건으로 만들지 않는다.
#
# 반드시
# "실제로 무엇인가 발생했는가?"
# 를 먼저 판단한다.
# ---------------------------------------------------------


def normalize_text(text):
    return re.sub(
        r"\s+",
        " ",
        str(text or "").lower()
    ).strip()


def contains_any(text, patterns):
    return any(
        pattern.lower() in text
        for pattern in patterns
    )

def has_speculative_context(text):
    """
    실제 확정 사건이 아니라
    전망·가능성·우려·가정·분석 문맥인지 판별
    """

    speculative_patterns = [
        # 한국어
        "가능성",
        "가능성이",
        "전망이다",
        "전망된다",
        "전망",
        "예상된다",
        "예상",
        "우려",
        "기대된다",
        "기대",
        "관측",
        "될 수",
        "할 수",
        "주간증시전망",

        # 영어
        "could",
        "may ",
        "might",
        "potential",
        "possibly",
        "expected to",
        "could happen",
        "what happens if",
    ]

    return contains_any(
        text,
        speculative_patterns
    )


def is_analysis_article(title):
    """
    새로운 사건 발표가 아니라
    투자분석·위험분석·전망 기사인지 판별
    """

    analysis_patterns = [
        "biggest risk",
        "risk facing",
        "what happens if",
        "is it a buy",
        "should you buy",
        "prediction:",
        "what to do now",
        "outlook",
        "주간증시전망",
        "증시전망",
    ]

    return contains_any(
        title,
        analysis_patterns
    )
def understand_event(article):

    title = normalize_text(
        article.get("title", "")
    )

    summary = normalize_text(
        article.get("summary", "")
    )

    text = f"{title} {summary}".strip()

        # =====================================================
    # 기사 역할 판별
    #
    # 새로운 사건 발표가 아닌
    # 위험분석·투자분석·시장전망 기사는 사건에서 제외
    # =====================================================

    if is_analysis_article(title):
        return {
            "is_real_event": False,
            "event_type": "NO_EVENT",
            "reason": "분석·전망 기사이며 신규 확정 사건이 아님"
        }
    # =====================================================
    # 1. 명백한 비사건 콘텐츠
    # 가장 먼저 제거한다.
    # =====================================================

    no_event_patterns = [

        # 매수/추천
        "stocks to watch",
        "stocks to buy",
        "stock to buy",
        "better buy",
        "best stocks",
        "top stock",
        "stock pick",
        "should you buy",
        "worth buying",
        "we love",
        "investors are missing",

        # 투자 조언
        "urges investors",
        "for investors",
        "what investors need to know",
        "spread bets",
        "to consider",

        # 단순 주가 기사
        "why is",
        "why shares",
        "stock surging",
        "stock plunging",
        "stock tumbling",
        "stock sliding",
        "here's why",
        "here’s why",

        # 시장 프리뷰
        "dow jones futures",
        "data due",
        "set to report earnings",
        "earnings preview",

        # 밸류에이션/해설
        "forward earnings",
        "price target",
        "valuation",
        "times earnings",

        # 한국어
        "추천주",
        "주목할 종목",
        "매수 추천",
        "목표가",
        "투자 포인트",
        "살까",
        "사야 할까",
    ]

    if contains_any(text, no_event_patterns):

        return {
            "is_real_event": False,
            "event_type": "NO_EVENT",
            "reason": "투자권유·해설·시장반응 콘텐츠"
        }

    # =========================================================
    # FOMC / FED 정책 이벤트
    # 반드시 미국 연준이 주체여야 함
    # =========================================================
    
    fed_subject_patterns = [
        "federal reserve",
        "the fed",
        "fed ",
        "fed's",
        "fomc",
        "연준",
        "미 연준",
        "미국 연준",
        "연방준비제도",
    ]

    fed_action_patterns = [
        "cuts interest rates",
        "cut interest rates",
        "raises interest rates",
        "raise interest rates",
        "rate cut",
        "rate hike",
        "cuts rates",
        "raises rates",
        "금리 인하",
        "금리 인상",
        "기준금리 인하",
        "기준금리 인상",
    ]

    if (
        contains_any(text, fed_subject_patterns)
        and contains_any(text, fed_action_patterns)
    ):

        # 가능성·전망·우려는 실제 FOMC 결정이 아니다.
        if has_speculative_context(text):
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "미국 금리 전망·가능성이며 실제 정책 결정이 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "FOMC",
            "reason": "실제 미국 통화정책·금리 결정"
        }
    # =====================================================
    # 3. POLICY / 관세 / 수출규제 / 제재
    # =====================================================

    policy_patterns = [
        "imposes tariff",
        "impose tariff",
        "announces tariff",
        "raises tariff",
        "tariff on",
        "export restrictions",
        "export restriction",
        "export ban",
        "imposes sanctions",
        "announces sanctions",

        "관세 부과",
        "관세 인상",
        "수출 규제",
        "수출 제한",
        "수출 금지",
        "제재 발표",
    ]
    if contains_any(text, policy_patterns):

        # "관세 부과 시", "부과할 경우" 등은
        # 실제 정책 시행이 아니라 가정이다.
        hypothetical_policy = contains_any(
            title,
            [
                "관세 부과 시",
                "관세 부과할 경우",
                "관세를 부과할 경우",
                "tariff if",
                "if tariff",
            ]
        )

        if hypothetical_policy:
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "가정형 정책 기사이며 실제 정책 결정이 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "POLICY",
            "reason": "실제 정부 정책·관세·수출규제 변화"
        } 

        
    # =====================================================
    # 2. M&A
    #
    # 핵심:
    # '인수'라는 단어가 있다는 것과
    # 실제 인수가 확정됐다는 것은 다르다.
    # =====================================================

    ma_confirmed_en = [
        "agrees to buy",
        "agreed to buy",
        "agrees to acquire",
        "agreed to acquire",
        "acquires",
        "acquired",
        "completes acquisition",
        "completed acquisition",
        "merger completed",
        "merger approved",
    ]

    if contains_any(text, ma_confirmed_en):
        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "실제 인수·합병 사건"
        }

    korean_ma_candidate = contains_any(
        title,
        [
            "인수",
            "합병",
        ]
    )

    korean_ma_uncertain = contains_any(
        title,
        [
            "인수 검토",
            "인수 추진 검토",
            "인수설",
            "인수 가능성",
            "인수 협상",
            "합병 검토",
            "합병 가능성",
            "동시 검토",
        ]
    )

    if korean_ma_candidate and not korean_ma_uncertain:
        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "제목에서 확인된 실제 인수·합병 사건"
        }

    # =====================================================
    # 3. 계약 / 수주 / 공급
    # =====================================================

    contract_patterns = [
        "wins contract",
        "won contract",
        "signed contract",
        "signs contract",
        "supply contract",
        "supply agreement",
        "purchase order",
        "order backlog",
        "orderbook",

        "공급계약",
        "공급 계약",
        "계약 체결",
        "수주잔고",
    ]

    if contains_any(text, contract_patterns):
        return {
            "is_real_event": True,
            "event_type": "CONTRACT",
            "reason": "실제 계약·수주·공급 변화"
        }

    # -----------------------------------------------------
    # 한국어 신규 수주
    #
    # 숫자 + '수주'만으로는 부족하다.
    # 과거 수주 조사/비리/평가 문맥은 신규 사건이 아니다.
    # -----------------------------------------------------

    korean_order_has_value = (
        re.search(
            r"\d[\d,.]*\s*(억|억원|조|조원|만원|원)",
            title
        )
        or re.search(
            r"\d[\d,.]*\s*(척|대|개|건)",
            title
        )
    )

    korean_order_context_only = contains_any(
        title,
        [
            "수주 과정",
            "수주 과정 조사",
            "수주 비리",
            "수주 의혹",
            "수주 관련 조사",
            "유리한 평가",
        ]
    )

    if (
        "수주" in title
        and korean_order_has_value
        and not korean_order_context_only
    ):
        return {
            "is_real_event": True,
            "event_type": "CONTRACT",
            "reason": "제목에서 금액·수량과 함께 확인된 신규 수주"
        }

    # =====================================================
    # 4. CAPEX / 투자 / 증설
    # =====================================================

    capex_patterns = [
        "to invest",
        "will invest",
        "plans to invest",
        "announces investment",
        "announced investment",
        
        "invest $",
        "invests $",
        "capital expenditure",
        "capex",
        "spending plan",
        "raises spending",
        "boosts spending",
        "new factory",
        "new plant",
        "expand production",
        "expands production",
        "투자한다",
        "투자 계획",
        "설비투자",
        "증설",
        "공장 건설",
        "생산능력 확대",
    ]

    if contains_any(text, capex_patterns):

        # 향후 투자·증설 전망은 실제 신규 CAPEX 사건이 아니다.
        if has_speculative_context(text):
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "투자·증설 전망이며 실제 확정 CAPEX가 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "CAPEX",
            "reason": "실제 투자·CAPEX·생산능력 변화"
        }
    # "announces $50 billion investment in ..." 같은
    # 실제 투자 발표 문장 처리

    if re.search(
        r"\b(announces|announced|plans|planned|commits|committed)\b"
        r".{0,40}"
        r"\binvestment\b",
        text
    ):

        if has_speculative_context(text):
            return {
                "is_real_event": False,
                "event_type": "NO_EVENT",
                "reason": "투자 전망이며 실제 확정 CAPEX가 아님"
            }

        return {
            "is_real_event": True,
            "event_type": "CAPEX",
            "reason": "실제 투자·CAPEX·생산능력 변화"
        }

    # =====================================================
    # 5. 실적 / 가이던스
    # =====================================================

    earnings_patterns = [
        
        # 영어 실제 실적
        "reports revenue",
        "reported revenue",
        "revenue doubles",
        "revenue rose",
        "revenue rises",
        "revenue increased",
        "profit surge",
        "profit rises",
        "earnings beat",
        "earnings miss",
        "quarterly profit",
        "quarterly revenue",
        "raises guidance",
        "raised guidance",
        "cuts guidance",
        "cut guidance",
        "forecasts annual revenue",
        "revenue above estimates",
        "record revenue",

        # 한국어 - 행동 자체가 명확한 경우
        "흑자전환",
        "흑자 전환",
        "적자전환",
        "적자 전환",
        "실적 발표",
        "가이던스 상향",
        "가이던스 하향",
    ]

    if contains_any(text, earnings_patterns):

        return {
            "is_real_event": True,
            "event_type": "EARNINGS",
            "reason": "실제 실적·가이던스 변화"
        }


    # -----------------------------------------------------
    # 한국어 실제 실적
    #
    # 실적은 반드시 '금액'이 있어야 하는 것이 아니다.
    # 기간 + 실적지표 + 확정된 결과 변화도 실제 실적이다.
    # -----------------------------------------------------

    korean_period = contains_any(
        title,
        [
            "1분기",
            "2분기",
            "3분기",
            "4분기",
            "상반기",
            "하반기",
            "연간",
        ]
    )

    korean_metric = contains_any(
        title,
        [
            "매출",
            "영업이익",
            "순이익",
            "실적",
        ]
    )

    korean_result_change = contains_any(
        title,
        [
            "급증",
            "급감",
            "증가",
            "감소",
            "늘어",
            "줄어",
            "사상 최대",
            "사상 첫",
            "최대 실적",
            "최대 매출",
            "흑자전환",
            "흑자 전환",
            "적자전환",
            "적자 전환",
        ]
    )

    korean_result_number = bool(
        re.search(
            r"(매출(?:액)?|영업이익|순이익)"
            r".{0,25}?"
            r"\d[\d,.]*\s*(억|억원|조|조원|만원|원)",
            title
        )
    )

    korean_result_percent = bool(
        re.search(
            r"(매출(?:액)?|영업이익|순이익)"
            r".{0,25}?"
            r"\d[\d,.]*\s*%",
            title
        )
    )

    if (
        korean_period
        and korean_metric
        and (
            korean_result_change
            or korean_result_number
            or korean_result_percent
        )
    ):
        return {
            "is_real_event": True,
            "event_type": "EARNINGS",
            "reason": "실적 기간과 확정된 실적 변화 확인"
        }


    # =====================================================
    # 6. 생산 / 양산
    # =====================================================

    production_patterns = [
        "mass production",
        "begins production",
        "began production",
        "commercial production",
        "starts production",
        "양산 시작",
        "양산 본격화",
        "상업 생산",
    ]

    if contains_any(text, production_patterns):

        return {
            "is_real_event": True,
            "event_type": "PRODUCTION",
            "reason": "실제 생산·양산 변화"
        }


    # =====================================================
    # 7. 어느 조건에도 해당하지 않으면 사건으로 만들지 않는다.
    # =====================================================

    return {
        "is_real_event": False,
        "event_type": "NO_EVENT",
        "reason": "확인 가능한 실제 행동·변화 없음"
    }
