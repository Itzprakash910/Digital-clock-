from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import db
import keyboards as k
from config import (FREE_LIKES_PER_DAY, FREE_SUPER_PER_DAY, PREMIUM_SUPER_PER_DAY, ADMIN_IDS)
from utils import card, is_premium, distance_km, compat

router = Router()


def link_for(u):
    return f"https://t.me/{u['username']}" if u.get("username") else f"tg://user?id={u['id']}"


async def show_next(bot: Bot, uid: int):
    u = await db.get_user(uid)
    if not u or not u["profile_done"]:
        return await bot.send_message(uid, "Pehle /start se profile banayein.")
    c = await db.get_candidate(u)
    if not c:
        return await bot.send_message(
            uid, "😴 Abhi koi nayi profile nahi. Thodi der baad aayein ya 🚀 /boost karein!",
            reply_markup=k.main_menu())
    await db.add_view(c["id"])
    await bot.send_photo(uid, c["photo"], caption=card(c, viewer=u), reply_markup=k.swipe_kb(c["id"]))


@router.message(Command("find"))
async def cmd_find(m: Message, bot: Bot):
    await show_next(bot, m.from_user.id)


async def notify_match(bot: Bot, a, b):
    for x, y in ((a, b), (b, a)):
        try:
            await bot.send_photo(
                x["id"], y["photo"],
                caption=f"💘 <b>It's a Match!</b>\nAapka aur <b>{y['name']}</b> ka match hua! "
                        f"Compatibility: {compat(x, y)}%",
                reply_markup=k.url_btn(f"💬 Chat with {y['name']}", link_for(y)))
        except Exception:
            pass


@router.callback_query(F.data.startswith("sw:"))
async def swipe(c: CallbackQuery, bot: Bot):
    _, action, tid = c.data.split(":")
    tid, uid = int(tid), c.from_user.id
    me = await db.get_user(uid)
    prem = is_premium(me)

    if action == "rewind":
        if not prem:
            return await c.answer("↩️ Rewind sirf 💎 Premium ke liye", show_alert=True)
        last = await db.last_swipe(uid)
        if not last:
            return await c.answer("Kuch rewind karne ko nahi", show_alert=True)
        await db.delete_swipe(last["id"])
        await c.message.delete()
        return await show_next(bot, uid)

    if action == "report":
        total = await db.add_report(uid, tid)
        for a in ADMIN_IDS:
            try:
                await bot.send_message(a, f"🚩 Report: {uid} → {tid} (total {total})\n/ban {tid}")
            except Exception:
                pass
        await db.add_swipe(uid, tid, "pass")
        await c.answer("Report ho gaya 🙏")
        await c.message.delete()
        return await show_next(bot, uid)

    if action in ("like", "super"):
        if not prem:
            likes = await db.count_swipes_today(uid, ["like", "super"])
            if likes >= FREE_LIKES_PER_DAY:
                return await c.answer(
                    f"Daily limit {FREE_LIKES_PER_DAY} likes. 💎 Premium = unlimited!", show_alert=True)
        if action == "super":
            limit = PREMIUM_SUPER_PER_DAY if prem else FREE_SUPER_PER_DAY
            if await db.count_swipes_today(uid, ["super"]) >= limit:
                return await c.answer("Aaj ke Super Likes khatam ⭐", show_alert=True)

    await db.add_swipe(uid, tid, action)
    target = await db.get_user(tid)
    if action in ("like", "super") and target:
        if await db.liked_me(uid, tid):
            await notify_match(bot, me, target)
        elif action == "super":
            try:
                if is_premium(target):
                    await bot.send_message(tid, f"⭐ <b>{me['name']}</b> ne aapko Super Like kiya!")
                else:
                    await bot.send_message(tid, "⭐ Kisi ne aapko Super Like kiya! Dekhne ke liye 💎 Premium lein.")
            except Exception:
                pass
    await c.answer()
    await c.message.delete()
    await show_next(bot, uid)


# ---------- matches / likes ----------
@router.message(Command("matches"))
async def cmd_matches(m: Message, bot: Bot):
    await send_matches(bot, m.from_user.id)


async def send_matches(bot, uid):
    ms = await db.get_matches(uid)
    if not ms:
        return await bot.send_message(uid, "💔 Abhi koi match nahi. /find karte rahein!")
    for u in ms[:20]:
        await bot.send_photo(uid, u["photo"], caption=card(u),
                             reply_markup=k.url_btn("💬 Chat", link_for(u)))


@router.message(Command("likes"))
async def cmd_likes(m: Message, bot: Bot):
    await send_likes(bot, m.from_user.id)


async def send_likes(bot, uid):
    me = await db.get_user(uid)
    ls = await db.who_liked_me(uid)
    if not ls:
        return await bot.send_message(uid, "Abhi koi pending like nahi.")
    if not is_premium(me):
        return await bot.send_message(
            uid, f"👀 <b>{len(ls)}</b> logon ne aapko like kiya hai!\n💎 Premium lekar dekhein ki kaun.",
            reply_markup=k.premium_kb())
    for u in ls[:20]:
        await bot.send_photo(uid, u["photo"], caption=card(u, viewer=me),
                             reply_markup=k.swipe_kb(u["id"]))


# ---------- daily pick (top compatibility) ----------
async def send_pick(bot, uid):
    me = await db.get_user(uid)
    pool = await db.fetchall(
        """SELECT * FROM users WHERE id!=? AND profile_done=1 AND banned=0 AND active=1
           AND id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)
           AND (?='all' OR gender=?) LIMIT 300""",
        (uid, uid, me["looking_for"], me["looking_for"]))
    if not pool:
        return await bot.send_message(uid, "Abhi koi pick available nahi.")
    pool.sort(key=lambda u: compat(me, u), reverse=True)
    top = pool[:3] if is_premium(me) else pool[:1]
    await bot.send_message(uid, "🌟 <b>Aapke Daily Picks</b>" +
                           ("" if is_premium(me) else "\n(💎 Premium me top 3)"))
    for u in top:
        await bot.send_photo(uid, u["photo"], caption=card(u, viewer=me),
                             reply_markup=k.swipe_kb(u["id"]))


@router.message(Command("dailypick"))
async def cmd_pick(m: Message, bot: Bot):
    await send_pick(bot, m.from_user.id)


# ---------- nearby ----------
async def send_nearby(bot, uid):
    me = await db.get_user(uid)
    if me["lat"] is None:
        return await bot.send_message(uid, "📍 Pehle /editprofile > Location se location set karein.")
    pool = await db.nearby_pool(me)
    pool = [(distance_km(me, u), u) for u in pool]
    pool.sort(key=lambda x: x[0])
    if not pool:
        return await bot.send_message(uid, "Aas-paas koi nahi mila.")
    limit = 10 if is_premium(me) else 3
    for d, u in pool[:limit]:
        await bot.send_photo(uid, u["photo"], caption=card(u, viewer=me),
                             reply_markup=k.swipe_kb(u["id"]))
    if not is_premium(me):
        await bot.send_message(uid, "💎 Premium me 10 nearby users dikhte hain.")


@router.message(Command("nearby"))
async def cmd_nearby(m: Message, bot: Bot):
    await send_nearby(bot, m.from_user.id)
