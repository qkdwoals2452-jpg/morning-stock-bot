HOLDING_COMPANIES = [
    "SK", "LG", "CJ", "GS", "LS", "한화",
    "두산", "HD현대", "롯데지주", "효성",
    "한국앤컴퍼니", "HL홀딩스"
]


def holding_penalty(stock_name):
    if stock_name in HOLDING_COMPANIES:
        return 999
    return 0
def safe_score(data):
    if isinstance(data, dict):
        return data.get("score", 0) or 0
    return 0
    
def make_final_score(
    theme_score,
    relation_score,
    finance_score,
    market_score,
    verify_score=0,
    company_score=0,
    chart_score=0,
    learning_score=0
):

    score = 0

    score += theme_score
    score += relation_score * 3
    score += finance_score
    score += market_score

    if verify_score >= 90:
        score += 20
    elif verify_score >= 70:
        score += 10

    score += min(company_score, 40)
    score += chart_score
    score += learning_score

    return score

def make_grade(score):

    if score >= 95:
        return "💎 S+"

    elif score >= 90:
        return "🏆 S"

    elif score >= 80:
        return "🥇 A"

    elif score >= 70:
        return "🥈 B"

    elif score >= 60:
        return "🥉 C"

    return "⚠️ 관심"


def safe_score(data):
    if isinstance(data, dict):
        return data.get("score", 0) or 0
    return 0


def make_reason(
    theme_score,
    relation_score,
    finance,
    market
):

    reason = []

    finance_score = safe_score(finance)
    market_score = safe_score(market)

    if theme_score >= 15:
        reason.append("미국뉴스 키워드 감지")
    elif theme_score >= 8:
        reason.append("뉴스 연관")

    if relation_score >= 15:
        reason.append("사업영역 후보")
    elif relation_score >= 8:
        reason.append("관련주 가능성")

    if finance_score >= 20:
        reason.append("재무 우수")
    elif finance_score >= 10:
        reason.append("재무 양호")

    if market_score >= 20:
        reason.append("시장 반응 확인")
    elif market_score >= 10:
        reason.append("시장 반응")

    return reason

def make_stock_result(
    stock,
    theme_score,
    finance,
    market,
    verify=None,
    company=None,
    chart=None,
    learning=None
):

    verify = verify or {}
    company = company or {}
    chart = chart or {}
    learning = learning or {}

    final_score = make_final_score(
        theme_score=theme_score,
        relation_score=stock["relation_score"],
        finance_score=safe_score(finance),
        market_score=safe_score(market),
        verify_score=safe_score(verify),
        company_score=safe_score(company),
        chart_score=safe_score(chart),
        learning_score=safe_score(learning)
    )

    reason = make_reason(
        theme_score,
        stock["relation_score"],
        finance,
        market
    )

    if verify.get("score", 0) >= 90:
        reason.append("사업내용 검증 우수")
    elif verify.get("score", 0) >= 70:
        reason.append("사업내용 검증 통과")

    if company.get("score", 0) > 0:
        reason.append(company.get("memo", ""))

    if chart.get("score", 0) != 0:
        reason.append(chart.get("memo", ""))

    if learning.get("score", 0) != 0:
        reason.append(learning.get("memo", ""))

    return {
        "name": stock["name"],
        "code": stock["code"],
        "sector": stock.get("sector", ""),
        "theme_score": theme_score,
        "relation_score": stock["relation_score"],
        "finance": finance,
        "market": market,
        "verify": verify,
        "company": company,
        "chart": chart,
        "learning": learning,
        "final_score": final_score,
        "grade": make_grade(final_score),
        "reason": reason
    }

def sort_results(results):

    return sorted(
        results,
        key=lambda x: x["final_score"],
        reverse=True
    )
