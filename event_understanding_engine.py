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


def understand_event(article):

    title = normalize_text(
        article.get("title", "")
    )

    summary = normalize_text(
        article.get("summary", "")
    )

    text = f"{title} {summary}".strip()


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

    # =====================================================
    # 2. FOMC / 미국 금리 결정
    # =====================================================

    fomc_patterns = [
        "federal reserve cuts interest rates",
        "federal reserve raises interest rates",
        "fed cuts interest rates",
        "fed raises interest rates",
        "cuts interest rates by",
        "raises interest rates by",
        "rate cut",
        "rate hike",
        "interest rate decision",
        "기준금리 인하",
        "기준금리 인상",
        "연준 금리 인하",
        "연준 금리 인상",
        "연방준비제도 금리 인하",
        "연방준비제도 금리 인상",
        
    ]

    if contains_any(text, fomc_patterns):

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

        return {
            "is_real_event": True,
            "event_type": "POLICY",
            "reason": "실제 정부 정책·관세·수출규제 변화"
        }
    # =====================================================
    # 2. M&A
    # =====================================================

    ma_patterns = [
        "agrees to buy",
        "agreed to buy",
        "agrees to acquire",
        "agreed to acquire",
        "acquires",
        "acquired",
        "acquisition",
        "completes acquisition",
        "completed acquisition",
        "merger completed",
        "merger approved",
        "인수한다",
        "인수 완료",
        "인수 계약",
        "합병 결의",
        "합병 승인",
        "합병 완료",
    ]

    if contains_any(text, ma_patterns):

        return {
            "is_real_event": True,
            "event_type": "M&A",
            "reason": "실제 인수·합병 사건"
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


    # 한국어 매출/이익 기사는 실제 숫자가 있을 때만 실적으로 인정
    korean_earnings_number = re.search(
        r"(매출(?:액)?|영업이익|순이익)"
        r".{0,20}?"
        r"\d[\d,.]*\s*(억|조|만원|원|%)",
        text
    )

    if korean_earnings_number:

        return {
            "is_real_event": True,
            "event_type": "EARNINGS",
            "reason": "실제 실적 수치 확인"
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
