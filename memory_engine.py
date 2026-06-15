import json
import os
from datetime import datetime

MEMORY_FILE = "data/history.json"


def make_folder():

    if not os.path.exists("data"):
        os.makedirs("data")


def load_memory():

    make_folder()

    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:
        return []


def save_memory(data):

    make_folder()

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )


# --------------------------
# 오늘 추천 저장
# --------------------------

def save_today_result(results):

    history = load_memory()

    history.append({
        "date":
        datetime.now().strftime(
            "%Y-%m-%d"
        ),

        "results":
        results
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

    history = load_memory()

    return {
        "saved_days":
        len(history),

        "saved_themes":
        sum(
            len(day["results"])
            for day in history
        )
    }
