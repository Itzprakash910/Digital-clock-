import random
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import db
import keyboards as k
from config import (MOODS, ICEBREAKERS, BOOST_COST_COINS, BOOST_MINUTES, DAILY_BASE_COINS,
                    BOT_USERNAME, REFERRAL_COINS)
from db import now
from utils import is_premium, is_boosted
from handlers import discover, profile, filters
from handlers.premium import premium_text
from utils import esc, card

router = Router()


class Support(StatesGroup):
    message = State()

async def send_support(bot, uid, state):
    await state.set_state(Support.message)
    await bot.send_message(uid,"🆘 <b>Help & Support</b>\nApni problem/message yahin bhejein. Admin team ko forward kar diya jayega.")

@router.message(Command("support", "contactadmin"))
async def cmd_support(m: Message, state: FSMContext, bot: Bot):
    await send_support(bot,m.from_user.id,state)

@router.message(Support.message)
async def support_message(m: Message, state: FSMContext, bot: Bot):
    if not m.text:
        return await m.answer("Support ke liye text message bhejein.")
    uid=m.from_user.id; u=await db.get_user(uid); await state.clear()
    for a in __import__('config').ADMIN_IDS:
        try:
            await bot.send_message(a,f"🆘 <b>Support Request</b>\n👤 {esc(u.get('name') or m.from_user.full_name)}\n🆔 <code>{uid}</code>\n\n{esc(m.text)}",reply_markup=k.kb([[k.B(text="✉️ Reply User",callback_data=f"adm:msg:{uid}")]]))
        except Exception: pass
    await m.answer("✅ Aapka message admin ko bhej diya gaya hai. Jaldi reply milega.",reply_markup=k.main_menu())


class Ice(StatesGroup):
    answer = State()


# ---------- main menu callbacks ----------
@router.callback_query(F.data.startswith("m:"))
async def menu_cb(c: CallbackQuery, bot: Bot, state: FSMContext):
    what, uid = c.data.split(":")[1], c.from_user.id
    await c.answer()
    if what == "menu":
        return await bot.send_message(uid, "🏠 <b>Main Menu</b>", reply_markup=k.main_menu())
    actions = {
        "find": lambda: discover.show_next(bot, uid),
        "me": lambda: profile.send_my_profile(uid, bot),
        "matches": lambda: discover.send_matches(bot, uid),
        "likes": lambda: discover.send_likes(bot, uid),
        "pick": lambda: discover.send_pick(bot, uid),
        "nearby": lambda: discover.send_nearby(bot, uid),
        "mood": lambda: send_mood(bot, uid),
        "ice": lambda: start_ice(bot, uid, state),
        "daily": lambda: do_daily(bot, uid),
        "boost": lambda: do_boost(bot, uid),
        "premium": lambda: send_premium(bot, uid),
        "coins": lambda: send_coins(bot, uid),
        "filters": lambda: filters.send_filters(bot, uid),
        "support": lambda: send_support(bot, uid, state),
        "views": lambda: send_views(bot, uid),
        "stats": lambda: send_stats(bot, uid),
    }
    if what in actions:
        await actions[what]()



@router.message(Command("menu"))
async def cmd_menu(m: Message, bot: Bot):
    await bot.send_message(m.from_user.id, "🏠 <b>ConnectMate Main Menu</b>", reply_markup=k.main_menu())

# ---------- mood ----------
async def send_mood(bot, uid):
    await bot.send_message(
        uid, "🎭 <b>Aaj aapka mood?</b>\nSame mood wale log aapko pehle dikhenge (24 ghante).",
        reply_markup=k.moods_kb())


@router.message(Command("mood"))
async def cmd_mood(m: Message, bot: Bot):
    await send_mood(bot, m.from_user.id)


@router.callback_query(F.data.startswith("mood:"))
async def set_mood(c: CallbackQuery, bot: Bot):
    mood = MOODS[int(c.data.split(":")[1])]
    await db.update_user(c.from_user.id, mood=mood, mood_at=now())
    await c.message.edit_text(f"✅ Mood set: {mood}")
    await bot.send_message(c.from_user.id, "Chalo swipe karte hain!", reply_markup=k.main_menu())


# ---------- icebreaker ----------
async def start_ice(bot, uid, state):
    q = await send_ice(bot, uid, state)
    await state.set_state(Ice.answer)
    await state.update_data(q=q)


async def send_ice(bot, uid, state):
    q = random.choice(ICEBREAKERS)
    await bot.send_message(uid, f"🧊 <b>Icebreaker</b>\n\n{q}\n\nApna jawab likhein (profile pe dikhega):")
    return q


@router.message(Command("icebreaker"))
async def cmd_ice(m: Message, state: FSMContext, bot: Bot):
    q = await send_ice(bot, m.from_user.id, state)
    await state.set_state(Ice.answer)
    await state.update_data(q=q)


@router.message(Ice.answer)
async def ice_answer(m: Message, state: FSMContext):
    if m.text and m.text.startswith("/"):
        await state.clear()
        return await m.answer("Icebreaker cancel. Command dobara bhejein.")
    if not m.text or len(m.text) > 150:
        return await m.answer("Chhota jawab likhein (max 150 chars).")
    data = await state.get_data()
    await db.update_user(m.from_user.id, icebreaker=f"{data.get('q', '')} — {m.text.strip()}")
    await state.clear()
    await m.answer("✅ Icebreaker profile pe add ho gaya!", reply_markup=k.main_menu())


