import os
import json
import requests
from datetime import datetime, date

BACKTEST_FILE = "orion_backtest.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def to_float(value):
    """쉼표, %, 문자열이 포함된 숫자를 float로 변환한다."""
    if value is None:
        return None

    try:
        cleaned = str(value).replace(",", "").replace("%", "").strip()
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def normalize_code(code):
    """종목코드를 항상 6자리 문자열로 맞춘다."""
    return str(code or "").strip().zfill(6)


def get_current_price(code):
    """네이버 증권 모바일 API에서 현재가 또는 종가를 가져온다."""
    code = normalize_code(code)

    try:
        url = f"https://m.stock.naver.com/api/stock/{code}/basic"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=5
        )
        response.raise_for_status()

        data = response.json()
        return to_float(data.get("closePrice"))

    except Exception as e:
        print("현재가 조회 실패:", code, e)
        return None


def load_backtest():
    if not os.path.exists(BACKTEST_FILE):
        return []

    try:
        with open(BACKTEST_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, list) else []

    except (json.JSONDecodeError, OSError) as e:
        print("백테스트 파일 읽기 실패:", e)
        return []


def save_backtest(data):
    """파일 저장 중 손상을 줄이기 위해 임시 파일에 먼저 저장한다."""
    temp_file = f"{BACKTEST_FILE}.tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        os.replace(temp_file, BACKTEST_FILE)

    except OSError as e:
        print("백테스트 파일 저장 실패:", e)


def calculate_return(start_price, current_price):
    start_price = to_float(start_price)
    current_price = to_float(current_price)

    if start_price is None or current_price is None:
        return None

    if start_price <= 0:
        return None

    return round(
        (current_price - start_price) / start_price * 100,
        2
    )


def days_since(date_text):
    """추천일로부터 경과한 달력 일수를 계산한다."""
    try:
        start_date = datetime.strptime(
            date_text,
            "%Y-%m-%d"
        ).date()

        return (date.today() - start_date).days

    except (TypeError, ValueError):
        return None


def is_duplicate(data, recommendation_date, theme, code):
    """같은 날, 같은 테마, 같은 종목의 중복 저장을 막는다."""
    code = normalize_code(code)

    for item in data:
        if (
            item.get("date") == recommendation_date
            and item.get("theme") == theme
            and normalize_code(item.get("code")) == code
        ):
            return True

    return False


def save_recommendations(final_results):
    data = load_backtest()

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    recommended_at = now.strftime("%Y-%m-%d %H:%M:%S")

    saved_count = 0
    skipped_count = 0

    for block in final_results:
        theme = block.get("theme", {})
        theme_name = theme.get("name", "미분류")

        ranked_stocks = block.get("ranked", [])

        for rank, stock in enumerate(ranked_stocks, start=1):
            name = stock.get("name")
            code = normalize_code(stock.get("code"))

            if not name or not code:
                continue

            if is_duplicate(data, today, theme_name, code):
                skipped_count += 1
                continue

            market = stock.get("market") or {}

            start_price = (
                market.get("close_price")
                or market.get("current_price")
                or stock.get("price")
                or stock.get("close")
                or stock.get("current")
            )

            start_price = to_float(start_price)

            # 전달받은 가격이 없으면 네이버 현재가로 보완
            if start_price is None:
                start_price = get_current_price(code)

            score_breakdown = (
                stock.get("score_breakdown")
                or stock.get("score_detail")
                or {}
            )

            item = {
                "date": today,
                "recommended_at": recommended_at,
                "theme": theme_name,
                "theme_score": theme.get("score"),
                "rank": rank,
                "name": name,
                "code": code,
                "score": stock.get("final_score"),
                "grade": stock.get("grade"),
                "reasons": stock.get("reasons", []),
                "score_breakdown": score_breakdown,

                "start_price": start_price,
                "current_price": start_price,
                "current_return": 0.0 if start_price else None,

                "highest_price": start_price,
                "highest_return": 0.0 if start_price else None,

                "lowest_price": start_price,
                "max_drawdown": 0.0 if start_price else None,

                "result_1d": None,
                "result_3d": None,
                "result_5d": None,
                "result_10d": None,
                "result_20d": None,

                "price_history": [],
                "last_updated": None
            }

            data.append(item)
            saved_count += 1

    save_backtest(data)

    print(
        f"백테스트 추천 저장 완료: "
        f"신규 {saved_count}건 / 중복 제외 {skipped_count}건 / "
        f"누적 {len(data)}건"
    )


