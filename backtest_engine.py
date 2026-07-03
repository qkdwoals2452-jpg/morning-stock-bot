import os
import json
from datetime import datetime

BACKTEST_FILE = "orion_backtest.json"


def load_backtest():
    if not os.path.exists(BACKTEST_FILE):
        return []

    try:
        with open(BACKTEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_backtest(data):
    with open(BACKTEST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_recommendations(final_results):
    data = load_backtest()

    today = datetime.now().strftime("%Y-%m-%d")

    for block in final_results:
        theme_name = block["theme"]["name"]

        for stock in block["ranked"]:
            item = {
                "date": today,
                "theme": theme_name,
                "name": stock["name"],
                "code": stock["code"],
                "score": stock["final_score"],
                "grade": stock["grade"],
                "start_price": stock.get("market", {}).get("close_price"),
                "result_1d": None,
                "result_5d": None,
                "result_10d": None
            }

            data.append(item)

    save_backtest(data)

    print("백테스트 저장 완료:", len(data))
