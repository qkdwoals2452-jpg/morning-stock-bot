import requests
import xml.etree.ElementTree as ET
import re
import html
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "ORION Stock Research Bot qkdwoals2452@gmail.com",

    "Accept-Encoding": "gzip, deflate"
}


def parse_rss(url, market, source_name):

    articles = []

    try:

        res = requests.get(url, headers=HEADERS, timeout=10)

        res.raise_for_status()

        root = ET.fromstring(res.content)

        for item in root.findall(".//item"):

            title_tag = item.find("title")

            link_tag = item.find("link")

            description_tag = item.find("description")
            pubdate_tag = item.find("pubDate")

            published_at = ""

            if pubdate_tag is not None and pubdate_tag.text:
                try:
                   dt = parsedate_to_datetime(pubdate_tag.text.strip())
                   published_at = dt.isoformat()
                except Exception:
                    published_at = pubdate_tag.text.strip()

            content_tag = item.find(

                "{http://purl.org/rss/1.0/modules/content/}encoded"

            )

            if title_tag is None or not title_tag.text:

                continue

            title = title_tag.text.strip()

            link = ""

            if link_tag is not None and link_tag.text:

                link = link_tag.text.strip()

            description = ""

            if description_tag is not None and description_tag.text:

                description = description_tag.text.strip()

            content = ""

            if content_tag is not None and content_tag.text:

                content = content_tag.text.strip()

            # content가 있으면 우선 사용하고, 없으면 description 사용

            summary = content or description

            # HTML 태그 및 특수문자 정리

            summary = html.unescape(summary)

            summary = re.sub(r"<[^>]+>", " ", summary)

            summary = re.sub(r"\s+", " ", summary).strip()

            articles.append({

                "title": title,

                "summary": summary,

                "link": link,

                "market": market,

                "source": source_name,
                "published_at": published_at

            })

    except Exception as e:

        print("RSS 수집 오류:", source_name, str(e))

    return articles
def parse_atom(url, market, source_name):

    articles = []

    try:

        res = requests.get(url, headers=HEADERS, timeout=10)

        res.raise_for_status()

        root = ET.fromstring(res.content)

        ns = {

            "atom": "http://www.w3.org/2005/Atom"

        }

        for entry in root.findall("atom:entry", ns):

            title_tag = entry.find("atom:title", ns)

            link_tag = entry.find("atom:link", ns)

            summary_tag = entry.find("atom:summary", ns)

            updated_tag = entry.find("atom:updated", ns)

            if title_tag is None or not title_tag.text:

                continue

            title = title_tag.text.strip()
            # SEC 핵심 공시만 통과

            if source_name == "SEC_Filings":

                important_forms = [

                    "8-K",

                    "10-Q",

                    "10-K",

                    "6-K",

                    "S-4"

                ]

                form_type = title.split(" - ")[0].strip()

                if form_type not in important_forms:

                    continue

            link = ""

            if link_tag is not None:

                link = link_tag.attrib.get("href", "").strip()

            summary = ""

            if summary_tag is not None and summary_tag.text:

                summary = summary_tag.text.strip()

            summary = html.unescape(summary)

            summary = re.sub(r"<[^>]+>", " ", summary)

            summary = re.sub(r"\s+", " ", summary).strip()

            published_at = ""

            if updated_tag is not None and updated_tag.text:

                published_at = updated_tag.text.strip()

            articles.append({

                "title": title,

                "summary": summary,

                "link": link,

                "market": market,

                "source": source_name,

                "published_at": published_at

            })

    except Exception as e:

        print("ATOM 수집 오류:", source_name, str(e))

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
def filter_recent_news(articles, hours=36):

    now = datetime.now(timezone.utc)

    result = []

    for article in articles:

        published_at = article.get("published_at", "")

        # 날짜 없는 기사는 일단 제외
        if not published_at:
            continue

        try:
            dt = datetime.fromisoformat(
                published_at.replace("Z", "+00:00")
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            age_hours = (
                now - dt.astimezone(timezone.utc)
            ).total_seconds() / 3600

            if 0 <= age_hours <= hours:
                result.append(article)

        except Exception:
            continue

    return result

def get_us_news():
    rss_list = [
        # 기존 미국 뉴스

        ("YahooFinance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,MSFT,GOOGL,AMZN,AMD,TSLA,SMCI,AVGO,META&region=US&lang=en-US"),

        ("Investing_Tech", "https://www.investing.com/rss/news_25.rss"),

        ("Investing_Economy", "https://www.investing.com/rss/news_285.rss"),

        ("Nasdaq_Tech", "https://www.nasdaq.com/feed/rssoutbound?category=Technology"),
        # SEC 공식

        ("SEC_Filings", "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"),
        # Fed 공식

        ("FED_All", "https://www.federalreserve.gov/feeds/press_all.xml"),

        ("FED_Monetary", "https://www.federalreserve.gov/feeds/press_monetary.xml"),

        ("FED_Speeches", "https://www.federalreserve.gov/feeds/speeches.xml"),

        # 미국 경제지표 공식

        ("BLS_Employment", "https://www.bls.gov/feed/empsit.rss"),

        ("BLS_CPI", "https://www.bls.gov/feed/cpi.rss"),

        ("BLS_PPI", "https://www.bls.gov/feed/ppi.rss"),

    ]

    news = []

    for source_name, url in rss_list:
        news += parse_rss(url, "US", source_name)
    news += parse_atom(

        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom",

        "US",

        "SEC_Filings"

    )
    news = filter_recent_news(news, hours=36)
    news = remove_duplicates(news)

    return news[:200]

def get_korea_news():
    rss_list = [
        ("한국경제_증권", "https://www.hankyung.com/feed/finance"),
        ("한국경제_경제", "https://www.hankyung.com/feed/economy"),
        

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

    news = filter_recent_news(news, hours=36)

    news = remove_duplicates(news)

    return news[:180]




def get_all_news():
    us_news = get_us_news()
    kr_news = get_korea_news()

    all_news = us_news + kr_news

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=36)

    fresh_news = []

    for article in all_news:
        published_at = article.get("published_at", "")

        if not published_at:
            continue

        try:
            dt = datetime.fromisoformat(
                published_at.replace("Z", "+00:00")
            )

            if dt >= cutoff:
                fresh_news.append(article)

        except Exception:
            continue

    print(
        f"\n전체 뉴스 수: {len(all_news)}"
    )

    print(
        f"최근 36시간 뉴스 수: {len(fresh_news)}"
    )

    print("\n===== 뉴스 날짜 확인 TOP10 =====")

    for article in fresh_news[:10]:
        print(
            article.get("source", ""),
            "|",
            article.get("published_at", ""),
            "|",
            article.get("title", "")
        )

    return fresh_news    
