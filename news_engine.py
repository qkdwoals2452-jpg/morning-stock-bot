import requests
import xml.etree.ElementTree as ET
import re
import html
import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from collections import defaultdict, deque
from urllib.parse import urlencode, urlsplit
from event_identity_engine import duplicate_article, publisher
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "ORION Stock Research Bot qkdwoals2452@gmail.com",

    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
    "Accept-Encoding": "gzip, deflate"
}


# 한 출처의 일시적 오류가 전체 수집을 중단하지 않도록 최대 두 번만 요청한다.
FEED_TIMEOUT = (5, 15)
FEED_MAX_ATTEMPTS = 2
FEED_WORKERS = 4
# 반복 시간초과가 발생한 선택 소스는 짧게 확인하고 검색 인덱스로 전환한다.
# requests timeout은 전체 실행 시간 제한이 아닌 연결/소켓 읽기 대기 제한이다.
NASDAQ_TIMEOUT = (3, 5)
NASDAQ_MAX_ATTEMPTS = 1

# 공개 RSS의 제목/요약만 수집한다. 유료 본문이나 차단된 피드를 우회하지 않는다.
# 2026-10-16 로컬 읽기 전용 점검: 모두 HTTP 200 / 최근 36시간 기사 확인.
MAJOR_MEDIA_FEEDS = [
    ('Bloomberg_Tech', 'https://www.bloomberg.com/feeds/technology/news.rss'),
    ('Bloomberg_Markets', 'https://www.bloomberg.com/feeds/markets/news.rss'),
    ('WSJ_Business', 'https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness'),
    ('WSJ_Tech', 'https://feeds.content.dowjones.io/public/rss/RSSWSJD'),
    ('WSJ_Markets', 'https://feeds.content.dowjones.io/public/rss/RSSMarketsMain'),
    ('FT_International', 'https://www.ft.com/rss/home/international'),
    ('BBC_Business', 'https://feeds.bbci.co.uk/news/business/rss.xml'),
]


class FeedFetchError(Exception):
    def __init__(self, reason, attempts, http_status=None):
        super().__init__(reason)
        self.reason = reason
        self.attempts = attempts
        self.http_status = http_status


def _fetch_feed(url, *, timeout=FEED_TIMEOUT, max_attempts=FEED_MAX_ATTEMPTS):
    for attempt in range(1, max_attempts + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            reason = ("connect_timeout" if isinstance(exc, requests.ConnectTimeout)
                      else "timeout" if isinstance(exc, requests.Timeout) else "connection_error")
            if attempt < max_attempts:
                time.sleep(1)
                continue
            raise FeedFetchError(reason, attempt) from exc
        except requests.RequestException as exc:
            raise FeedFetchError("request_error", attempt) from exc

        status = res.status_code
        if status in (403, 429):
            # 차단/요청 제한은 즉시 재시도하지 않는다.
            raise FeedFetchError("access_denied" if status == 403 else "rate_limited", attempt, status)
        if 500 <= status < 600 and attempt < max_attempts:
            time.sleep(1)
            continue
        if not 200 <= status < 300:
            raise FeedFetchError("http_error", attempt, status)
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError as exc:
            raise FeedFetchError("invalid_xml", attempt, status) from exc
        return root, attempt, status


def _report_feed(source_name, articles, started, attempts, http_status,
                 diagnostics, error=None, received=0):
    recent = len(filter_recent_news(articles, hours=36))
    status = ("error" if error else "empty_feed" if not received
              else "no_relevant" if not articles else "no_recent" if not recent else "ok")
    report = {
        "status": status, "received": received, "parsed": len(articles), "recent": recent,
        "attempts": attempts, "http_status": http_status,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "error": error,
    }
    if diagnostics is not None:
        diagnostics[source_name] = report
    print(f"뉴스 수집: {source_name} | 상태={status} | 응답항목={received} | 파싱={len(articles)} "
          f"| 최근36시간={recent} | 요청={attempts} | HTTP={http_status} "
          f"| {report['elapsed_seconds']}초" + (f" | 사유={error}" if error else ""))


def parse_rss(url, market, source_name, diagnostics=None, *,
              timeout=FEED_TIMEOUT, max_attempts=FEED_MAX_ATTEMPTS):

    articles = []
    started = time.monotonic()
    attempts, http_status, error, received = 0, None, None, 0

    try:

        root, attempts, http_status = _fetch_feed(url, timeout=timeout, max_attempts=max_attempts)

        if root.tag != "rss":
            raise FeedFetchError("unexpected_rss_root", attempts, http_status)

        items = root.findall(".//item")
        received = len(items)
        for item in items:
            if source_name == "Nasdaq_GoogleRSS":
                publisher = item.find("source")
                host = urlsplit(publisher.get("url", "") if publisher is not None else "").hostname or ""
                if host != "nasdaq.com" and not host.endswith(".nasdaq.com"):
                    continue

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
                # RSS가 명시한 원 발행처만 보존한다. 수집 경로(source)와 분리.
                "origin_publisher": (item.findtext('source') or item.findtext(
                    '{http://purl.org/dc/elements/1.1/}publisher') or '').strip(),
                "published_at": published_at

            })

    except FeedFetchError as exc:
        error, attempts, http_status = exc.reason, exc.attempts, exc.http_status
    except Exception as exc:
        error = type(exc).__name__

    _report_feed(source_name, articles, started, attempts, http_status, diagnostics, error, received)
    return articles
