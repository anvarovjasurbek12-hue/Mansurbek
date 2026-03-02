import os
import sqlite3
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, Tuple

import requests
import yt_dlp
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse


BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

ADMIN_LOGIN = "mamurbek"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Qw9!zP4nLm2@xB")  # можно поменять в переменных окружения
ADMIN_COOKIE_NAME = "mamurbek_admin"

DB_PATH = Path(os.getenv("DB_PATH", "mamurbeksave.db"))
_DB_LOCK = Lock()


if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    # Лучше сразу упасть при отсутствии токена
    raise RuntimeError(
        "TELEGRAM_TOKEN не задан. Установите переменную окружения TELEGRAM_TOKEN на Render."
    )


app = FastAPI(title="MamurbekSave Bot Backend")


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                blocked INTEGER DEFAULT 0,
                request_count INTEGER DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def record_user(chat: Dict[str, Any]) -> None:
    chat_id = chat.get("id")
    if not chat_id:
        return

    username = chat.get("username")
    first_name = chat.get("first_name")
    last_name = chat.get("last_name")

    with _DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO users (chat_id, username, first_name, last_name, request_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                request_count=request_count + 1,
                last_seen=CURRENT_TIMESTAMP
            """,
            (chat_id, username, first_name, last_name),
        )
        conn.commit()


def is_blocked(chat_id: int) -> bool:
    with _DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT blocked FROM users WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        return bool(row and row[0])


def get_stats() -> Tuple[int, int, list]:
    with _DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(request_count), 0) AS r FROM users")
        row = cur.fetchone()
        total_users = int(row["c"])
        total_requests = int(row["r"])

        cur.execute(
            """
            SELECT chat_id, username, first_name, last_name, request_count, blocked, last_seen
            FROM users
            ORDER BY request_count DESC, last_seen DESC
            LIMIT 200
            """
        )
        users = [dict(r) for r in cur.fetchall()]

    return total_users, total_requests, users


_init_db()


def download_video(url: str) -> Path:
    """
    Скачивает видео через yt-dlp и возвращает путь к файлу.
    Ограничиваем размер/формат, чтобы Telegram принял файл.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="mamurbeksave_"))

    ydl_opts = {
        "outtmpl": str(tmp_dir / "%(title).80s.%(ext)s"),
        "format": "mp4[filesize<50M]/best[filesize<50M]/mp4/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = Path(ydl.prepare_filename(info))

    # иногда расширение может отличаться
    if not file_path.exists():
        # пробуем найти любой файл в папке
        candidates = list(tmp_dir.glob("*"))
        if not candidates:
            raise RuntimeError("Видео не удалось скачать")
        file_path = candidates[0]

    return file_path


def send_telegram_message(chat_id: int, text: str) -> None:
    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=40,
    )


def send_telegram_video(chat_id: int, file_path: Path, caption: Optional[str] = None) -> None:
    with file_path.open("rb") as f:
        files = {"video": f}
        data: Dict[str, Any] = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        requests.post(
            f"{TELEGRAM_API_URL}/sendVideo",
            data=data,
            files=files,
            timeout=120,
        )


@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "MamurbekSavebot backend ishga tushdi."


@app.post("/webhook")
async def telegram_webhook(update: Dict[str, Any]):
    """
    Основной обработчик Telegram webhook.
    На Render нужно будет указать URL вида:
    https://mamurbeksave.onrender.com/webhook
    """
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text") or ""

    if not chat_id:
        return {"ok": True}

    # сохраняем/обновляем информацию о пользователе
    record_user(chat)

    # проверяем, не заблокирован ли пользователь
    if is_blocked(chat_id):
        send_telegram_message(
            chat_id,
            "Siz uchun bu botdan foydalanish taqiqlangan.",
        )
        return {"ok": True}

    text = text.strip()

    # Команда /start
    if text.startswith("/start"):
        send_telegram_message(
            chat_id,
            "Assalomu alaykum! 👋\n\n"
            "Men — MamurbekSavebot.\n"
            "Menga YouTube yoki Instagram havolasini yuboring, "
            "men esa sizga videoni yuklab beraman.\n\n"
            "Masalan:\n"
            "https://youtube.com/...\n"
            "https://www.instagram.com/reel/...",
        )
        return {"ok": True}

    # Простейшая проверка на ссылку
    if "http://" not in text and "https://" not in text:
        send_telegram_message(
            chat_id,
            "Iltimos, menga YouTube yoki Instagram videoning to‘liq havolasini yuboring.",
        )
        return {"ok": True}

    url = text.split()[0]

    send_telegram_message(chat_id, "⏳ Video yuklab olinmoqda, biroz kuting…")

    try:
        file_path = download_video(url)
    except Exception:
        send_telegram_message(
            chat_id,
            "Kechirasiz, videoni yuklab bo‘lmadi. "
            "Havolani tekshirib, keyinroq yana urinib ko‘ring.",
        )
        return {"ok": True}

    try:
        send_telegram_video(chat_id, file_path, caption="Videongiz tayyor ✅")
    except Exception:
        send_telegram_message(
            chat_id,
            "Video yuklab olindi, lekin uni yuborishda xatolik yuz berdi. "
            "Keyinroq yana urinib ko‘ring.",
        )
    finally:
        # Удаляем временный файл/директорию
        try:
            for p in file_path.parent.glob("*"):
                p.unlink(missing_ok=True)
            file_path.parent.rmdir()
        except Exception:
            pass

    return {"ok": True}


