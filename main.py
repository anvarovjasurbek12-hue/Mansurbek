import os
import threading

from bot import run_bot
from admin import app


def main() -> None:
    # Запускаем Telegram-бота в отдельном потоке (polling)
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Запускаем Flask-админку
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()