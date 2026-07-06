import requests
import pandas as pd
from datetime import datetime
from config import DART_API_KEY

HEADERS = {"User-Agent": "Mozilla/5.0"}

corp_df = pd.read_csv("corp_code.csv", dtype=str)
corp_map = dict(zip(corp_df["stock_code"], corp_df["corp_code"]))


def to_int(value):
    try:
        return int(str(value).replace(",", ""))
    except:
        return None


def get_corp_code(stock_code):
    stock_code = str(stock_code).zfill(6)
    return corp_map.get(stock_code)


def get_dart_year_finance(stock_code, year):
    corp_code = get_corp_code(stock_code)

    if corp_code is None:
        return None

    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": "11011",
        "fs_div": "CFS"
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if data.get("status") != "000":
            return None

        sales = 0
        op = 0
        net_income = 0
        asset = 0
        debt = 0
        equity = 0

        for row in data.get("list", []):
            name = row.get("account_nm", "")
            account_id = row.get("account_id", "")
            amount = to_int(row.get("thstrm_amount", 0)) or 0

            if (
                name in ["매출액", "매출", "영업수익", "영업수익(매출액)"]
                or account_id in [
                    "ifrs-full_Revenue",
                    "ifrs-full_GrossRevenue",
                    "ifrs-full_RevenueFromContractsWithCustomers"
                ]
            ):
                sales = max(sales, amount)

            elif name in ["영업이익", "영업이익(손실)"] or "OperatingIncomeLoss" in account_id:
                op = amount

            elif name in ["당기순이익", "당기순이익(손실)"] or account_id in [
                "ifrs-full_ProfitLoss",
                "ifrs-full_ProfitLossAttributableToOwnersOfParent"
            ]:
                net_income = amount

            elif name == "자산총계":
                asset = amount

            elif name == "부채총계":
                debt = amount

            elif name == "자본총계":
                equity = amount

        if equity == 0 and asset > 0:
            equity = asset - debt

        roe = None
        op_margin = None
        debt_ratio = None

        if equity > 0:
            roe = round(net_income / equity * 100, 2)

        if sales > 0:
            op_margin = round(op / sales * 100, 2)

        if equity > 0:
            debt_ratio = round(debt / equity * 100, 2)

        return {
            "year": year,
            "sales": sales,
            "op": op,
            "net_income": net_income,
            "equity": equity,
            "roe": roe,
            "op_margin": op_margin,
            "debt_ratio": debt_ratio
        }

    except Exception as e:
        print("QUALITY DART ERROR:", stock_code, year, e)
        return None


def calc_growth(first, last):
    if first is None or last is None:
        return None
    if first <= 0:
        return None

    try:
        return round((last / first - 1) * 100, 2)
    except:
        return None


def make_quality_grade(score):
    if score >= 90:
        return "Champion"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    else:
        return "D"


def get_quality_score(stock):
    code = stock["code"]

    current_year = datetime.now().year
    years = list(range(current_year - 5, current_year))

    records = []

    for year in years:
        data = get_dart_year_finance(code, year)
        if data:
            records.append(data)

    if len(records) < 3:
        return {
            "score": 0,
            "grade": "D",
            "memo": "5년 재무데이터 부족",
            "records": records,
            "reason": []
        }

    sales_list = [r["sales"] for r in records if r["sales"] > 0]
    op_list = [r["op"] for r in records]
    roe_list = [r["roe"] for r in records if r["roe"] is not None]

    sales_growth = None
    profit_growth = None
    roe_avg = None
    roe_min = None

    if len(sales_list) >= 2:
        sales_growth = calc_growth(sales_list[0], sales_list[-1])

    if len(op_list) >= 2 and op_list[0] > 0:
        profit_growth = calc_growth(op_list[0], op_list[-1])

    if roe_list:
        roe_avg = round(sum(roe_list) / len(roe_list), 2)
        roe_min = min(roe_list)

    latest = records[-1]

    score = 0
    reason = []

    # 5년 매출 성장
    if sales_growth is not None:
        if sales_growth >= 100:
            score += 25
            reason.append("5년 매출 2배 이상 성장")
        elif sales_growth >= 50:
            score += 20
            reason.append("5년 매출 성장 우수")
        elif sales_growth >= 20:
            score += 15
            reason.append("5년 매출 성장 양호")
        elif sales_growth >= 0:
            score += 5
            reason.append("5년 매출 유지")
        else:
            score -= 10
            reason.append("5년 매출 감소")

    # 5년 영업이익 성장
    if profit_growth is not None:
        if profit_growth >= 100:
            score += 25
            reason.append("5년 영업이익 2배 이상 성장")
        elif profit_growth >= 50:
            score += 20
            reason.append("5년 영업이익 성장 우수")
        elif profit_growth >= 20:
            score += 15
            reason.append("5년 영업이익 성장 양호")
        elif profit_growth >= 0:
            score += 5
            reason.append("5년 영업이익 유지")
        else:
            score -= 10
            reason.append("5년 영업이익 감소")

    # ROE 평균
    if roe_avg is not None:
        if roe_avg >= 25:
            score += 20
            reason.append(f"5년 평균 ROE 우수 {roe_avg}%")
        elif roe_avg >= 15:
            score += 15
            reason.append(f"5년 평균 ROE 양호 {roe_avg}%")
        elif roe_avg >= 10:
            score += 10
            reason.append(f"5년 평균 ROE 보통 {roe_avg}%")
        elif roe_avg > 0:
            score += 3
            reason.append(f"5년 평균 ROE 낮음 {roe_avg}%")
        else:
            score -= 15
            reason.append("5년 평균 ROE 적자")

    # ROE 안정성
    if roe_min is not None:
        if roe_min >= 15:
            score += 10
            reason.append("ROE 안정성 우수")
        elif roe_min >= 5:
            score += 5
            reason.append("ROE 안정성 보통")
        else:
            score -= 5
            reason.append("ROE 변동성 주의")

    # 최근 영업이익률
    op_margin = latest.get("op_margin")
    if op_margin is not None:
        if op_margin >= 20:
            score += 10
            reason.append("최근 영업이익률 우수")
        elif op_margin >= 10:
            score += 7
            reason.append("최근 영업이익률 양호")
        elif op_margin > 0:
            score += 3
            reason.append("최근 흑자")
        else:
            score -= 10
            reason.append("최근 영업적자")

    # 최근 부채비율
    debt_ratio = latest.get("debt_ratio")
    if debt_ratio is not None:
        if debt_ratio <= 100:
            score += 10
            reason.append("부채비율 안정")
        elif debt_ratio <= 200:
            score += 5
            reason.append("부채비율 보통")
        else:
            score -= 10
            reason.append("부채비율 높음")

    if score < 0:
        score = 0

    if score > 100:
        score = 100

    return {
        "score": score,
        "grade": make_quality_grade(score),
        "sales_growth": sales_growth,
        "profit_growth": profit_growth,
        "roe_avg": roe_avg,
        "roe_min": roe_min,
        "op_margin": op_margin,
        "debt_ratio": debt_ratio,
        "memo": f"Champion Score {score}점",
        "records": records,
        "reason": reason
    }
