from __future__ import annotations

import html
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bandju_api import BandjuAPI

load_dotenv("/etc/bandju-telegram-bot/.env")
DB_PATH = Path("/var/lib/bandju-telegram-bot/bot.db")
DEFAULT_DAYS = int(os.getenv("DEFAULT_DAYS", "30"))
PROTOCOL = os.getenv("VPN_PROTOCOL", "amneziawg")
MUTATIONS_ENABLED = os.getenv("BANDJU_MUTATIONS_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}

api = BandjuAPI()


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute(
        """CREATE TABLE IF NOT EXISTS users(
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        access_id TEXT,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )"""
    )
    c.commit()
    return c


def get_user(uid: int):
    c = db()
    row = c.execute("SELECT * FROM users WHERE telegram_id=?", (uid,)).fetchone()
    c.close()
    return row


def save_user(uid: int, username: str, access_id: str):
    c = db()
    c.execute(
        """INSERT INTO users(telegram_id,username,access_id)
        VALUES(?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,access_id=excluded.access_id""",
        (uid, username, access_id),
    )
    c.commit()
    c.close()


def admin(uid: int) -> bool:
    ids = {int(x.strip()) for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip().isdigit()}
    return uid in ids


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Получить VPN", callback_data="get")],
        [InlineKeyboardButton("📱 Мой доступ", callback_data="my"),
         InlineKeyboardButton("♻️ Продлить", callback_data="renew")],
        [InlineKeyboardButton("🩺 Проверка", callback_data="health")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")],
    ])


def extract_access_id(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in ("id", "access_id", "accessId", "uuid", "token", "client_id"):
            if data.get(key) is not None:
                return str(data[key])
        for key in ("access", "client", "data", "obj"):
            value = data.get(key)
            found = extract_access_id(value)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            found = extract_access_id(item)
            if found:
                return found
    return None


def extract_connection(data: Any) -> str | None:
    if isinstance(data, dict):
        keys = ("subscription_url", "subscriptionUrl", "sub_url", "subUrl",
                "url", "link", "config", "vpn_url", "vpnUrl", "connection")
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        for value in data.values():
            found = extract_connection(value)
            if found:
                return found
    if isinstance(data, list):
        for value in data:
            found = extract_connection(value)
            if found:
                return found
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "только проверка и просмотр" if not MUTATIONS_ENABLED else "управление доступом"
    await update.message.reply_text(
        "🚀 <b>Bandju VPN Bot</b>\n\n"
        "Режим: <b>" + mode + "</b>\n"
        "Бот работает через локальный API Bandju Panel.",
        parse_mode="HTML",
        reply_markup=keyboard(),
    )


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = await api.health()
    message = update.effective_message
    if not message:
        return
    if r.ok:
        await message.reply_text("🟢 Bandju API доступен.\n\n" + html.escape(json.dumps(r.data, ensure_ascii=False)[:1500]))
    else:
        await message.reply_text("🔴 Bandju API недоступен.\n" + html.escape(r.error))


async def get_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not MUTATIONS_ENABLED:
        await update.effective_message.reply_text(
            "🔒 Создание VPN временно отключено.\n"
            "Сейчас бот работает в безопасном режиме и ничего не изменяет в Bandju Panel.",
            reply_markup=keyboard(),
        )
        return

    uid = update.effective_user.id
    username = update.effective_user.username or ""
    existing = get_user(uid)

    if existing and existing["access_id"]:
        await update.effective_message.reply_text(
            "У вас уже есть доступ. Используйте «Мой доступ» или «Продлить».",
            reply_markup=keyboard(),
        )
        return

    payload = {
        "name": f"tg-{uid}",
        "remark": f"Telegram {username or uid}",
        "protocol": PROTOCOL,
        "days": DEFAULT_DAYS,
        "telegram_id": uid,
    }
    r = await api.create_access(payload)
    if not r.ok:
        await update.effective_message.reply_text(
            "❌ Не удалось создать доступ.\n\n"
            "API Bandju не подтвердил операцию. Проверьте endpoint в .env.",
            reply_markup=keyboard(),
        )
        return

    access_id = extract_access_id(r.data)
    connection = extract_connection(r.data)
    if not access_id:
        await update.effective_message.reply_text(
            "⚠️ Bandju вернул ответ, но бот не смог определить ID доступа.",
            reply_markup=keyboard(),
        )
        return

    save_user(uid, username, access_id)
    text = "✅ <b>VPN-доступ создан</b>\n\nСрок: " + str(DEFAULT_DAYS) + " дней."
    if connection:
        text += "\n\n<code>" + html.escape(connection) + "</code>"
    await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=keyboard())


async def my_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    if not user or not user["access_id"]:
        await update.effective_message.reply_text("У вас ещё нет VPN-доступа.", reply_markup=keyboard())
        return

    r = await api.get_access(user["access_id"])
    if not r.ok:
        await update.effective_message.reply_text("❌ Не удалось получить данные доступа.", reply_markup=keyboard())
        return

    connection = extract_connection(r.data)
    text = "📱 <b>Мой VPN-доступ</b>\n\nID: <code>" + html.escape(user["access_id"]) + "</code>"
    if connection:
        text += "\n\n" + html.escape(connection)
    await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=keyboard())


async def renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not MUTATIONS_ENABLED:
        await update.effective_message.reply_text(
            "🔒 Продление временно отключено.\n"
            "Сейчас бот не выполняет никаких изменений в Bandju Panel.",
            reply_markup=keyboard(),
        )
        return

    uid = update.effective_user.id
    user = get_user(uid)
    if not user or not user["access_id"]:
        await update.effective_message.reply_text("Сначала получите VPN-доступ.", reply_markup=keyboard())
        return

    r = await api.renew_access(user["access_id"], DEFAULT_DAYS)
    if r.ok:
        await update.effective_message.reply_text(
            f"♻️ Доступ продлён ещё на {DEFAULT_DAYS} дней.",
            reply_markup=keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            "❌ Не удалось продлить доступ. Проверьте endpoint Bandju API.",
            reply_markup=keyboard(),
        )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "get":
        await get_vpn(update, context)
    elif q.data == "my":
        await my_access(update, context)
    elif q.data == "renew":
        await renew(update, context)
    elif q.data == "health":
        await health(update, context)
    elif q.data == "help":
        await q.message.reply_text(
            "ℹ️ <b>Команды</b>\n/start — меню\n/vpn — получить доступ\n/my — мой доступ\n/renew — продлить\n/health — проверка API",
            parse_mode="HTML",
            reply_markup=keyboard(),
        )


async def admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin(update.effective_user.id):
        return
    r = await api.discover()
    if r:
        paths = list((r["openapi"].get("paths") or {}).keys())
        msg = "🛠 <b>Bandju API</b>\n\n" + "\n".join(paths[:100])
    else:
        msg = "⚠️ OpenAPI schema не найдена. Безопасный режим остаётся включённым."
    await update.message.reply_text(msg, parse_mode="HTML")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not configured")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("vpn", get_vpn))
    app.add_handler(CommandHandler("my", my_access))
    app.add_handler(CommandHandler("renew", renew))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("bandjuapi", admin_status))
    app.add_handler(CallbackQueryHandler(callback))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
