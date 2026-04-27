import requests
from bs4 import BeautifulSoup
import telegram
import os

TOKEN = TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1648839639"

KEYWORDS = {
    "데이터센터": ["삼성전자", "SK하이닉스"],
    "MLCC": ["삼성전기", "삼화콘덴서"],
    "HBM": ["SK하이닉스", "한미반도체"],
    "전력": ["효성중공업", "LS ELECTRIC"],
    "원전": ["두산에너빌리티", "한전기술"]
}

def get_news():
    url = "https://www.hankyung.com/feed/economy"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "xml")
    titles = [item.title.text for item in soup.find_all("item")[:10]]
    return titles

def find_keywords(titles):
    found = []
    for title in titles:
        for key in KEYWORDS:
            if key in title:
                found.append(key)
    return list(set(found))

def send_telegram(msg):
    bot = telegram.Bot(token=TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=msg)

def main():
    titles = get_news()
    keys = find_keywords(titles)

    if not keys:
        return

    msg = "📊 오늘 아침 테마\n\n"
    for k in keys:
        stocks = KEYWORDS[k]
        msg += f"{k}\n🥇 {stocks[0]}\n🥈 {stocks[1]}\n\n"

    send_telegram(msg)

if __name__ == "__main__":
    main()
