import json
import os
from copy import deepcopy
from datetime import datetime, date
from zoneinfo import ZoneInfo

MEMORY_FILE = "data/history.json"


def make_folder():

    if not os.path.exists("data"):
        os.makedirs("data")


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)
        if not isinstance(data, list) or any(not isinstance(row, dict)
                or not isinstance(row.get('results'), list) for row in data):
            raise ValueError('invalid history schema')
        if any(not isinstance(block, dict) or not isinstance(block.get('theme'), dict)
               or not isinstance(block.get('ranked'), list)
               or any(not isinstance(stock, dict) for stock in block['ranked'])
               for row in data for block in row['results']):
            raise ValueError('invalid recommendation schema')
        return data
    except (OSError, ValueError) as exc:
        # 손상된 파일을 빈 이력으로 덮어쓰지 않는다.
        raise RuntimeError('표시용 이력 읽기 실패: ' + type(exc).__name__) from None


def save_memory(data):
    make_folder()
    temporary = MEMORY_FILE + '.tmp'
    with open(
        temporary,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )
    os.replace(temporary, MEMORY_FILE)


# --------------------------
# 오늘 추천 저장
# --------------------------

def save_today_result(results):
    history = load_memory()
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    today = now.date().isoformat()
    existing = {(block.get('theme', {}).get('name'), stock.get('code'))
                for day in history if day.get('date') == today
                for block in day['results'] for stock in block.get('ranked', [])}
    incoming = {(block.get('theme', {}).get('name'), stock.get('code'))
                for block in results for stock in block.get('ranked', [])}
    # 같은 날 동일 후보 재실행은 중복 저장하지 않고 과거 결과도 삭제하지 않는다.
    if any(day.get('date') == today for day in history) and incoming.issubset(existing):
        return
    new_results = []
    for block in results:
        copied = deepcopy(block)
        copied['ranked'] = []
        for stock in block.get('ranked', []):
            key = (block.get('theme', {}).get('name'), stock.get('code'))
            if key not in existing:
                copied['ranked'].append(deepcopy(stock))
                existing.add(key)
        if copied['ranked']:
            new_results.append(copied)
    history.append({
        'date': today, 'recorded_at': now.isoformat(), 'date_timezone': 'Asia/Seoul',
        'results': new_results
    })

    save_memory(history)


# --------------------------
# 과거 유사테마 검색
# --------------------------

def search_theme_history(
    theme_name
):

    history = load_memory()

    found = []

    for day in history:

        for item in day["results"]:

            if item["theme"]["name"] == theme_name:

                found.append(item)

    return found


# --------------------------
# 종목 등장횟수
# --------------------------

def get_stock_frequency(
    stock_name
):

    history = load_memory()

    count = 0

    for day in history:

        for item in day["results"]:

            for stock in item["ranked"]:

                if stock["name"] == stock_name:
                    count += 1

    return count


# --------------------------
# AI 학습 점수
# --------------------------

def get_memory_score(
    stock_name
):

    count = get_stock_frequency(
        stock_name
    )

    score = 0

    memo = ""

    if count >= 20:

        score = 20
        memo = "과거 자주 등장"

    elif count >= 10:

        score = 10
        memo = "과거 반복 등장"

    elif count >= 5:

        score = 5
        memo = "과거 이력 존재"

    else:

        score = 0
        memo = "신규"

    return {
        "score": score,
        "memo": memo
    }


# --------------------------
# 테마 적중률
# --------------------------

def get_theme_count(
    theme_name
):

    history = load_memory()

    total = 0

    for day in history:

        for item in day["results"]:

            if item["theme"]["name"] == theme_name:
                total += 1

    return total


# --------------------------
# 최근 추천 보기
# --------------------------

def get_recent_result(
    limit=5
):

    history = load_memory()

    return history[-limit:]


# --------------------------
# 프로젝트 통계
# --------------------------

def get_project_status():
    from backtest_engine import load_backtest
    history = load_memory()
    days, themes = set(), set()
    def valid_day(value):
        try:
            return date.fromisoformat(value).isoformat()
        except (TypeError, ValueError):
            return None
    for row in history:
        day = valid_day(row.get('date'))
        if not day:
            continue
        days.add(day)
        for block in row['results']:
            name = block.get('theme', {}).get('name')
            if name and block.get('ranked'):
                themes.add((day, name))
    # 사라진 실행 일자를 추측하지 않는다. 보존된 추천일만 표시 통계에 합친다.
    backtest_days = set()
    for row in load_backtest():
        if not isinstance(row, dict):
            continue
        day = valid_day(row.get('date'))
        if day and row.get('theme') and row.get('code'):
            backtest_days.add(day)
            themes.add((day, row['theme']))
    days.update(backtest_days)
    return {'saved_days': len(days), 'saved_themes': len(themes),
            'count_basis': 'distinct_recorded_dates_and_date_theme_pairs',
            'known_dates': sorted(days), 'continuous_history_confirmed': False}
