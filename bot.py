import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import db
from config import BOT_TOKEN
from handlers import profile, discover, extras, premium, admin


class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            u = await db.get_user(user.id)
            if u and u["banned"]:
                return
        return await handler(event, data)


async def start_web():
    """Render Web Service ke liye dummy HTTP server (port binding)."""
    async def health(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info("Web server started on port %s", port)


async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init_db()
    await start_web()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())
    dp.include_routers(admin.router, premium.router, profile.router,
                       extras.router, discover.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="🚀 Start"),
        BotCommand(command="find", description="🔥 Discover"),
        BotCommand(command="myprofile", description="👤 My profile"),
        BotCommand(command="editprofile", description="✏️ Edit profile"),
        BotCommand(command="matches", description="💞 Matches"),
        BotCommand(command="likes", description="👀 Who liked me"),
        BotCommand(command="dailypick", description="🌟 Daily picks"),
        BotCommand(command="nearby", description="📍 Nearby"),
        BotCommand(command="mood", description="🎭 Set mood"),
        BotCommand(command="icebreaker", description="🧊 Icebreaker"),
        BotCommand(command="daily", description="🎁 Daily reward"),
        BotCommand(command="boost", description="🚀 Boost"),
        BotCommand(command="coins", description="🪙 Coins & refer"),
        BotCommand(command="premium", description="💎 Premium"),
        BotCommand(command="stats", description="📊 Stats"),
        BotCommand(command="help", description="📚 Help"),
    ])

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
