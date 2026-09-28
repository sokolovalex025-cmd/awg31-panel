import asyncio
from contextlib import suppress
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from nurvpn_bot.bot import router
from nurvpn_bot.config import settings
from nurvpn_bot.db import DB
from nurvpn_bot.web import app

async def run_bot():
    if not settings.bot_token or settings.bot_token.startswith("PUT_"):
        raise RuntimeError("BOT_TOKEN is not configured")
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["db"] = DB(settings.db_path)
    dp.include_router(router)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

async def run_web():
    config = uvicorn.Config(app, host=settings.web_host, port=settings.web_port, log_level="info")
    await uvicorn.Server(config).serve()

async def main():
    await asyncio.gather(run_bot(), run_web())

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
