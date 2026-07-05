import os
import json
import requests
from datetime import datetime

BACKTEST_FILE = "orion_backtest.json"

HEADERS = {

    "User-Agent": "Mozilla/5.0"

}

def to_float(value):

    try:

        return float(str(value).replace(",", "").replace("%", ""))

    except:

        return None

def get_current_price(code):

    try:

        url = f"https://m.stock.naver.com/api/stock/{code}/basic"

        res = requests.get(

            url,

            headers=HEADERS,

            timeout=5

        )

        data = res.json()

        price = data.get("closePrice")

        return to_float(price)

    except Exception as e:

        print("현재가 조회 실패:", code, e)

        return None
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
def update_backtest_prices(stocks):
    data = load_backtest()

    if not data:
        print("백테스트 업데이트 대상 없음")
        return

    price_map = {}

    for stock in stocks:
        code = str(stock.get("code", "")).zfill(6)
        price = stock.get("price") or stock.get("close") or stock.get("current")

        if price is not None:
            price_map[code] = price

    updated = 0

    for item in data:
        code = str(item.get("code", "")).zfill(6)
        start_price = item.get("start_price")
        current_price = price_map.get(code)

        if start_price is None or current_price is None:
            continue

        try:
            start_price = float(start_price)
            current_price = float(current_price)

            if start_price <= 0:
                continue

            rate = round((current_price - start_price) / start_price * 100, 2)

            item["current_price"] = current_price
            item["current_return"] = rate

            updated += 1

        except:
            continue

    save_backtest(data)

    print("백테스트 가격 업데이트 완료:", updated)
