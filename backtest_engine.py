import os
import json
import requests
import math
import copy
from datetime import datetime, date, timedelta, time
from zoneinfo import ZoneInfo
from performance_validation_engine import completed_performance

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
        number = float(cleaned)
        return number if math.isfinite(number) else None
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

    now = datetime.now(ZoneInfo("Asia/Seoul"))
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

            if not name or len(code) != 6 or not code.isdigit() or code == "000000":
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
            if start_price is None or start_price <= 0:
                start_price = get_current_price(code)
            if start_price is not None and start_price <= 0:
                start_price = None

            score_breakdown = (
                stock.get("score_breakdown")
                or stock.get("score_detail")
                or {}
            )

            item = {
                "date": today,
                "recommended_at": recommended_at,
                "date_timezone": "Asia/Seoul",
                "theme": theme_name,
                "theme_score": theme.get("score"),
                "rank": rank,
                "name": name,
                "code": code,
                "score": stock.get("final_score"),
                "grade": stock.get("grade"),
                "event_score": stock.get("event_score"),
                "frequency_score": theme.get("frequency_score"),
                "reasons": stock.get("reasons") or stock.get("reason") or [],
                "score_breakdown": score_breakdown,
                "score_version": stock.get("score_version", "legacy_unversioned"),
                "grade_status": stock.get("grade_status", "legacy_unvalidated"),

                "start_price": start_price,
                "return_basis": "reference_price_only",
                "reference_price_status": "available" if start_price is not None else "unavailable",
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

            if isinstance(stock.get("pre_news_activity"), dict):
                item["pre_news_activity"] = copy.deepcopy(stock["pre_news_activity"])
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

    # 관측한 현재가를 과거 1/3/5/10/20일 종가로 기록하지 않는다.
    # 거래일별 수익률은 확인된 과거 종가로만 별도 계산한다.

    return True


def last_completed_date(now=None):
    now = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if now.tzinfo is not None:
        now = now.astimezone(ZoneInfo("Asia/Seoul"))
    return now.date() if now.time() >= time(15, 30) else now.date() - timedelta(days=1)


def fill_trading_checkpoints(item, daily_closes, as_of=None):
    """추천일 다음의 실제 거래일 종가로 D+1/3/5/10/20을 계산한다."""
    start = to_float(item.get("start_price"))
    try:
        recommended = date.fromisoformat(item.get("date", ""))
        cutoff = date.fromisoformat(as_of) if as_of else last_completed_date()
    except (TypeError, ValueError):
        return 0
    if start is None or start <= 0 or recommended > cutoff:
        return 0

    fields = [f"result_{n}d" for n in (1, 3, 5, 10, 20)]
    if item.get("checkpoint_method") != "trading_sessions_v1":
        legacy = {field: item.get(field) for field in fields if item.get(field) is not None}
        if legacy:
            item.setdefault("legacy_calendar_checkpoints", legacy)
        for field in fields:
            item[field] = None
        item["checkpoint_method"] = "trading_sessions_v1"

    prices = {}
    for day, value in daily_closes:
        try:
            day = date.fromisoformat(day)
        except (TypeError, ValueError):
            continue
        if day > cutoff:
            continue
        price = to_float(value)
        price = price if price is not None and price > 0 else None
        # 같은 날짜에 서로 다른 가격이 오면 그 날짜는 검증 보류한다.
        if day in prices and prices[day] != price:
            prices[day] = None
        else:
            prices[day] = price
    # 조회 범위가 추천일을 포함하지 않으면 N번째 거래일을 셀 수 없다.
    if not any(day <= recommended for day in prices):
        item["checkpoint_status"] = "history_unavailable"
        return 0

    later = sorted((day, price) for day, price in prices.items() if day > recommended)
    filled = 0
    dates = item.setdefault("checkpoint_dates", {})
    for n in (1, 3, 5, 10, 20):
        field = f"result_{n}d"
        if item.get(field) is None and len(later) >= n:
            day, price = later[n - 1]
            if price is not None:
                item[field] = calculate_return(start, price)
                dates[field] = day.isoformat()
                item.setdefault('checkpoint_observed_at', {})[field] = datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
                filled += 1
    item["checkpoint_status"] = "complete" if all(item.get(field) is not None for field in fields) else "pending"
    return filled


def fetch_daily_closes(code, start_date=None, as_of=None):
    """날짜가 있는 과거 종가를 조회하며 미완료 거래일은 제외한다."""
    code = normalize_code(code)
    if len(code) != 6 or not code.isdigit() or code == "000000":
        return []
    try:
        cutoff = date.fromisoformat(as_of) if as_of else last_completed_date()
        anchor = date.fromisoformat(start_date) if start_date else cutoff - timedelta(days=100)
    except (TypeError, ValueError):
        return []
    begin = anchor - timedelta(days=14)
    try:
        response = requests.get(
            f"https://api.stock.naver.com/chart/domestic/item/{code}/day",
            params={"startDateTime": begin.strftime("%Y%m%d"),
                    "endDateTime": cutoff.strftime("%Y%m%d")},
            headers=HEADERS, timeout=8,
        )
        response.raise_for_status()
        raw = response.json()
        if isinstance(raw, list):
            rows = []
            for row in raw:
                try:
                    day = datetime.strptime(row.get("localDate", ""), "%Y%m%d").date()
                except (TypeError, ValueError):
                    continue
                if begin <= day <= cutoff:
                    rows.append((day.isoformat(), to_float(row.get("closePrice"))))
            if rows and (start_date is None or min(day for day, _ in rows) <= anchor.isoformat()):
                return sorted(rows)
    except (requests.RequestException, ValueError, TypeError) as exc:
        print("과거 종가 조회 실패:", code, "NAVER", type(exc).__name__)

    # 기존 검토 브랜치의 Yahoo 조회는 보조 경로로 유지한다.
    begin_ts = int(datetime.combine(begin, time.min, ZoneInfo("Asia/Seoul")).timestamp())
    end_ts = int(datetime.combine(cutoff + timedelta(days=1), time.min, ZoneInfo("Asia/Seoul")).timestamp())
    for suffix in (".KS", ".KQ"):
        try:
            response = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/" + code + suffix,
                params={"period1": begin_ts, "period2": end_ts, "interval": "1d"},
                headers=HEADERS, timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                continue
            results = payload.get("chart", {}).get("result") or []
            if not results:
                continue
            data = results[0]
            quote = data.get("indicators", {}).get("quote") or []
            closes = quote[0].get("close") if quote else []
            rows = []
            for stamp, value in zip(data.get("timestamp") or [], closes or []):
                day = datetime.fromtimestamp(stamp, ZoneInfo("Asia/Seoul")).date()
                if begin <= day <= cutoff:
                    rows.append((day.isoformat(), to_float(value)))
            if rows and (start_date is None or min(day for day, _ in rows) <= anchor.isoformat()):
                return sorted(rows)
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            print("과거 종가 조회 실패:", code, suffix, type(exc).__name__)
    return []


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

    update_date = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    updated_count = 0
    failed_count = 0

    for item in data:
        code = normalize_code(item.get("code"))

        if code not in price_map:
            price_map[code] = get_current_price(code)
        current_price = price_map[code]

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

    pending = [item for item in data
               if item.get("checkpoint_method") != "trading_sessions_v1"
               or any(item.get(f"result_{n}d") is None for n in (1, 3, 5, 10, 20))]
    earliest = {}
    for item in pending:
        try:
            day = date.fromisoformat(item.get("date", "")).isoformat()
        except (TypeError, ValueError):
            continue
        code = normalize_code(item.get("code"))
        earliest[code] = min(earliest.get(code, day), day)
    history_cache = {code: fetch_daily_closes(code, day) for code, day in earliest.items()}
    checkpoint_count = 0
    for item in pending:
        checkpoint_count += fill_trading_checkpoints(
            item, history_cache.get(normalize_code(item.get("code")), [])
        )
    save_backtest(data)
    print("거래일 기준 평가 저장:", checkpoint_count, "건")

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

    report = completed_performance(data)

    print("━━━━━━━━━━━━━━━━━━━━")
    print("📊 ORION 백테스트 현황")
    print("전체 추천:", len(data))
    print("평가 기준: 완료된 D+5 기준가 성과(비용 미포함)")
    print("검증 표본:", report['count'])
    print("수익 표본:", report.get('winners', 0))
    print("손실 표본:", report.get('losers', 0))
    print("승률:", f"{report['accuracy']}%" if report['count'] else "미확인(완료·확인 시점 근거 없음)")
    print("평균 수익률:", f"{report['average']}%" if report['count'] else "미확인")
    print("집계 제외:", report['excluded'])
    print("━━━━━━━━━━━━━━━━━━━━")
