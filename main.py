from config import *
from news_engine import get_all_news
from theme_engine import extract_themes
from stock_engine import load_korean_stocks, find_related_stocks
from finance_engine import get_finance_score
from market_engine import get_market_score
from scoring_engine import make_stock_result, sort_results, make_grade
from memory_engine import save_today_result, get_project_status
from memory_learning_engine import get_learning_score, save_prediction
from telegram_bot import send_telegram


def run():
    stocks = load_korean_stocks()
    news = get_all_news()
    themes = extract_themes(news)

    final_results = []

    for theme in themes[:TOP_THEME_COUNT]:

        if theme["score"] < MIN_THEME_SCORE:
            continue

        candidates = find_related_stocks(
            theme,
            stocks,
            news
        )

        ranked = []

        for stock in candidates:

            finance = get_finance_score(stock)
            market = get_market_score(stock)
            learning = get_learning_score(stock["name"])

            result = make_stock_result(
                stock=stock,
                theme_score=theme["score"],
                finance=finance,
                market=market
            )

            result["final_score"] += learning["score"]
            result["grade"] = make_grade(result["final_score"])

            if learning["score"] != 0:
                result["reason"].append(learning["memo"])

            result["learning"] = learning

            ranked.append(result)

        ranked = sort_results(ranked)

        if not ranked:
            continue

        top_ranked = ranked[:TOP_STOCK_COUNT]

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
