import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

TOKEN = "8696435525:AAFLWarYrwou-l1BoqaJ0PdbH0mUXOJnJXs"
CHAT_ID = "1648839639"

THEMES = {
    "HBM": ["SK하이닉스", "한미반도체"],
    "AI": ["삼성전자", "SK하이닉스"],
    "데이터센터": ["삼성전자", "SK하이닉스"],
    "반도체": ["SK하이닉스", "한미반도체"],

    "2차전지": ["에코프로", "포스코퓨처엠"],
    "동박": ["롯데에너지머티리얼즈", "솔루스첨단소재"],
    "CCL": ["롯데에너지머티리얼즈", "코리아써키트"],

    "전력": ["효성중공업", "LS ELECTRIC"],
    "원전": ["두산에너빌리티", "한전기술"],
    "태양광": ["한화솔루션", "OCI"],

    "로봇": ["레인보우로보틱스", "두산로보틱스"],
    "우주항공": ["한국항공우주", "한화에어로스페이스"],
    "자율주행": ["현대모비스", "HL만도"],

    "방산": ["한화에어로스페이스", "LIG넥스원"],
    "건설": ["현대건설", "GS건설"],
    "재건축": ["현대건설", "대우건설"],

    "바이오": ["삼성바이오로직스", "셀트리온"],
    "엔터": ["하이브", "JYP Ent."],
    "게임": ["엔씨소프트", "크래프톤"],

    "PCB": ["삼성전기", "대덕전자", "심텍", "코리아써키트"],
    "MLCC": ["삼성전기", "삼화콘덴서"]
}


STOCK_CODES = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "한미반도체": "042700",

    "삼성전기": "009150",
    "삼화콘덴서": "001820",
    "대덕전자": "353200",
    "심텍": "222800",
    "코리아써키트": "007810",

    "롯데에너지머티리얼즈": "020150",
    "솔루스첨단소재": "336370",
    "에코프로": "086520",
    "포스코퓨처엠": "003670",

    "효성중공업": "298040",
    "LS ELECTRIC": "010120",
    "두산에너빌리티": "034020",
    "한전기술": "052690",
    "한화솔루션": "009830",
    "OCI": "456040",

    "레인보우로보틱스": "277810",
    "두산로보틱스": "454910",
    "한국항공우주": "047810",
    "한화에어로스페이스": "012450",
    "현대모비스": "012330",
    "HL만도": "204320",

    "LIG넥스원": "079550",
    "현대건설": "000720",
    "GS건설": "006360",
    "대우건설": "047040",

    "삼성바이오로직스": "207940",
    "셀트리온": "068270",
    "하이브": "352820",
    "JYP Ent.": "035900",
    "엔씨소프트": "036570",
    "크래프톤": "259960"
}


def get_news():
    url = "https://www.hankyung.com/feed/finance"
    res = requests.get(url)
    root = ET.fromstring(res.content)

    titles = []
    for item in root.findall(".//item"):
        title = item.find("title")
        if title is not None and title.text:
            titles.append(title.text.strip())

    return titles[:20]

def find_themes(news):
    result = {}
    for title in news:
        for keyword in THEMES:
            if keyword in title:
                result.setdefault(keyword, []).append(title)
    return result

def load_data():
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def detect_3days(data):
    dates = sorted(data.keys())[-3:]
    result = []

    if len(dates) < 3:
        return result

    for keyword in THEMES:
        if all(keyword in data[d] for d in dates):
            result.append(keyword)

    return result

def calculate_score(today_counts, trend_3days):
    scores = {}

    for keyword, count in today_counts.items():
        score = count

        if keyword in trend_3days:
            score += 3

        scores[keyword] = score

    return scores

def get_stock_power(stock_name):
    code = STOCK_CODES.get(stock_name)

    if not code:
        return {
            "name": stock_name,
            "change_rate": 0,
            "volume": 0,
            "value": 0
        }

    try:
        url = f"https://api.stock.naver.com/stock/{code}/basic"
        headers = {"User-Agent": "Mozilla/5.0"}

        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()

        change_rate = data.get("fluctuationsRatio", "0")
        volume = data.get("accumulatedTradingVolume", "0")
        value = data.get("accumulatedTradingValue", "0")

        change_rate = float(str(change_rate).replace("%", "").replace(",", ""))
        volume = int(str(volume).replace(",", ""))
        value = int(str(value).replace(",", ""))

        return {
            "name": stock_name,
            "change_rate": change_rate,
            "volume": volume,
            "value": value
        }

    except:
        return {
            "name": stock_name,
            "change_rate": 0,
            "volume": 0,
            "value": 0
        }

def pick_leader(stocks):
    stock_data = []

    for stock in stocks:
        power = get_stock_power(stock)
        stock_data.append(power)

    stock_data = sorted(
        stock_data,
        key=lambda x: (x["change_rate"], x["value"], x["volume"]),
        reverse=True
    )

    return stock_data

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=data)

news = get_news()
themes = find_themes(news)

today = datetime.now().strftime("%Y-%m-%d")
data = load_data()

today_counts = {}
for keyword, titles in themes.items():
    today_counts[keyword] = len(titles)

past_dates = sorted(data.keys())
yesterday_counts = data[past_dates[-1]] if past_dates else {}

data[today] = today_counts

trend_3days = detect_3days(data)
scores = calculate_score(today_counts, trend_3days)

msg = "📈 한국경제 테마 감지\n\n"

sent_count = 0

if scores:
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    for keyword, score in sorted_scores:
        if score < 3:
            continue

        sent_count += 1

        stocks = THEMES[keyword]
        titles = themes[keyword]

        today_count = today_counts.get(keyword, 0)
        yesterday_count = yesterday_counts.get(keyword, 0)
        increase = today_count - yesterday_count

        stock_rank = pick_leader(stocks)

        if score >= 8:
            level = "🚨 초강력"
        elif score >= 5:
            level = "🔥 강"
        else:
            level = "⚡ 초기"

        msg += f"{level} {keyword} ({score}점)\n"

        if yesterday_count == 0 and today_count >= 2:
            msg += "🆕 신규 테마\n"

        if increase >= 2:
            msg += f"🚀 전일 대비 +{increase}개 급증\n"

        if keyword in trend_3days:
            msg += "📌 3일 연속 등장\n"

        if stock_rank:
            leader = stock_rank[0]

            msg += f"🚀 대장주: {leader['name']} ({leader['change_rate']}%)\n"
            msg += f"💰 거래대금: {leader['value'] // 100000000}억\n"

            if len(stock_rank) > 1:
                second = stock_rank[1]
                msg += f"⚡ 후발주: {second['name']} ({second['change_rate']}%)\n"

            if (
    leader["change_rate"] >= 3 and
    leader["value"] >= 1000_0000_0000 and
    today_count >= 3
):
    msg += "🔥 강력 매매 신호\n"

        msg += f"📰 기사 수: {today_count}개\n"

        msg += "🧠 핵심 뉴스:\n"
        for t in titles[:2]:
            msg += f"• {t}\n"

        msg += "━━━━━━━━━━━━━━\n"

if sent_count == 0:
    msg += "오늘은 강한 테마 없음\n"

send_telegram(msg)
save_data(data)