def parse_atom(url, market, source_name, diagnostics=None):

    articles = []
    started = time.monotonic()
    attempts, http_status, error, received = 0, None, None, 0

    try:

        root, attempts, http_status = _fetch_feed(url)
        if root.tag != "{http://www.w3.org/2005/Atom}feed":
            raise FeedFetchError("unexpected_atom_root", attempts, http_status)

        ns = {

            "atom": "http://www.w3.org/2005/Atom"

        }

        entries = root.findall("atom:entry", ns)
        received = len(entries)
        for entry in entries:

            title_tag = entry.find("atom:title", ns)

            links = entry.findall("atom:link", ns)
            link_tag = next((tag for tag in links if tag.get("rel", "alternate") == "alternate"), None)

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

    except FeedFetchError as exc:
        error, attempts, http_status = exc.reason, exc.attempts, exc.http_status
    except Exception as exc:
        error = type(exc).__name__

    _report_feed(source_name, articles, started, attempts, http_status, diagnostics, error, received)
    return articles
def remove_duplicates(articles):
    result = []
    for article in articles:
        if not any(duplicate_article(article, old) for old in result):
            result.append(article)
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

def get_nasdaq_news(diagnostics=None):
    reports = diagnostics if diagnostics is not None else {}
    articles = parse_rss(
        "https://www.nasdaq.com/feed/rssoutbound?category=Technology",
        "US", "Nasdaq_Tech", diagnostics=reports,
        timeout=NASDAQ_TIMEOUT, max_attempts=NASDAQ_MAX_ATTEMPTS,
    )
    if reports["Nasdaq_Tech"]["status"] != "error":
        return articles
    # 직접 피드 장애 시 Nasdaq 기사 검색 인덱스만 사용한다.
    # 원본 피드와 범위/수집 경로가 다르므로 별도 출처로 기록한다.
    query = urlencode({"q": 'site:nasdaq.com/articles (technology OR semiconductor OR "data center" OR AI) when:2d',
                       "hl": "en-US", "gl": "US", "ceid": "US:en"})
    reports["Nasdaq_Tech"]["fallback_source"] = "Nasdaq_GoogleRSS"
    return parse_rss("https://news.google.com/rss/search?" + query,
                     "US", "Nasdaq_GoogleRSS", diagnostics=reports)


def _collect_feeds(feeds, market, diagnostics=None):
    """독립 피드를 제한된 병렬도로 수집하되 기존 목록 순서로 합친다."""
    feeds = list(feeds)
    def host_key(feed):
        source, url = feed
        return "www.nasdaq.com" if source == "Nasdaq_Tech" else (urlsplit(url).hostname or url)
    # Fed/BLS 등 같은 호스트의 여러 피드는 동시에 요청하지 않는다.
    gates = {host_key(feed): BoundedSemaphore(1) for feed in feeds}
    def collect(feed):
        source_name, url = feed
        reports = {}
        with gates[host_key(feed)]:
            if source_name == "Nasdaq_Tech":
                articles = get_nasdaq_news(reports)
            else:
                parser = parse_atom if source_name.startswith("BLS_") or source_name == "SEC_Filings" else parse_rss
                articles = parser(url, market, source_name, diagnostics=reports)
        return articles, reports

    articles = []
    with ThreadPoolExecutor(max_workers=FEED_WORKERS) as executor:
        # map 순서는 완료 순서가 아니라 입력 순서다. 진단 dict는 호출 스레드에서만 갱신한다.
        for batch, reports in executor.map(collect, feeds):
            articles.extend(batch)
            if diagnostics is not None:
                diagnostics.update(reports)
    return articles


def get_us_news(diagnostics=None):
    rss_list = [
        # 기존 미국 뉴스

        ("YahooFinance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,MSFT,GOOGL,AMZN,AMD,TSLA,SMCI,AVGO,META&region=US&lang=en-US"),

        ("Investing_Tech", "https://www.investing.com/rss/news_25.rss"),

        ("Investing_Economy", "https://www.investing.com/rss/news_285.rss"),

        ("Nasdaq_Tech", None),
        # SEC 공시는 아래 Atom 파서에서 한 번만 요청한다.
        # Fed 공식

        ("FED_All", "https://www.federalreserve.gov/feeds/press_all.xml"),

        ("FED_Monetary", "https://www.federalreserve.gov/feeds/press_monetary.xml"),

        ("FED_Speeches", "https://www.federalreserve.gov/feeds/speeches.xml"),

        # 미국 경제지표 공식

        ("BLS_Employment", "https://www.bls.gov/feed/empsit.rss"),

        ("BLS_CPI", "https://www.bls.gov/feed/cpi.rss"),

        ("BLS_PPI", "https://www.bls.gov/feed/ppi.rss"),

    ]

    rss_list.extend(MAJOR_MEDIA_FEEDS)
    rss_list.append(("SEC_Filings", "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"))
    news = _collect_feeds(rss_list, "US", diagnostics)
    news = filter_recent_news(news, hours=36)
    news = remove_duplicates(news)

    selected = select_diverse_news(news, limit=200)
    counts = defaultdict(int)
    for article in selected:
        counts[publisher(article)[0]] += 1
    print('미국/글로벌 뉴스 매체별 선택:', dict(counts),
          '| 최근 중복제거 후:', len(news), '| 선택:', len(selected))
    return selected


def select_diverse_news(articles, limit=200):
    """한 매체의 여러 피드가 한도를 독점하지 않도록 순환 선택한다."""
    groups = defaultdict(deque)
    for article in articles:
        groups[publisher(article)[0]].append(article)
    selected = []
    while groups and len(selected) < max(0, limit):
        for key in list(groups):
            if len(selected) >= limit:
                break
            selected.append(groups[key].popleft())
            if not groups[key]:
                del groups[key]
    return selected

def get_korea_news(diagnostics=None):
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

    news = _collect_feeds(rss_list, "KR", diagnostics)

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
