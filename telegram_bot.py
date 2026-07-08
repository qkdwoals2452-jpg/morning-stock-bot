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

    for theme_data in results:

        theme = theme_data["theme"]
        ranked = theme_data["ranked"]

        msg += (
            f"🔥 {theme['name']}\n"
        )

        msg += (
            f"📊 점수 "
            f"{theme['score']}\n"
        )

        msg += (
            f"🧠 "
            f"{theme['reason']}\n\n"
        )

        msg += (
            "🏆 추천 TOP5\n"
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
                f"   AI점수 "
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
        f"저장일수 : "
        f"{project_status['saved_days']}일\n"
    )

    msg += (
        f"누적 추천테마 : "
        f"{project_status['saved_themes']}개\n"
    )

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