# ---------- daily reward + streak ----------
async def do_daily(bot, uid):
    u = await db.get_user(uid)
    gap = now() - (u["last_daily"] or 0)
    if gap < 86400:
        left = (86400 - gap) // 3600
        return await bot.send_message(uid, f"⏳ Agla reward ~{left + 1} ghante baad.")
    streak = u["streak"] + 1 if gap < 172800 else 1
    reward = DAILY_BASE_COINS + min(streak, 7) * 2
    if streak % 7 == 0:
        reward += 30
    await db.update_user(uid, streak=streak, last_daily=now())
    await db.add_coins(uid, reward)
    await bot.send_message(uid, f"🎁 Daily reward: <b>+{reward} 🪙</b>\n🔥 Streak: {streak} din\n"
                                "(Har 7 din pe bonus +30!)")


@router.message(Command("daily"))
async def cmd_daily(m: Message, bot: Bot):
    await do_daily(bot, m.from_user.id)


# ---------- boost ----------
async def do_boost(bot, uid):
    u = await db.get_user(uid)
    if is_boosted(u):
        left = (u["boost_until"] - now()) // 60
        return await bot.send_message(uid, f"🚀 Boost active hai, {left} min baaki.")
    if u["coins"] < BOOST_COST_COINS:
        return await bot.send_message(
            uid, f"🪙 Boost ke liye {BOOST_COST_COINS} coins chahiye (aapke paas {u['coins']}). "
                 "/daily ya /refer se coins kamayein.")
    await db.add_coins(uid, -BOOST_COST_COINS)
    await db.update_user(uid, boost_until=now() + BOOST_MINUTES * 60)
    await bot.send_message(uid, f"🚀 Boost ON! {BOOST_MINUTES} min tak aap sabse upar dikhenge.")


@router.message(Command("boost"))
async def cmd_boost(m: Message, bot: Bot):
    await do_boost(bot, m.from_user.id)


# ---------- coins / refer ----------
async def send_coins(bot, uid):
    u = await db.get_user(uid)
    refs = {"c": await db.count_referrals(uid)}
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{u['ref_code']}"
    await bot.send_message(
        uid,
        f"🪙 <b>Coins:</b> {u['coins']}\n👥 <b>Referrals:</b> {refs['c']}\n\n"
        f"1 referral = {REFERRAL_COINS} coins\nCoins se 💎 Premium ya 🚀 Boost lein.\n\n"
        f"🔗 Aapka link:\n{link}",
        reply_markup=k.kb([[k.B(text="📤 Share", url=f"https://t.me/share/url?url={link}")],
                           [k.B(text="💎 Premium", callback_data="m:premium")]]))


@router.message(Command("coins", "refer"))
async def cmd_coins(m: Message, bot: Bot):
    await send_coins(bot, m.from_user.id)


async def send_premium(bot, uid):
    u = await db.get_user(uid)
    await bot.send_message(uid, premium_text(u), reply_markup=k.premium_kb())


# ---------- stats / help ----------
async def send_views(bot, uid):
    u=await db.get_user(uid); viewers=await db.get_profile_viewers(uid,50)
    if not viewers:
        return await bot.send_message(uid,"👁 Abhi kisi ne aapki profile uniquely view nahi ki hai.")
    await bot.send_message(uid,f"👁 <b>Profile Views</b> — {len(viewers)} recent viewers")
    for v in viewers:
        await bot.send_message(uid, card(v, viewer=u), reply_markup=k.kb([[k.B(text="👤 View Profile",callback_data=f"viewprofile:{v['id']}")]]))

async def send_stats(bot, uid):
    u = await db.get_user(uid)
    likes_given = await db.count_likes_given(uid)
    likes_recv = await db.count_likes_received(uid)
    matches = len(await db.get_matches(uid))
    rate = f"{matches / likes_given * 100:.0f}%" if likes_given else "0%"
    await bot.send_message(uid, f"📊 <b>Your Stats</b>\n👁 Profile views: {u['views']}\n❤️ Likes diye: {likes_given}\n"
                   f"💌 Likes mile: {likes_recv}\n💞 Matches: {matches}\n🎯 Match rate: {rate}\n🔥 Streak: {u['streak']} din")

@router.message(Command("views"))
async def cmd_views(m: Message, bot: Bot):
    await send_views(bot,m.from_user.id)

@router.message(Command("stats"))
async def cmd_stats(m: Message, bot: Bot):
    await send_stats(bot,m.from_user.id)


@router.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(
        "📋 <b>Commands</b>\n/start /find /myprofile /editprofile /matches /likes\n"
        "/dailypick /nearby /mood /icebreaker /daily /boost\n/coins /refer /premium /stats /posts /contacts /setcontacts /chat /endchat /deleteprofile\n\n"
        "💎 Premium: unlimited likes + new chats, rewind, who-liked-me, 10 super likes, top-3 picks, more nearby, mutual-match contacts/social.")
