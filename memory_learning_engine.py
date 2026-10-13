import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from statistics import mean
from performance_validation_engine import completed_performance

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
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    name = stock.get('name', '') if isinstance(stock, dict) else stock
    code = stock.get('code') if isinstance(stock, dict) else None
    if any(item.get('date') == now.date().isoformat() and item.get('theme') == theme
           and (item.get('code') == code if code else item.get('stock') == name)
           for item in history if isinstance(item, dict)):
        return

    history.append({

        "theme": theme,

        "stock": name,
        "code": code,
        "date": now.date().isoformat(),
        "recommended_at": now.isoformat(),

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

def get_learning_score(stock, as_of=None, minimum_samples=5):
    from backtest_engine import load_backtest
    data = load_backtest()
    code = stock.get('code') if isinstance(stock, dict) else None
    name = stock.get('name', '') if isinstance(stock, dict) else stock
    if isinstance(data, list):
        data = [item for item in data if isinstance(item, dict)
                and (item.get('code') == code if code else item.get('name') == name)]
    report = completed_performance(data, as_of=as_of)
    if not code and len({row['code'] for row in report['samples']}) > 1:
        return {'score': 0, 'memo': '동명 종목 확인 필요', 'sample_count': 0}
    count = report['count']
    result = {'score': 0, 'memo': '검증 표본 부족', 'sample_count': count,
              'status': report['status'],
              'minimum_samples': minimum_samples, 'horizon': 5,
              'average_return': mean(row['return'] for row in report['samples']) if count else None,
              'excluded': report['excluded'],
              'source': 'completed_trading_checkpoints'}
    if not isinstance(minimum_samples, int) or isinstance(minimum_samples, bool) or minimum_samples < 5 or count < minimum_samples:
        return result
    avg = result['average_return']
    result['score'] = 20 if avg >= 10 else 10 if avg >= 5 else 3 if avg >= 0 else -10
    result['memo'] = f'검증된 D+5 기준가 성과 {count}개 평균 {avg:.4f}%'
    return result


# --------------------
# 프로젝트 성적표
# --------------------

def get_project_report(as_of=None):
    from backtest_engine import load_backtest
    report = completed_performance(load_backtest(), as_of=as_of)
    return {key: value for key, value in report.items() if key != 'samples'}
