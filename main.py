import os
import build_corp_db
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
from backtest_engine import save_recommendations, update_backtest_prices
from memory_learning_engine import get_learning_score, save_prediction
from telegram_bot import send_telegram


def run():
    if not os.path.exists("corp_code.csv"):
        print("corp_code.csv 없음 → DART 기업코드 생성")
        build_corp_db

    stocks = load_korean_stocks()
    update_backtest_prices(stocks)
    news = get_all_news()
    themes = extract_themes(news)

    print("뉴스 개수:", len(news))
    print("테마 개수:", len(themes))
    # print(themes[:5])

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
            # AI 업종 필터

            if theme["name"] == "AI":

                text = (

                      str(company.get("matched", {})) +

                      stock.get("name", "")

                )

                allow_words = [

                    "반도체", "HBM", "AI", "서버", "GPU",

                    "데이터센터", "메모리", "전력",

                    "네트워크", "보안", "장비"

                ]

                if not any(word in text for word in allow_words):

                    print("제외:", stock["name"], "AI 업종 부적합")

                    continue
            print("==========")
            print(stock["name"])
            print("verify:", verify)
            print("company:", company)
            print("finance:", finance)
            print("market:", market)
            print("chart:", chart)
            # 추천 제외 필터

            if finance.get("exclude") == True:

                print("제외:", stock["name"], finance.get("exclude_reason"))

                continue
            if company.get("exclude") == True:
                print("제외:", stock["name"], company.get("exclude_reason"))
                continue
            

            if chart.get("details", {}).get("high_52w_gap") is not None:

                if chart["details"]["high_52w_gap"] <= -60:

                    print("제외:", stock["name"], "52주 고점 대비 -60% 이하")

                    continue

            if chart.get("details", {}).get("ma120") is not None:

                current = chart["details"].get("current")

                ma120 = chart["details"].get("ma120")

                if current is not None and current < ma120:

                    print("제외:", stock["name"], "120일선 아래")

                    continue

            if market.get("trading_value") is None:
                print("거래대금 없음:", stock["name"])
            else:
                if market["trading_value"] < 30_0000_0000:
                    print("제외:", stock["name"], "거래대금 30억 미만")
                    continue
            result = make_stock_result(
                stock=stock,
                theme_score=theme["score"],
                finance=finance,
                market=market,
                verify=verify,
                company=company,
                chart=chart,
                learning=learning
            )
            # 대형주/지주사는 TOP 추천에서 감점
            mega_caps = [
                "삼성전자",
                "SK하이닉스",
                "SK",
                "SK스퀘어"
            ]

            if stock["name"] in mega_caps:
                

                print("참고용:", stock["name"], "대형주/지주사")

                 
                continue
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
    save_recommendations(final_results)
    update_backtest_prices(stocks)
    project_status = get_project_status()

    send_telegram(
        final_results,
        project_status
    )


if __name__ == "__main__":
    run()
