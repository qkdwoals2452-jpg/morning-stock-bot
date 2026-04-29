import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

TOKEN = "8696435525:AAFLWarYrwou-l1BoqaJ0PdbH0mUXOJnJXs"
CHAT_ID = "1648839639"

THEMES = {
    "데이터센터": ["삼성전자", "SK하이닉스"],
    "HBM": ["SK하이닉스", "한미반도체"],
    "MLCC": ["삼성전기", "삼화콘덴서"],
    "전력": ["효성중공업", "LS ELECTRIC"],
    "원전": ["두산에너빌리티", "한전기술"],
    "AI": ["삼성전자", "SK하이닉스"],
    "반도체": ["SK하이닉스", "한미반도체"]
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
        appeared = True
        for d in dates:
            if keyword not in data[d]:
                appeared = False

        if appeared:
            result.append(keyword)

    return result

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

data[today] = today_counts

msg = "📈 한국경제 테마 감지\n\n"

if themes:
    for keyword, titles in themes.items():
        stocks = THEMES[keyword]
        msg += f"🔥 {keyword}\n"
        msg += f"🥇 대장주: {stocks[0]}\n"
        msg += f"🥈 2등주: {stocks[1]}\n"
        msg += f"기사 수: {len(titles)}개\n"
        msg += "관련 기사:\n"
        for t in titles[:2]:
            msg += f"• {t}\n"
        msg += "\n"
else:
    msg += "오늘 감지된 테마 없음\n\n"

surges = []
for keyword, count in today_counts.items():
    if count >= 2:
        surges.append((keyword, count))

if surges:
    msg += "⚠️ 급증 감지\n"
    for keyword, count in surges:
        stocks = THEMES[keyword]
        msg += f"{keyword} → 관련 기사 {count}개\n"
        msg += f"🥇 {stocks[0]} / 🥈 {stocks[1]}\n"
    msg += "\n"

trend_3days = detect_3days(data)

if trend_3days:
    msg += "🚨 3일 연속 등장 테마\n"
    for keyword in trend_3days:
        stocks = THEMES[keyword]
        msg += f"{keyword}\n"
        msg += f"🥇 {stocks[0]} / 🥈 {stocks[1]}\n"
else:
    msg += "아직 3일 연속 테마는 없음\n"

send_telegram(msg)
save_data(data)