def update_result_by_day(item, elapsed_days, current_return):
    """경과 일수에 따라 해당 시점의 수익률을 한 번만 기록한다."""
    checkpoints = {
        1: "result_1d",
        3: "result_3d",
        5: "result_5d",
        10: "result_10d",
        20: "result_20d"
    }

    for target_day, field_name in checkpoints.items():
        if (
            elapsed_days >= target_day
            and item.get(field_name) is None
        ):
            item[field_name] = current_return


def update_single_item(item, current_price, update_date):
    start_price = to_float(item.get("start_price"))
    current_price = to_float(current_price)

    if start_price is None or current_price is None:
        return False

    if start_price <= 0 or current_price <= 0:
        return False

    current_return = calculate_return(
        start_price,
        current_price
    )

    item["current_price"] = current_price
    item["current_return"] = current_return
    item["last_updated"] = update_date

    highest_price = to_float(item.get("highest_price"))

    if highest_price is None or current_price > highest_price:
        item["highest_price"] = current_price
        item["highest_return"] = current_return

    lowest_price = to_float(item.get("lowest_price"))

    if lowest_price is None or current_price < lowest_price:
        item["lowest_price"] = current_price
        item["max_drawdown"] = current_return

    history = item.setdefault("price_history", [])

    # 같은 날짜의 가격 기록 중복 방지
    already_saved = any(
        row.get("date") == update_date
        for row in history
    )

    if not already_saved:
        history.append({
            "date": update_date,
            "price": current_price,
            "return": current_return
        })

    elapsed_days = days_since(item.get("date"))

    if elapsed_days is not None:
        update_result_by_day(
            item,
            elapsed_days,
            current_return
        )

    return True


def update_backtest_prices(stocks=None):
    """
    추천 종목 가격을 업데이트한다.

    stocks가 전달되면 전달된 가격을 우선 사용하고,
    없거나 가격이 빠진 종목은 네이버 현재가를 조회한다.
    """
    data = load_backtest()

    if not data:
        print("백테스트 업데이트 대상 없음")
        return

    price_map = {}

    if stocks:
        for stock in stocks:
            code = normalize_code(stock.get("code"))

            price = (
                stock.get("price")
                or stock.get("close")
                or stock.get("current")
                or stock.get("current_price")
            )

            price = to_float(price)

            if code and price is not None:
                price_map[code] = price

    update_date = datetime.now().strftime("%Y-%m-%d")
    updated_count = 0
    failed_count = 0

    for item in data:
        code = normalize_code(item.get("code"))

        current_price = price_map.get(code)

        if current_price is None:
            current_price = get_current_price(code)

        if current_price is None:
            failed_count += 1
            continue

        updated = update_single_item(
            item,
            current_price,
            update_date
        )

        if updated:
            updated_count += 1
        else:
            failed_count += 1

    save_backtest(data)

    print(
        f"백테스트 가격 업데이트 완료: "
        f"성공 {updated_count}건 / 실패 {failed_count}건"
    )


def print_backtest_summary():
    """현재 저장된 백테스트 결과를 간단히 출력한다."""
    data = load_backtest()

    if not data:
        print("백테스트 데이터 없음")
        return

    valid_returns = [
        item.get("current_return")
        for item in data
        if isinstance(item.get("current_return"), (int, float))
    ]

    winners = [
        value for value in valid_returns
        if value > 0
    ]

    losers = [
        value for value in valid_returns
        if value < 0
    ]

    win_rate = (
        round(len(winners) / len(valid_returns) * 100, 2)
        if valid_returns
        else 0
    )

    average_return = (
        round(sum(valid_returns) / len(valid_returns), 2)
        if valid_returns
        else 0
    )

    print("━━━━━━━━━━━━━━━━━━━━")
    print("📊 ORION 백테스트 현황")
    print("전체 추천:", len(data))
    print("수익 종목:", len(winners))
    print("손실 종목:", len(losers))
    print("승률:", f"{win_rate}%")
    print("평균 수익률:", f"{average_return}%")
    print("━━━━━━━━━━━━━━━━━━━━")
