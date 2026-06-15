def make_final_score(
    theme_score,
    relation_score,
    finance_score,
    market_score
):

    score = 0

    # ------------------
    # 미국/국내 뉴스
    # ------------------

    score += theme_score

    # ------------------
    # 관련도
    # ------------------

    score += relation_score * 3

    # ------------------
    # 재무
    # ------------------

    score += finance_score

    # ------------------
    # 시장반응
    # ------------------

    score += market_score

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


def make_reason(
    theme_score,
    relation_score,
    finance,
    market
):

    reason = []

    # ------------------
    # 뉴스
    # ------------------

    if theme_score >= 15:
        reason.append("미국뉴스 강한 연관")

    elif theme_score >= 8:
        reason.append("뉴스 연관")

    # ------------------
    # 관련도
    # ------------------

    if relation_score >= 15:
        reason.append("사업영역 일치")

    elif relation_score >= 8:
        reason.append("관련주 가능성")

    # ------------------
    # 재무
    # ------------------

    if finance["score"] >= 20:
        reason.append("재무 우수")

    elif finance["score"] >= 10:
        reason.append("재무 양호")

    # ------------------
    # 시장
    # ------------------

    if market["score"] >= 20:
        reason.append("거래대금 증가")

    elif market["score"] >= 10:
        reason.append("시장 반응")

    return reason


def make_stock_result(
    stock,
    theme_score,
    finance,
    market
):

    final_score = make_final_score(
        theme_score=theme_score,
        relation_score=stock["relation_score"],
        finance_score=finance["score"],
        market_score=market["score"]
    )

    return {
        "name": stock["name"],
        "code": stock["code"],
        "sector": stock.get("sector", ""),

        "theme_score": theme_score,
        "relation_score": stock["relation_score"],

        "finance": finance,
        "market": market,

        "final_score": final_score,

        "grade": make_grade(
            final_score
        ),

        "reason": make_reason(
            theme_score,
            stock["relation_score"],
            finance,
            market
        )
    }


def sort_results(results):

    return sorted(
        results,
        key=lambda x: x["final_score"],
        reverse=True
    )
