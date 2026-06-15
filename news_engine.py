import requests
import xml.etree.ElementTree as ET
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def parse_rss(url, market, source_name):
    articles = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        root = ET.fromstring(res.content)

        for item in root.findall(".//item"):
            title = item.find("title")
            link = item.find("link")

            if title is not None and title.text:
                articles.append({
                    "title": title.text.strip(),
                    "link": link.text.strip() if link is not None and link.text else "",
                    "market": market,
                    "source": source_name
                })

    except Exception:
        pass

    return articles


def remove_duplicates(articles):
    result = []
    seen = []

    for article in articles:
        title = article["title"]
        words = set(re.sub(r"[^가-힣A-Za-z0-9 ]", " ", title).split())

        duplicate = False

        for old_words in seen:
            if len(words & old_words) >= 3:
                duplicate = True
                break

        if not duplicate:
            result.append(article)
            seen.append(words)

    return result


def get_us_news():
    rss_list = [
        ("YahooFinance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,MSFT,GOOGL,AMZN,AMD,TSLA,SMCI,AVGO,META&region=US&lang=en-US"),
        ("Investing_Tech", "https://www.investing.com/rss/news_25.rss"),
        ("Investing_Economy", "https://www.investing.com/rss/news_285.rss"),
        ("Nasdaq_Tech", "https://www.nasdaq.com/feed/rssoutbound?category=Technology"),
    ]

    news = []

    for source_name, url in rss_list:
        news += parse_rss(url, "US", source_name)

    return remove_duplicates(news)[:120]


def get_korea_news():
    rss_list = [
        ("한국경제_증권", "https://www.hankyung.com/feed/finance"),
        ("한국경제_경제", "https://www.hankyung.com/feed/economy"),
        ("한국경제_산업", "https://www.hankyung.com/feed/industry"),

        ("매일경제_경제", "https://www.mk.co.kr/rss/30100041/"),
        ("매일경제_증권", "https://www.mk.co.kr/rss/50200011/"),
        ("매일경제_기업", "https://www.mk.co.kr/rss/50100032/"),

        ("이데일리_증권", "http://rss.edaily.co.kr/stock_news.xml"),
        ("이데일리_경제", "http://rss.edaily.co.kr/economy_news.xml"),
        ("이데일리_기업", "http://rss.edaily.co.kr/enterprise_news.xml"),
    ]

    news = []

    for source_name, url in rss_list:
        news += parse_rss(url, "KR", source_name)

    return remove_duplicates(news)[:180]


def get_all_news():
    us_news = get_us_news()
    kr_news = get_korea_news()

    return us_news + kr_news
