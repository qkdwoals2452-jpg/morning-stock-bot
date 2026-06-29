import requests
import re
import pandas as pd

corp_df = pd.read_csv("corp_code.csv", dtype=str)

corp_map = dict(zip(
    corp_df["stock_code"],
    corp_df["corp_code"]
))
from config import DART_API_KEY

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def to_float(value):
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except:
        return None


def to_int(value):
    try:
        return int(str(value).replace(",", ""))
    except:
        return None


# ------------------------
# 네이버 기본정보
# ------------------------

def get_naver_basic(code):

    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"

        res = requests.get(
            url,
            headers=HEADERS,
            timeout=7
        )

        text = res.text

        per = None
        pbr = None

        per_match = re.search(
            r"<strong>PER\(배\)</strong>\s*</th>\s*<td[^>]*>\s*([\d\.,\-]+)",
            text
        )

        pbr_match = re.search(
            r"<strong>PBR\(배\)</strong>\s*</th>\s*<td[^>]*>\s*([\d\.,\-]+)",
            text
        )

        if per_match:
            per = to_float(per_match.group(1))

        if pbr_match:
            pbr = to_float(pbr_match.group(1))

        print("NAVER PER/PBR:", code, per, pbr)

        return {
            "per": per,
            "pbr": pbr
        }

    except Exception as e:
        print("NAVER ERROR:", code, e)

        return {
            "per": None,
            "pbr": None
        }

# ------------------------
# DART 기업코드
# ------------------------

def get_corp_code(stock_code):
    stock_code = str(stock_code).zfill(6)

    corp_code = corp_map.get(stock_code)

    print("corp lookup:", stock_code, corp_code)

    return corp_code


# ------------------------
# DART 재무
# ------------------------

def get_dart_finance(stock_code):

    corp_code = get_corp_code(stock_code)

    if corp_code is None:
        return {
            "op_margin": None,
            "debt_ratio": None
        }

    year = 2025

    try:

        url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

        params = {
            "crtfc_key": DART_API_KEY,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",
            "fs_div": "CFS"
        }

        res = requests.get(
            url,
            params=params,
            timeout=10
        )

        data = res.json()

        print("DART finance:", stock_code, data)

        if data.get("status") != "000":
            return {
                "op_margin": None,
                "debt_ratio": None
            }

        sales = 0
        op = 0
        asset = 0
        debt = 0

        for row in data.get("list", []):

            name = row.get("account_nm", "")
            account_id = row.get("account_id", "")
            amount = to_int(row.get("thstrm_amount", 0))

            

            if amount is None:
                amount = 0
      
            if (
                name in [
                    "매출액",
                    "매출",
                    "영업수익",
                    "영업수익(매출액)"
                ]
                or account_id in [
                    "ifrs-full_Revenue",
                    "ifrs-full_GrossRevenue",
                    "ifrs-full_RevenueFromContractsWithCustomers"
                ]
            ):

                if amount > sales:
                    sales = amount

            elif name in ["영업이익", "영업이익(손실)"] or "OperatingIncomeLoss" in account_id:
                op = amount

            elif name == "자산총계":
                asset = amount

            elif name == "부채총계":
                debt = amount
        print("SALES:", sales, "OP:", op)
        
        op_margin = None
        debt_ratio = None

        if sales > 0:
            op_margin = round(
                op / sales * 100,
                2
            )

        equity = asset - debt

        if equity > 0:
            debt_ratio = round(
                debt / equity * 100,
                2
            )

        return {
            "op_margin": op_margin,
            "debt_ratio": debt_ratio
        }

    except:

        return {
            "op_margin": None,
            "debt_ratio": None
        }


# ------------------------
# 최종 점수
# ------------------------

def get_finance_score(stock):

    code = stock["code"]

    basic = get_naver_basic(code)
    dart = get_dart_finance(code)

    score = 0

    memo = []

    per = basic["per"]
    pbr = basic["pbr"]

    if per is not None:

        if per <= 15:
            score += 10
            memo.append("PER 저평가")

        elif per <= 30:
            score += 5
            memo.append("PER 양호")

        else:
            score -= 5
            memo.append("PER 고평가")

    if pbr is not None:

        if pbr <= 1:
            score += 10
            memo.append("PBR 저평가")

        elif pbr <= 3:
            score += 5
            memo.append("PBR 보통")

        else:
            score -= 5
            memo.append("PBR 높음")

    op_margin = dart["op_margin"]

    if op_margin is not None:

        if op_margin >= 15:
            score += 15
            memo.append("영업이익률 우수")

        elif op_margin >= 7:
            score += 10
            memo.append("영업이익률 양호")

        elif op_margin > 0:
            score += 3
            memo.append("흑자")

        else:
            score -= 15
            memo.append("영업적자")

    debt_ratio = dart["debt_ratio"]

    if debt_ratio is not None:

        if debt_ratio <= 100:
            score += 10
            memo.append("부채 안정")

        elif debt_ratio <= 200:
            score += 3
            memo.append("부채 보통")

        else:
            score -= 10
            memo.append("부채 높음")

    exclude = False
    exclude_reason = ""

    if op_margin is not None and op_margin < 0:
        exclude = True
        exclude_reason = "영업적자 제외"

    if debt_ratio is not None and debt_ratio >= 300:
        exclude = True
        exclude_reason = "부채비율 과다 제외"

    if pbr is not None and pbr >= 10:
        exclude = True
        exclude_reason = "PBR 과도 제외"

    return {
        "score": score,
        "memo": ", ".join(memo),
        "per": per,
        "pbr": pbr,
        "op_margin": op_margin,
        "debt_ratio": debt_ratio,
        "exclude": exclude,
        "exclude_reason": exclude_reason
    }
