from company_verify_engine import verify_company_theme
from config import *
from news_engine import get_all_news
from theme_engine import extract_themes, expand_theme_words
from stock_engine import load_korean_stocks, find_related_stocks
from company_engine import get_company_match_score
from finance_engine import get_finance_score
from market_engine import get_market_score
from chart_engine import get_chart_score
from scoring_engine import make_stock_result, sort_results, make_grade
from memory_engine import save_today_result, get_project_status
from memory_learning_engine import get_learning_score, save_prediction
from telegram_bot import send_telegram


def run():
    stocks = load_korean_stocks()
    news = get_all_news()
    themes = extract_themes(news)

    print("뉴스 개수:", len(news))
    print("테마 개수:", len(themes))
    print(themes[:5])

    final_results = []
    themes = themes[:TOP_THEME_COUNT]
    print("실제 분석 테마 수:", len(themes))
    
    for theme in themes:
        if theme["score"] < MIN_THEME_SCORE:
            continue

        candidates = find_related_stocks(
            theme,
            stocks,
            news
        )
        candidates = candidates[:10]
        print("실제 정밀분석 종목 수:", len(candidates))
        theme_words = expand_theme_words(
            theme["name"]
        )

        ranked = []

        for stock in candidates:
            if stock["name"] in ["SG"]:
                continue
            verify = verify_company_theme(stock, theme["name"])

            if not verify["pass"]:
                continue

            finance = get_finance_score(stock)
           # if finance.get("exclude"):
           #     continue
            market = get_market_score(stock)
            chart = get_chart_score(stock)
            learning = get_learning_score(stock["name"])
            company = get_company_match_score(stock, theme_words)

            result = make_stock_result(
                stock=stock,
                theme_score=theme["score"],
                finance=finance,
                market=market
            )
            result["verify"] = verify
            if verify["score"] >= 90:

                result["final_score"] += 20

                result["reason"].append("사업내용 검증 우수")

            elif verify["score"] >= 70:

                result["final_score"] += 10

                result["reason"].append("사업내용 검증 통과")
            # 사업내용 점수
            result["final_score"] += min(company["score"], 20)
            result["company"] = company

            if company["score"] > 0:
                result["reason"].append(company["memo"])

            # 차트 점수
            result["final_score"] += chart["score"]
            result["chart"] = chart

            if chart["score"] != 0:
                result["reason"].append(chart["memo"])

            # 과거 학습 점수
            result["final_score"] += learning["score"]
            result["learning"] = learning

            if learning["score"] != 0:
                result["reason"].append(learning["memo"])

            # 최종 등급 재계산
            result["grade"] = make_grade(
                result["final_score"]
            )

            ranked.append(result)

        ranked = sort_results(ranked)

        if not ranked:
            continue

        top_ranked = ranked[:TOP_STOCK_COUNT]
        print(
            "추가됨:",
            theme["name"],
            "종목수:",
            len(top_ranked)
        )
        final_results.append({
            "theme": theme,
            "ranked": top_ranked
        })

        for stock in top_ranked:
            save_prediction(
                theme["name"],
                stock["name"],
                stock["final_score"]
            )

    save_today_result(final_results)

    project_status = get_project_status()

    send_telegram(
        final_results,
        project_status
    )


if __name__ == "__main__":
    run()
