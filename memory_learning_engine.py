import json
import os

RESULT_FILE = "data/performance.json"


def make_folder():

    if not os.path.exists("data"):
        os.makedirs("data")


def load_result():

    make_folder()

    if not os.path.exists(
        RESULT_FILE
    ):
        return []

    try:

        with open(
            RESULT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return []


def save_result(data):

    make_folder()

    with open(
        RESULT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )


# --------------------
# 추천결과 저장
# --------------------

def save_prediction(
    theme,
    stock,
    final_score
):

    history = load_result()

    history.append({

        "theme": theme,

        "stock": stock,

        "score": final_score,

        "result": None

    })

    save_result(history)


# --------------------
# 실제 결과 입력
# --------------------

def update_result(
    stock,
    change_rate
):

    history = load_result()

    for item in history:

        if (
            item["stock"]
            == stock
        ):

            if (
                item["result"]
                is None
            ):

                item["result"] = (
                    change_rate
                )

                break

    save_result(
        history
    )


# --------------------
# AI 가중치
# --------------------

def get_learning_score(
    stock
):

    history = load_result()

    total = 0

    count = 0

    for item in history:

        if (
            item["stock"]
            == stock
        ):

            if (
                item["result"]
                is not None
            ):

                total += (
                    item["result"]
                )

                count += 1

    if count == 0:

        return {
            "score": 0,
            "memo": "학습없음"
        }

    avg = (
        total / count
    )

    if avg >= 10:

        return {
            "score": 20,
            "memo": "과거 강세"
        }

    elif avg >= 5:

        return {
            "score": 10,
            "memo": "과거 상승"
        }

    elif avg >= 0:

        return {
            "score": 3,
            "memo": "보통"
        }

    return {
        "score": -10,
        "memo": "과거 약세"
    }


# --------------------
# 프로젝트 성적표
# --------------------

def get_project_report():

    history = load_result()

    success = 0

    fail = 0

    total_return = 0

    count = 0

    for item in history:

        if (
            item["result"]
            is None
        ):

            continue

        count += 1

        total_return += (
            item["result"]
        )

        if (
            item["result"]
            > 0
        ):

            success += 1

        else:

            fail += 1

    if count == 0:

        return {

            "accuracy": 0,

            "average": 0
        }

    return {

        "accuracy":

        round(
            success
            /
            count
            *
            100,
            1
        ),

        "average":

        round(
            total_return
            /
            count,
            2
        )
    }
