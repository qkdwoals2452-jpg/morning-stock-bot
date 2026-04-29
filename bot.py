import telegram
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1648839639"

def main():
    bot = telegram.Bot(token=TOKEN)
    bot.send_message(chat_id=CHAT_ID, text="🔥 진짜 테스트 성공")

if __name__ == "__main__":
    main()
