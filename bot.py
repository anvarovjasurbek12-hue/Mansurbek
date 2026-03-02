import os
import logging
import asyncio
import json
import glob
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "8516985342:AAEyMOGpMzHMCmAzpVOIvxLIkn6iuRkaP-0")

stats = {
    "total_users": set(),
    "total_downloads": 0,
    "download_history": []
}

def save_stats():
    try:
        with open("stats.json", "w") as f:
            json.dump({
                "total_users": list(stats["total_users"]),
                "total_downloads": stats["total_downloads"],
                "download_history": stats["download_history"][-200:]
            }, f)
    except Exception as e:
        logger.error(f"Save stats error: {e}")

def load_stats():
    try:
        with open("stats.json", "r") as f:
            data = json.load(f)
            stats["total_users"] = set(data.get("total_users", []))
            stats["total_downloads"] = data.get("total_downloads", 0)
            stats["download_history"] = data.get("download_history", [])
    except:
        pass

load_stats()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats["total_users"].add(user.id)
    save_stats()

    keyboard = [
        [InlineKeyboardButton("📥 Qanday ishlatish?", callback_data="help")],
        [InlineKeyboardButton("ℹ️ Bot haqida", callback_data="about")]
    ]

    await update.message.reply_text(
        f"👋 Salom, *{user.first_name}*!\n\n"
        "🤖 *MamurbekSavebot* ga xush kelibsiz!\n\n"
        "📱 Men quyidagi platformalardan video yuklab beraman:\n"
        "🎬 YouTube\n"
        "📸 Instagram\n"
        "🎵 TikTok\n\n"
        "📎 *Video linkini yuboring — men yuklab beraman!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Qanday ishlatish kerak?*\n\n"
        "1️⃣ Video linkini nusxalang\n"
        "2️⃣ Linkni menga yuboring\n"
        "3️⃣ Video yuklanishini kuting\n\n"
        "✅ *Qo'llab-quvvatlanadigan saytlar:*\n"
        "• youtube.com / youtu.be\n"
        "• instagram.com\n"
        "• tiktok.com\n\n"
        "⚠️ *Eslatma:* 50MB dan katta videolar yuklanmaydi"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *MamurbekSavebot*\n\n"
        "📌 Versiya: 1.0\n"
        "👨‍💻 Yaratuvchi: Mamurbek\n\n"
        f"👥 Foydalanuvchilar: *{len(stats['total_users'])}*\n"
        f"📥 Jami yuklashlar: *{stats['total_downloads']}*"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "help":
        await help_cmd(update, context)
    elif update.callback_query.data == "about":
        await about_cmd(update, context)

def is_valid_url(text):
    domains = ["youtube.com", "youtu.be", "instagram.com", "tiktok.com", "vm.tiktok.com"]
    return any(d in text.lower() for d in domains)

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user = update.effective_user

    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ *Noto'g'ri havola!*\n\n"
            "✅ Quyidagi saytlardan link yuboring:\n"
            "• YouTube\n• Instagram\n• TikTok",
            parse_mode="Markdown"
        )
        return

    stats["total_users"].add(user.id)
    msg = await update.message.reply_text("⏳ Video tayyorlanmoqda, biroz kuting...")

    try:
        ydl_opts = {
            "format": "best[ext=mp4][filesize<50M]/best[filesize<50M]/best",
            "outtmpl": "/tmp/%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
        }

        loop = asyncio.get_event_loop()

        def do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = await loop.run_in_executor(None, do_download)
        title = info.get("title", "Video")
        vid_id = info.get("id", "video")
        ext = info.get("ext", "mp4")
        filename = f"/tmp/{vid_id}.{ext}"

        if not os.path.exists(filename):
            files = glob.glob(f"/tmp/{vid_id}.*")
            if files:
                filename = files[0]

        if not os.path.exists(filename):
            raise FileNotFoundError("Fayl topilmadi")

        file_size_mb = os.path.getsize(filename) / (1024 * 1024)

        if file_size_mb > 50:
            await msg.edit_text("❌ Video hajmi 50MB dan katta. Qisqaroq video yuboring.")
            os.remove(filename)
            return

        await msg.edit_text(f"📤 Jo'natilmoqda...\n📌 {title[:60]}")

        with open(filename, "rb") as vf:
            await update.message.reply_video(
                video=vf,
                caption=f"📥 *{title[:100]}*\n\n🤖 @MamurbekSavebot",
                parse_mode="Markdown",
                supports_streaming=True
            )

        os.remove(filename)

        stats["total_downloads"] += 1
        stats["download_history"].append({
            "user_id": user.id,
            "username": user.username or user.first_name,
            "url": url,
            "title": title,
            "size_mb": round(file_size_mb, 2),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        save_stats()
        await msg.delete()

    except Exception as e:
        logger.error(f"Download error: {e}")
        err = str(e).lower()
        if "private" in err or "login" in err:
            text = "❌ Bu video *xususiy* (private). Ochiq video havolasini yuboring."
        elif "not available" in err or "unavailable" in err:
            text = "❌ Bu video mavjud emas yoki o'chirilgan."
        elif "file not found" in err:
            text = "❌ Video yuklab bo'lmadi. Boshqa havolani sinab ko'ring."
        else:
            text = "❌ Xatolik yuz berdi. Iltimos, boshqa havolani sinab ko'ring."
        await msg.edit_text(text, parse_mode="Markdown")


def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    logger.info("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)