def get_admin_logged_in(admin_cookie: Optional[str] = Cookie(default=None, alias=ADMIN_COOKIE_NAME)) -> bool:
    return admin_cookie == "1"


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, logged_in: bool = Depends(get_admin_logged_in)):
    if not logged_in:
        return HTMLResponse(
            """
            <html>
              <head><title>MamurbekSave Admin</title></head>
              <body style="font-family: sans-serif;">
                <h2>Kirish</h2>
                <form method="post">
                  <label>Login: <input type="text" name="login" /></label><br/><br/>
                  <label>Parol: <input type="password" name="password" /></label><br/><br/>
                  <button type="submit">Kirish</button>
                </form>
              </body>
            </html>
            """,
            status_code=200,
        )

    total_users, total_requests, users = get_stats()

    rows_html = ""
    for u in users:
        blocked_label = "Ha" if u["blocked"] else "Yo‘q"
        action_link = (
            f'<a href="/admin/block?chat_id={u["chat_id"]}">Bloklash</a>'
            if not u["blocked"]
            else f'<a href="/admin/unblock?chat_id={u["chat_id"]}">Blokdan yechish</a>'
        )
        rows_html += f"""
        <tr>
          <td>{u["chat_id"]}</td>
          <td>{u.get("username") or "-"}</td>
          <td>{u.get("first_name") or ""} {u.get("last_name") or ""}</td>
          <td>{u["request_count"]}</td>
          <td>{blocked_label}</td>
          <td>{action_link}</td>
        </tr>
        """

    html = f"""
    <html>
      <head>
        <title>MamurbekSave Admin</title>
      </head>
      <body style="font-family: sans-serif; padding: 20px;">
        <h1>MamurbekSavebot — Admin panel</h1>
        <p>Bot hozircha ishlamoqda ✅</p>
        <h3>Statistika</h3>
        <ul>
          <li>Foydalanuvchilar soni: <b>{total_users}</b></li>
          <li>Jami so‘rovlar: <b>{total_requests}</b></li>
        </ul>
        <h3>Foydalanuvchilar ro‘yxati (eng faol 200 ta)</h3>
        <table border="1" cellpadding="5" cellspacing="0">
          <thead>
            <tr>
              <th>Chat ID</th>
              <th>Username</th>
              <th>Ism</th>
              <th>So‘rovlar soni</th>
              <th>Bloklangan</th>
              <th>Harakat</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </body>
    </html>
    """

    return HTMLResponse(html, status_code=200)


@app.post("/admin", response_class=HTMLResponse)
async def admin_login(
    response: Response,
    login: str = Form(...),
    password: str = Form(...),
):
    if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        resp = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        resp.set_cookie(
            key=ADMIN_COOKIE_NAME,
            value="1",
            httponly=True,
            secure=True,
            samesite="lax",
        )
        return resp

    return HTMLResponse(
        """
        <html>
          <head><title>MamurbekSave Admin</title></head>
          <body style="font-family: sans-serif;">
            <h2>Kirish</h2>
            <p style="color:red;">Login yoki parol noto‘g‘ri.</p>
            <form method="post">
              <label>Login: <input type="text" name="login" /></label><br/><br/>
              <label>Parol: <input type="password" name="password" /></label><br/><br/>
              <button type="submit">Kirish</button>
            </form>
          </body>
        </html>
        """,
        status_code=401,
    )


@app.get("/admin/block")
async def admin_block(chat_id: int, logged_in: bool = Depends(get_admin_logged_in)):
    if not logged_in:
        raise HTTPException(status_code=403, detail="Not authorized")

    with _DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET blocked = 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()

    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)


@app.get("/admin/unblock")
async def admin_unblock(chat_id: int, logged_in: bool = Depends(get_admin_logged_in)):
    if not logged_in:
        raise HTTPException(status_code=403, detail="Not authorized")

    with _DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET blocked = 0 WHERE chat_id = ?", (chat_id,))
        conn.commit()

    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)


@app.get("/healthz", response_class=PlainTextResponse)
async def healthcheck() -> str:
    return "ok"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)

