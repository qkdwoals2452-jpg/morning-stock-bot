import math

SCORE_VERSION = 'evidence_dedup_v2'

HOLDING_COMPANIES = [
    "SK", "LG", "CJ", "GS", "LS", "한화",
    "두산", "HD현대", "롯데지주", "효성",
    "한국앤컴퍼니", "HL홀딩스"
]


def holding_penalty(stock_name):
    if stock_name in HOLDING_COMPANIES:
        return 999
    return 0
def numeric_score(value):
    if isinstance(value, bool):
        return 0
    try:
        result = float(value)
        return result if math.isfinite(result) else 0
    except (TypeError, ValueError):
        return 0


def score_components(finance_score, market_score, verify_score=0, company_score=0,
                     chart_score=0, learning_score=0):
    # 사업 검증/기업카드는 같은 영역의 증거이므로 더 큰 값 하나만 사용한다.
    verified = 20 if numeric_score(verify_score) >= 90 else 10 if numeric_score(verify_score) >= 70 else 0
    return {'finance': numeric_score(finance_score), 'market': numeric_score(market_score),
            'business': max(verified, min(max(numeric_score(company_score), 0), 40)),
            'chart': numeric_score(chart_score), 'learning': numeric_score(learning_score)}

def make_final_score(
    theme_score,
    relation_score,
    finance_score,
    market_score,
    verify_score=0,
    company_score=0,
    chart_score=0,
    learning_score=0,
    impact_score=0
):

    # 기사 빈도·회사명 직접 언급·사건 당사자는 진입/정렬 근거이지 이익의 가산점이 아니다.
    return sum(score_components(finance_score, market_score, verify_score, company_score,
                                chart_score, learning_score).values())

def make_grade(score):

    # 수익 예측력이 검증된 임계값이 생기기 전에는 정렬 점수로 등급을 만들지 않는다.
    return "🧪 검증중"


def safe_score(data):
    if isinstance(data, dict):
        return numeric_score(data.get("score", 0))
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
    learning=None,
    impact=None,
    event_score=None
):

    verify = verify or {}
    company = company or {}
    chart = chart or {}
    learning = learning or {}
    impact = impact or {}
    print("=" * 60)

    print(stock["name"])

    print("theme     :", theme_score)

    print("relation  :", stock["relation_score"])

    print("finance   :", safe_score(finance))

    print("market    :", safe_score(market))

    print("verify    :", safe_score(verify))

    print("company   :", safe_score(company))

    print("chart     :", safe_score(chart))

    print("learning  :", safe_score(learning))
    print("impact    :", safe_score(impact))
    samples = learning.get('sample_count')
    usable_learning = (isinstance(samples, int) and not isinstance(samples, bool) and samples >= 5
                       and learning.get('source') == 'completed_trading_checkpoints')
    learning_points = safe_score(learning) if usable_learning else 0
    components = score_components(safe_score(finance), safe_score(market), safe_score(verify),
                                  safe_score(company), safe_score(chart), learning_points)
    final_score = make_final_score(
        theme_score=theme_score,
        relation_score=stock["relation_score"],
        finance_score=safe_score(finance),
        market_score=safe_score(market),
        verify_score=safe_score(verify),
        company_score=safe_score(company),
        chart_score=safe_score(chart),
        learning_score=learning_points,
        impact_score=safe_score(impact)
    )
    print("FINAL     :", final_score)
    print("SCORE VERSION:", SCORE_VERSION, "COMPONENTS:", components)

    print("=" * 60)

    reason = make_reason(
        theme_score,
        stock["relation_score"],
        finance,
        market
    )
    if event_score is not None:
        reason = [f"사건 신호 {event_score}점"] + [
            item for item in reason
            if item not in {"미국뉴스 키워드 감지", "뉴스 연관"}
        ]

    if verify.get("score", 0) >= 90:
        reason.append("사업내용 검증 우수")
    elif verify.get("score", 0) >= 70:
        reason.append("사업내용 검증 통과")

    if company.get("score", 0) > 0:
        reason.append(company.get("memo", ""))

    if chart.get("score", 0) != 0:
        reason.append(chart.get("memo", ""))

    if learning_points != 0:
        reason.append(learning.get("memo", ""))


    if impact.get("score", 0) != 0:

        reason.append(impact.get("memo", ""))

    return {
        "name": stock["name"],
        "code": stock["code"],
        "sector": stock.get("sector", ""),
        "theme_score": theme_score,
        "event_score": event_score,
        "relation_score": stock["relation_score"],
        "finance": finance,
        "market": market,
        "verify": verify,
        "company": company,
        "chart": chart,
        "learning": learning,
        "impact": impact,
        "final_score": final_score,
        "score_version": SCORE_VERSION,
        "score_breakdown": components,
        "score_excluded": {'article_frequency': numeric_score(theme_score),
                           'direct_mention': numeric_score(stock['relation_score']),
                           'event_relation': safe_score(impact)},
        "score_unit": "heuristic_ranking_points_not_probability",
        "grade_status": "uncalibrated",
        "grade": make_grade(final_score),
        "reason": reason
    }

def sort_results(results):

    return sorted(
        results,
        key=lambda x: x["final_score"],
        reverse=True
    )
