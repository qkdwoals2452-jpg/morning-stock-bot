import requests
import re
import pandas as pd

corp_df = pd.read_csv("corp_code.csv", dtype=str)

corp_map = dict(zip(
    corp_df["stock_code"],
    corp_df["corp_code"]
))
from config import DART_API_KEY
from quality_engine import get_quality_score
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
        url = f"https://m.stock.naver.com/api/stock/{code}/integration"

        res = requests.get(
            url,
            headers=HEADERS,
            timeout=7
        )

        res.raise_for_status()
        values = {item.get("code"): item.get("value", "")
                  for item in res.json().get("totalInfos", [])}
        per = to_float(str(values.get("per", "")).replace("배", ""))
        pbr = to_float(str(values.get("pbr", "")).replace("배", ""))

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
        asset = None
        debt = None
        equity = None

        for row in data.get("list", []):

            if row.get("sj_div") not in {"BS", "IS", "CIS"}:
                continue

            name = re.sub(r"\s+", "", row.get("account_nm", ""))
            account_id = row.get("account_id", "")
            amount = to_int(row.get("thstrm_amount"))

            

            if amount is None:
                continue
      
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

            elif row.get("sj_div") == "BS" and (account_id == "ifrs-full_Assets" or name == "자산총계"):
                asset = amount

            elif row.get("sj_div") == "BS" and (account_id == "ifrs-full_Liabilities" or name == "부채총계"):
                debt = amount
            elif row.get("sj_div") == "BS" and (account_id == "ifrs-full_Equity" or name == "자본총계"):
                equity = amount
        print("SALES:", sales, "OP:", op)
        
        op_margin = None
        debt_ratio = None

        if sales > 0:
            op_margin = round(
                op / sales * 100,
                2
            )

        if equity is None and asset is not None and debt is not None:
            equity = asset - debt

        if equity is not None and equity > 0 and debt is not None:
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
    quality = get_quality_score(stock)
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
        # Champion Score 반영
        if quality.get("score", 0) > 0:
            quality_bonus = int(quality["score"] * 0.3)
            score += quality_bonus
            memo.append(f"Champion {quality['score']}점")

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
        "quality": quality,
        "exclude": exclude,
        "exclude_reason": exclude_reason
    }
