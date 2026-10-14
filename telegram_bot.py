import html
import requests
import time

from config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID

)


def send_message(message):

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}"
        f"/sendMessage"
    )

    data = {

        "chat_id": TELEGRAM_CHAT_ID,

        "text": message,

        "parse_mode": "HTML",

        "disable_web_page_preview": True
    }

    try:

        requests.post(
            url,
            data=data,
            timeout=10
        )

    except Exception as e:

        print(
            "텔레그램 오류",
            e
        )


def split_message(
    message,
    max_length=3500
):

    result = []

    while len(message) > max_length:

        pos = message.rfind(
            "\n",
            0,
            max_length
        )

        if pos == -1:
            pos = max_length

        result.append(
            message[:pos]
        )

        message = message[pos:]

    result.append(message)

    return result


def send_telegram(
    results,
    project_status
):

    msg = ""

    msg += "🚀 Project ORION\n\n"

    msg += (
        "🇺🇸 미국뉴스 기반\n"
        "🇰🇷 한국증시 AI 탐지\n\n"
    )

    watch = project_status.get('supply_chain_watch', {})
    if watch.get('paths'):
        msg += "🔎 공급망 관찰 — 추천·신규 수주 확정 아님\n"
        msg += f"관찰 경로 {len(watch['paths'])}개 중 최대 5개 표시\n"
        for item in watch['paths'][:5]:
            msg += html.escape(' → '.join(item['path'])) + '\n'
            msg += "기존 관계 원자료 확인 / 이번 사건 매출·이익 귀속 미확정\n"
            if item['knowledge_timing'] == 'retrospective_review':
                msg += "현재 원자료를 검토한 연결이며 당시 탐지 실적이 아닙니다.\n"
            msg += '<a href="' + html.escape(item['event_link'], quote=True) + '">미국 사건 원문</a>\n'
            for edge in item['evidence']:
                msg += '<a href="' + html.escape(edge['source_url'], quote=True) + '">관계 근거</a> (' + html.escape(edge['published_on']) + ')\n'
            orders = item.get('order_review', {})
            if orders.get('documented_orders'):
                msg += "개별 주문 문서 확인 / 이 미국 사건과의 인과·매출 인식은 미확정\n"
                for order in orders['documented_orders'][:2]:
                    msg += html.escape(f"계약금액 {order['amount']:,} {order['currency']} / 주문일 {order['ordered_on']}") + '\n'
                    if order['knowledge_timing'] == 'retrospective_review':
                        msg += "사후 확인 문서이며 당시 탐지 실적이 아닙니다.\n"
                    msg += '<a href="' + html.escape(order['source_url'], quote=True) + '">개별 주문 근거</a>\n'
            elif orders:
                msg += "대조 가능한 개별 주문 원자료 미확인 — 주문 없음 판정 아님\n"
        msg += '\n'

    for theme_data in results:

        theme = theme_data["theme"]
        ranked = theme_data["ranked"]

        msg += (
            f"🔥 {theme['name']}\n"
        )

        msg += (
            f"📊 사건점수 "
            f"{theme['score']}\n"
        )

        msg += (
            f"🧠 "
            f"{theme['reason']}\n\n"
        )
        
        msg += (
            f"🔎 검증 후보 TOP{min(len(ranked), 5)}\n"
        )

        for i, stock in enumerate(
            ranked[:5],
            1
        ):

            msg += (
                f"{i}. "
                f"{stock['grade']} "
                f"{stock['name']} "
                f"({stock['code']})\n"
            )

            msg += (
                f"   정렬점수(수익확률 아님) "
                f"{stock['final_score']}\n"
            )

            if stock["reason"]:

                msg += (
                    "   ✔ "
                    + ", ".join(
                        stock["reason"]
                    )
                    + "\n"
                )

        msg += "\n"

        msg += (
            "📰 핵심 뉴스\n"
        )

        seen_titles = set()
        unique_articles = []

        for article in theme["articles"]:
            title = article.get("title", "").strip()
            link = article.get("link", "").strip()

            key = link or title

            if not key:
                continue

            if key in seen_titles:
                continue

            seen_titles.add(key)
            unique_articles.append(article)
        for article in unique_articles[:3]:

            if (
                article["market"]
                == "US"
            ):
                flag = "🇺🇸"
            else:
                flag = "🇰🇷"

            title = html.escape(

                article.get("title", "")

            )

            link = article.get(

                "link",

                ""

            )

            if link:

                msg += (

                    f'{flag} '

                    f'<a href="{link}">{title}</a>\n'

                )

            else:

                 msg += (

                     f"{flag} "

                     f"{title}\n"

                 )

        msg += (
            "\n━━━━━━━━━━━━━━\n\n"
        )

    msg += (
        "📊 프로젝트 현황\n\n"
    )

    msg += (
        f"기록 확인일수 : "
        f"{project_status['saved_days']}일\n"
    )

    msg += (
        f"누적 추천테마 : "
        f"{project_status['saved_themes']}개\n"
    )
    msg += "날짜·테마 중복 제외 / 남아 있는 기록 기준\n"

    msg += (
        "\n🤖 "
        "미국의 돈의 흐름을 읽고\n"
    )

    msg += (
        "한국의 다음 대장주를 찾습니다."
    )

    messages = split_message(
        msg
    )

    for part in messages:

        send_message(
            part
        )

        time.sleep(0.5)
