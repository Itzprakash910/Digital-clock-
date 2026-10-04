import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import db
from config import ADMIN_IDS

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))


@router.message(Command("admin"))
async def admin(m: Message):
    await m.answer("🛠 <b>Admin</b>\n/totalusers\n/userinfo id\n/ban id\n/unban id\n"
                   "/verify id\n/givepremium id days\n/broadcast text")


@router.message(Command("totalusers"))
async def total(m: Message):
    s = await db.stats_global()
    await m.answer(f"👥 Users: {s['users']}\n✅ Profiles: {s['profiles']}\n💎 Premium: {s['premium']}\n"
                   f"👆 Swipes: {s['swipes']}\n💳 Payments: {s['payments']}")


@router.message(Command("userinfo"))
async def userinfo(m: Message, command: CommandObject):
    try:
        u = await db.get_user(int(command.args))
    except Exception:
        return await m.answer("Usage: /userinfo id")
    await m.answer(str(u) if u else "Not found")


@router.message(Command("ban", "unban"))
async def ban(m: Message, command: CommandObject):
    try:
        uid = int(command.args)
    except Exception:
        return await m.answer("Usage: /ban id")
    val = 1 if m.text.startswith("/ban") else 0
    await db.update_user(uid, banned=val)
    await m.answer("🚫 Banned" if val else "✅ Unbanned")


@router.message(Command("verify"))
async def verify(m: Message, command: CommandObject):
    await db.update_user(int(command.args), verified=1)
    await m.answer("✅ Verified badge diya")


@router.message(Command("givepremium"))
async def give(m: Message, command: CommandObject):
    try:
        uid, days = command.args.split()
        await db.extend_premium(int(uid), int(days))
        await m.answer("💎 Done")
    except Exception:
        await m.answer("Usage: /givepremium id days")


@router.message(Command("broadcast"))
async def broadcast(m: Message, command: CommandObject, bot: Bot):
    if not command.args:
        return await m.answer("Usage: /broadcast text")
    ok = 0
    for uid in await db.all_user_ids():
        try:
            await bot.send_message(uid, command.args)
            ok += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await m.answer(f"📢 Sent: {ok}")
