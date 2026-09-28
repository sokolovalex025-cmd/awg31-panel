import io
import qrcode
from datetime import datetime, timedelta, timezone
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from .config import settings
from .xui import XUIClient

router = Router()

def menu():
    b = InlineKeyboardBuilder()
    b.button(text="🔐 Подключиться", callback_data="connect")
    b.button(text="🎁 Пробный период", callback_data="trial")
    b.button(text="💳 Тарифы", callback_data="plans")
    b.button(text="👤 Мой аккаунт", callback_data="profile")
    b.button(text="🆘 Помощь", callback_data="help")
    b.adjust(2, 2, 1)
    return b.as_markup()

def plans():
    b = InlineKeyboardBuilder()
    b.button(text=f"7 дней — {settings.plan_7} ⭐", callback_data="buy:7")
    b.button(text=f"30 дней — {settings.plan_30} ⭐", callback_data="buy:30")
    b.button(text=f"90 дней — {settings.plan_90} ⭐", callback_data="buy:90")
    b.adjust(1)
    return b.as_markup()

@router.message(CommandStart())
async def start(m: Message, db):
    db.upsert_user(m.from_user)
    await m.answer("🛡 <b>NOVA VPN</b>\n\nБыстрое подключение к VPN без ручного ввода конфигурации.", reply_markup=menu())

@router.callback_query(F.data == "help")
async def help_cb(c: CallbackQuery):
    await c.message.edit_text("🆘 <b>Помощь</b>\n\nВыберите «Подключиться», получите VLESS-конфигурацию и импортируйте её в совместимый клиент.", reply_markup=menu())

@router.callback_query(F.data == "plans")
async def plans_cb(c: CallbackQuery):
    await c.message.edit_text("💳 <b>Тарифы</b>\n\nОплата выполняется через Telegram Stars.", reply_markup=plans())

@router.callback_query(F.data == "profile")
async def profile_cb(c: CallbackQuery, db):
    row = db.latest_subscription(c.from_user.id)
    if not row:
        text = "👤 <b>Аккаунт</b>\n\nАктивной подписки нет."
    else:
        exp = datetime.fromisoformat(row["expires_at"]).astimezone(timezone.utc)
        text = f"👤 <b>Аккаунт</b>\n\nПротокол: VLESS\nДействует до: <code>{exp:%Y-%m-%d %H:%M} UTC</code>"
    await c.message.edit_text(text, reply_markup=menu())

@router.callback_query(F.data == "trial")
async def trial_cb(c: CallbackQuery, db):
    if db.trial_used(c.from_user.id):
        await c.answer("Пробный период уже использован", show_alert=True)
        return
    try:
        expires = datetime.now(timezone.utc) + timedelta(days=settings.trial_days)
        email = f"tg-{c.from_user.id}-trial"
        async with XUIClient(settings) as xui:
            cid = await xui.add_vless_client(email, int(expires.timestamp()*1000))
            config = await xui.create_config(cid)
        db.add_subscription(c.from_user.id, cid, email, config, expires.isoformat())
        db.mark_trial(c.from_user.id)
        await send_config(c.message, config, expires)
    except Exception as e:
        await c.message.answer(f"❌ Не удалось создать конфигурацию: <code>{e}</code>")
    await c.answer()

@router.callback_query(F.data == "connect")
async def connect_cb(c: CallbackQuery, db):
    row = db.latest_subscription(c.from_user.id)
    if not row:
        await c.message.edit_text("Сначала активируйте пробный период или купите тариф.", reply_markup=plans())
        await c.answer()
        return
    exp = datetime.fromisoformat(row["expires_at"])
    await send_config(c.message, row["config"], exp)
    await c.answer()

@router.callback_query(F.data.startswith("buy:"))
async def buy_cb(c: CallbackQuery):
    days = int(c.data.split(":")[1])
    stars = {7: settings.plan_7, 30: settings.plan_30, 90: settings.plan_90}[days]
    await c.message.answer_invoice(title=f"VPN на {days} дней", description="VPN-доступ NOVA VPN", payload=f"vpn:{days}", currency="XTR", prices=[LabeledPrice(label=f"{days} дней", amount=stars)])
    await c.answer()

@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(m: Message, db):
    payment = m.successful_payment
    days = int(payment.invoice_payload.split(":")[1])
    existing = db.latest_subscription(m.from_user.id)
    if existing:
        exp = db.extend(m.from_user.id, days)
        db.add_payment(m.from_user.id, days, payment.total_amount, payment.telegram_payment_charge_id)
        await m.answer(f"✅ Оплата получена. Подписка продлена до {exp:%Y-%m-%d %H:%M} UTC.", reply_markup=menu())
        return
    exp = datetime.now(timezone.utc) + timedelta(days=days)
    email = f"tg-{m.from_user.id}-{int(datetime.now().timestamp())}"
    try:
        async with XUIClient(settings) as xui:
            cid = await xui.add_vless_client(email, int(exp.timestamp()*1000))
            config = await xui.create_config(cid)
        db.add_subscription(m.from_user.id, cid, email, config, exp.isoformat())
        db.add_payment(m.from_user.id, days, payment.total_amount, payment.telegram_payment_charge_id)
        await send_config(m, config, exp)
    except Exception as e:
        await m.answer(f"⚠️ Оплата получена, но создание VPN не завершилось: <code>{e}</code>")

async def send_config(message, config, expires):
    img = qrcode.make(config)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    await message.answer_photo(BufferedInputFile(buf.getvalue(), filename="nova-vpn.png"), caption=f"🔐 <b>VPN готов</b>\n\nСрок: <code>{expires:%Y-%m-%d %H:%M} UTC</code>\n\n<b>VLESS:</b>\n<code>{config}</code>")
