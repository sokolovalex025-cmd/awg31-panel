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
MUTATIONS_ENABLED = os.getenv("BANDJU_MUTATIONS_ENABLED", "0").strip().lower() in {
    "1", "true", "yes", "on",
}
BANDJU_CONTAINER = os.getenv("BANDJU_CONTAINER", "").strip()

api = BandjuAPI()


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users(
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            client_name TEXT,
            access_id TEXT,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )"""
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "client_name" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN client_name TEXT")
    if "access_id" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN access_id TEXT")

    rows = conn.execute(
        "SELECT telegram_id, access_id FROM users "
        "WHERE (client_name IS NULL OR client_name='') AND access_id IS NOT NULL"
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE users SET client_name=? WHERE telegram_id=?",
            (str(row["access_id"]), row["telegram_id"]),
        )

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_client_name "
        "ON users(client_name) WHERE client_name IS NOT NULL"
    )
    conn.commit()
    return conn


def get_user(uid: int):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (uid,)).fetchone()
    conn.close()
    return row


def save_user(uid: int, username: str, client_name: str) -> None:
    conn = db()
    conn.execute(
        """INSERT INTO users(telegram_id, username, client_name, access_id)
           VALUES(?,?,?,?)
           ON CONFLICT(telegram_id) DO UPDATE SET
             username=excluded.username,
             client_name=excluded.client_name,
             access_id=excluded.access_id""",
        (uid, username, client_name, client_name),
    )
    conn.commit()
    conn.close()


def clear_user(uid: int) -> None:
    conn = db()
    conn.execute("UPDATE users SET client_name=NULL, access_id=NULL WHERE telegram_id=?", (uid,))
    conn.commit()
    conn.close()


def admin(uid: int) -> bool:
    ids = {
        int(x.strip())
        for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
        if x.strip().isdigit()
    }
    return uid in ids


def mutations_blocked_text() -> str:
    return (
        "🔒 Изменение VPN сейчас отключено.\n"
        "Бот работает в безопасном режиме и не изменяет Bandju Panel."
    )


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Получить VPN", callback_data="get")],
        [
            InlineKeyboardButton("📱 Мой доступ", callback_data="my"),
            InlineKeyboardButton("♻️ Продлить", callback_data="renew"),
        ],
        [
            InlineKeyboardButton("🟢 Включить", callback_data="enable"),
            InlineKeyboardButton("🔴 Выключить", callback_data="disable"),
        ],
        [InlineKeyboardButton("🗑 Удалить доступ", callback_data="delete")],
        [InlineKeyboardButton("🩺 Проверка", callback_data="health")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")],
    ])


def delete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⚠️ Да, удалить", callback_data="delete_confirm"),
        InlineKeyboardButton("Отмена", callback_data="delete_cancel"),
    ]])


def _unwrap(data: Any) -> Any:
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def _client_from_data(data: Any, name: str) -> dict[str, Any] | None:
    value = _unwrap(data)
    if isinstance(value, dict):
        if str(value.get("name", "")) == name:
            return value
        for key in ("client", "item"):
            nested = value.get(key)
            if isinstance(nested, dict) and str(nested.get("name", "")) == name:
                return nested
        for key in ("clients", "items"):
            nested = value.get(key)
            if isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict) and str(item.get("name", "")) == name:
                        return item
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and str(item.get("name", "")) == name:
                return item
    return None


def extract_connection(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in (
            "config", "config_text", "configuration", "link",
            "subscription_url", "subscriptionUrl", "url",
        ):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("artifact", "access", "client", "data", "row"):
            found = extract_connection(data.get(key))
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = extract_connection(value)
            if found:
                return found
    return None


def safe_name(uid: int) -> str:
    return f"tg-{uid}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "просмотр" if not MUTATIONS_ENABLED else "управление"
    message = update.effective_message
    if not message:
        return
    await message.reply_text(
        "🚀 <b>Bandju VPN Bot</b>\n\n"
        f"Режим: <b>{mode}</b>\n"
        "Подключение выполняется через локальный API Bandju Panel.",
        parse_mode="HTML",
        reply_markup=keyboard(),
    )


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await api.health()
    message = update.effective_message
    if not message:
        return
    if result.ok:
        body = json.dumps(result.data, ensure_ascii=False, indent=2)[:1800]
        await message.reply_text(
            "🟢 <b>Bandju API доступен</b>\n\n<pre>"
            + html.escape(body)
            + "</pre>",
            parse_mode="HTML",
        )
    else:
        await message.reply_text(
            "🔴 <b>Bandju API недоступен</b>\n" + html.escape(result.error),
            parse_mode="HTML",
        )


async def get_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    if not MUTATIONS_ENABLED:
        await message.reply_text(mutations_blocked_text(), reply_markup=keyboard())
        return

    existing = get_user(user.id)
    if existing and existing["client_name"]:
        await message.reply_text(
            "У вас уже есть VPN-доступ. Откройте «Мой доступ».",
            reply_markup=keyboard(),
        )
        return

    client_name = safe_name(user.id)
    result = await api.create_amnezia_client(client_name, BANDJU_CONTAINER)
    if not result.ok:
        await message.reply_text(
            "❌ Bandju не создал клиента.\n\n"
            f"HTTP: {result.status_code}\n" + html.escape(result.error)[:1200],
            parse_mode="HTML",
            reply_markup=keyboard(),
        )
        return

    save_user(user.id, user.username or "", client_name)
    connection = extract_connection(result.data)
    text = (
        "✅ <b>VPN-доступ создан</b>\n\n"
        f"Клиент: <code>{html.escape(client_name)}</code>"
    )
    if connection:
        text += "\n\n<pre>" + html.escape(connection) + "</pre>"
    else:
        text += (
            "\n\nBandju создал клиента, но в ответе не найден текст конфигурации. "
            "Откройте «Мой доступ»."
        )
    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard())


async def my_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    row = get_user(user.id)
    if not row or not row["client_name"]:
        await message.reply_text("У вас ещё нет VPN-доступа.", reply_markup=keyboard())
        return

    client_name = row["client_name"]
    result = await api.get_amnezia_client(client_name, BANDJU_CONTAINER)
    if not result.ok:
        await message.reply_text(
            "❌ Клиент не найден в Bandju Panel.\n"
            "Возможно, он был удалён непосредственно в панели.",
            reply_markup=keyboard(),
        )
        return

    client = _client_from_data(result.data, client_name) or result.data
    body = json.dumps(client, ensure_ascii=False, indent=2)[:3500]
    connection = extract_connection(result.data)
    text = (
        "📱 <b>Мой VPN-доступ</b>\n\n"
        f"Клиент: <code>{html.escape(client_name)}</code>\n"
    )
    if isinstance(client, dict):
        if "enabled" in client:
            text += f"Статус: <b>{'включён' if client['enabled'] else 'выключен'}</b>\n"
        if client.get("ip"):
            text += f"IP: <code>{html.escape(str(client['ip']))}</code>\n"
    if connection:
        text += "\n<pre>" + html.escape(connection) + "</pre>"
    else:
        text += "\n\n<pre>" + html.escape(body) + "</pre>"
    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard())


async def renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    if not MUTATIONS_ENABLED:
        await message.reply_text(mutations_blocked_text(), reply_markup=keyboard())
        return
    await message.reply_text(
        "ℹ️ В Bandju 1.9.0 пока не найден подтверждённый API продления срока "
        "AmneziaWG-клиента. Я не буду отправлять непроверенный запрос.",
        reply_markup=keyboard(),
    )


async def toggle_client(update: Update, enabled: bool) -> None:
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    if not MUTATIONS_ENABLED:
        await message.reply_text(mutations_blocked_text(), reply_markup=keyboard())
        return

    row = get_user(user.id)
    if not row or not row["client_name"]:
        await message.reply_text("У вас нет VPN-доступа.", reply_markup=keyboard())
        return

    result = await api.toggle_amnezia_client(row["client_name"], enabled, BANDJU_CONTAINER)
    if result.ok:
        await message.reply_text(
            f"{'🟢' if enabled else '🔴'} Клиент "
            f"<code>{html.escape(row['client_name'])}</code> "
            f"{'включён' if enabled else 'выключен'}.",
            parse_mode="HTML",
            reply_markup=keyboard(),
        )
    else:
        await message.reply_text(
            "❌ Bandju не выполнил операцию.\n" + html.escape(result.error)[:1200],
            parse_mode="HTML",
            reply_markup=keyboard(),
        )


async def delete_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    if not MUTATIONS_ENABLED:
        await message.reply_text(mutations_blocked_text(), reply_markup=keyboard())
        return

    row = get_user(user.id)
    if not row or not row["client_name"]:
        await message.reply_text("У вас нет VPN-доступа.", reply_markup=keyboard())
        return

    await message.reply_text(
        f"⚠️ Удалить VPN-клиента <code>{html.escape(row['client_name'])}</code>?\n"
        "Действие необратимо.",
        parse_mode="HTML",
        reply_markup=delete_keyboard(),
    )


async def delete_client_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    message = query.message if query else None
    user = update.effective_user
    if not query or not message or not user:
        return
    await query.answer()

    if not MUTATIONS_ENABLED:
        await message.reply_text(mutations_blocked_text(), reply_markup=keyboard())
        return

    row = get_user(user.id)
    if not row or not row["client_name"]:
        await message.reply_text("У вас нет VPN-доступа.", reply_markup=keyboard())
        return

    client_name = row["client_name"]
    result = await api.delete_amnezia_client(client_name, BANDJU_CONTAINER)
    if result.ok:
        clear_user(user.id)
        await message.reply_text(
            "🗑 VPN-доступ удалён.",
            reply_markup=keyboard(),
        )
    else:
        await message.reply_text(
            "❌ Bandju не удалил клиента.\n" + html.escape(result.error)[:1200],
            parse_mode="HTML",
            reply_markup=keyboard(),
        )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if query.data == "get":
        await get_vpn(update, context)
    elif query.data == "my":
        await my_access(update, context)
    elif query.data == "renew":
        await renew(update, context)
    elif query.data == "enable":
        await toggle_client(update, True)
    elif query.data == "disable":
        await toggle_client(update, False)
    elif query.data == "delete":
        await delete_client(update, context)
    elif query.data == "delete_confirm":
        await delete_client_confirm(update, context)
    elif query.data == "delete_cancel":
        await query.message.reply_text("Отмена.", reply_markup=keyboard())
    elif query.data == "health":
        await health(update, context)
    elif query.data == "help":
        await query.message.reply_text(
            "ℹ️ <b>Команды</b>\n"
            "/start — меню\n"
            "/vpn — получить VPN\n"
            "/my — мой доступ\n"
            "/renew — продлить\n"
            "/health — проверить Bandju API",
            parse_mode="HTML",
            reply_markup=keyboard(),
        )


async def admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not admin(update.effective_user.id):
        return
    result = await api.status()
    if result.ok:
        body = json.dumps(result.data, ensure_ascii=False, indent=2)[:3000]
        await update.effective_message.reply_text(
            "<b>Bandju API status</b>\n<pre>" + html.escape(body) + "</pre>",
            parse_mode="HTML",
        )
    else:
        await update.effective_message.reply_text(
            "❌ " + html.escape(result.error),
            parse_mode="HTML",
        )


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
