import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, Message, CallbackQuery

import db
from config import BOT_TOKEN, START_DELAY
from handlers import profile, discover, extras, premium, admin, system, chat, posts, filters

# Jin commands/buttons ke liye complete profile chahiye
NEEDS_PROFILE_CMDS = {"find", "myprofile", "editprofile", "matches", "likes", "dailypick", "nearby",
                      "mood", "icebreaker", "daily", "boost", "coins", "refer", "premium", "stats", "posts", "contacts", "setcontacts", "filters"}
NEEDS_PROFILE_CB = {"m", "sw", "ed", "mood", "pay", "coinbuy", "posts", "flt"}


class TrackMiddleware(BaseMiddleware):
    """Har user ko DB me save/update karta hai, ban check aur profile gate lagata hai."""

    async def __call__(self, handler, event, data):
        tg = data.get("event_from_user")
        if tg is None or tg.is_bot:
            return await handler(event, data)

        is_start = isinstance(event, Message) and (event.text or "").startswith("/start")
        u = await db.get_user(tg.id)
        if u is None:
            if not is_start:  # /start me referral handle hota hai
                await db.create_user(tg)
                u = await db.get_user(tg.id)
        else:
            await db.touch_user(tg)

        if u and u["banned"]:
            if isinstance(event, CallbackQuery):
                await event.answer("🚫 Aap banned hain.", show_alert=True)
            return

        if not (u and u["profile_done"]):
            if isinstance(event, Message) and (event.text or "").startswith("/"):
                cmd = event.text.split()[0][1:].split("@")[0].lower()
                if cmd in NEEDS_PROFILE_CMDS:
                    await event.answer("Pehle /start se profile banayein.")
                    return
            if isinstance(event, CallbackQuery) and event.data and \
                    event.data.split(":")[0] in NEEDS_PROFILE_CB:
                await event.answer("Pehle /start se profile banayein.", show_alert=True)
                return
        return await handler(event, data)


async def start_web():
    """Render Web Service ke liye health server (port binding)."""
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
    logging.info("Database ready (%s)", "MongoDB" if getattr(db, "USE_MONGO", False) else ("PostgreSQL" if getattr(db, "USE_PG", False) else "SQLite"))
    await start_web()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(TrackMiddleware())
    dp.callback_query.outer_middleware(TrackMiddleware())
    dp.include_routers(admin.router, premium.router, profile.router,
                       extras.router, discover.router, filters.router, posts.router, chat.router, system.router)

    # ConnectMate branding metadata; BotFather can override these values.
    try:
        await bot.set_my_name(name=os.getenv("BOT_NAME", "ConnectMate"))
        await bot.set_my_short_description(
            short_description=os.getenv("BOT_SHORT_DESCRIPTION", "💘 ConnectMate — Find your perfect match. Chat, match & connect safely.")
        )
        await bot.set_my_description(
            description=os.getenv("BOT_DESCRIPTION",
                "💘 ConnectMate is a Telegram dating & social matching bot. "
                "Create your profile, discover nearby people, Like/Skip, get mutual matches, "
                "chat privately, add up to 4 profile posts, refer friends and unlock Premium features.")
        )
    except Exception:
        logging.exception("Bot metadata update failed")

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
        BotCommand(command="posts", description="📸 Manage profile posts"),
        BotCommand(command="filters", description="⚙️ Discover filters"),
        BotCommand(command="contacts", description="🔐 Premium contact settings"),
        BotCommand(command="setcontacts", description="🔐 Set contact details"),
        BotCommand(command="chat", description="💬 Chat help"),
        BotCommand(command="endchat", description="🛑 End current chat"),
        BotCommand(command="deleteprofile", description="🗑 Delete profile"),
        BotCommand(command="help", description="📚 Help"),
    ])

    # Render deploy me purana instance band hone do (TelegramConflictError se bachne ke liye)
    if START_DELAY > 0:
        logging.info("Waiting %ss before polling (old instance shutdown)...", START_DELAY)
        await asyncio.sleep(START_DELAY)

    # pending updates drop NAHI karte (payments/messages na khoyen)
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())
