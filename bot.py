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

# 어제 데이터 찾기
past_dates = sorted(data.keys())
yesterday_counts = data[past_dates[-1]] if past_dates else {}

# 오늘 데이터 저장
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

        msg += f"🎯 핵심주: {', '.join(stocks[:2])}\n"
        msg += f"📰 기사 수: {today_count}개\n"

        msg += "🧠 핵심 뉴스:\n"
        for t in titles[:2]:
            msg += f"• {t}\n"

        msg += "━━━━━━━━━━━━━━\n"

if sent_count == 0:
    msg += "오늘은 강한 테마 없음\n"

send_telegram(msg)
save_data(data)
