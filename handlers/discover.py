from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import db
import keyboards as k
from config import (FREE_LIKES_PER_DAY, FREE_SUPER_PER_DAY, PREMIUM_SUPER_PER_DAY, ADMIN_IDS)
from utils import card, is_premium, distance_km, compat, esc, safe_delete

router = Router()


def link_for(u):
    return f"https://t.me/{u['username']}" if u.get("username") else f"tg://user?id={u['id']}"


async def send_profile(bot: Bot, uid: int, c: dict, viewer: dict):
    caption = card(c, viewer=viewer)
    posts = await db.list_posts(c["id"])
    if posts:
        caption += f"\n📸 <b>{len(posts)} profile posts</b> — tap Posts to view\n"
    if c.get("photo"):
        await bot.send_photo(uid, c["photo"], caption=caption, reply_markup=k.swipe_kb(c["id"]))
    else:
        await bot.send_message(uid, caption, reply_markup=k.swipe_kb(c["id"]))


async def show_next(bot: Bot, uid: int, target_id: int | None = None):
    u = await db.get_user(uid)
    if not u or not u["profile_done"]:
        return await bot.send_message(uid, "Pehle /start se profile banayein.")
    c = await db.get_user(target_id) if target_id else None
    if not c:
        c = await db.get_candidate(u)
    if not c:
        return await bot.send_message(
            uid,
            "😴 <b>Abhi koi suitable profile nahi mili.</b>\n\n"
            "⚙️ Filters check karein, location/distance badhayein, ya thodi der baad dobara Discover karein.",
            reply_markup=k.kb([
                [k.B(text="⚙️ Filters", callback_data="m:filters"), k.B(text="📍 Nearby", callback_data="m:nearby")],
                [k.B(text="🔄 Discover Again", callback_data="m:find"), k.B(text="🏠 Menu", callback_data="m:menu")]
            ]))
    view_count, is_new_view = await db.add_view(c["id"], uid)
    if is_new_view:
        try:
            await bot.send_message(c["id"], f"👀 <b>{esc(u.get('name') or 'Someone')}</b> ne aapki profile dekhi.")
        except Exception: pass
        # Engagement achievements are unlocked once and never spammed.
        thresholds = [(10,"profile_10_views","👀 Getting Noticed","Aapki profile ko 10 unique people ne dekha!"),
                      (50,"profile_50_views","🌟 Popular Profile","Aapki profile 50 unique views cross kar chuki hai!"),
                      (100,"profile_100_views","🔥 Trending","Aapki profile 100 unique views cross kar chuki hai!")]
        for threshold,key,title,desc in thresholds:
            if view_count >= threshold and await db.unlock_achievement(c["id"],key,title,desc):
                try: await bot.send_message(c["id"], f"🏆 <b>Achievement Unlocked!</b>\n{title}\n{desc}")
                except Exception: pass
    await send_profile(bot, uid, c, u)




@router.callback_query(F.data.startswith("viewprofile:"))
async def view_profile_callback(c: CallbackQuery, bot: Bot):
    target=int(c.data.split(":")[1]); me=await db.get_user(c.from_user.id); u=await db.get_user(target)
    if not u or not u.get("profile_done") or u.get("banned") or not u.get("active"):
        return await c.answer("Profile ab available nahi hai.",show_alert=True)
    await c.answer()
    await db.add_view(target,c.from_user.id)
    await send_profile(bot,c.from_user.id,u,me)

@router.message(Command("find", "discover"))
async def cmd_find(m: Message, bot: Bot):
    await show_next(bot, m.from_user.id)


async def notify_match(bot: Bot, a, b):
    for x, y in ((a, b), (b, a)):
        caption = (f"💘 <b>It's a Match!</b>\nAapka aur <b>{esc(y['name'] or '')}</b> ka match hua! "
                   f"Compatibility: {compat(x, y)}%")
        markup = k.match_actions(y["id"])
        try:
            if y.get("photo"):
                await bot.send_photo(x["id"], y["photo"], caption=caption, reply_markup=markup)
            else:
                await bot.send_message(x["id"], caption, reply_markup=markup)
        except Exception:
            pass


@router.callback_query(F.data.startswith("sw:"))
async def swipe(c: CallbackQuery, bot: Bot):
    _, action, tid = c.data.split(":")
    tid, uid = int(tid), c.from_user.id
    me = await db.get_user(uid)
    if not me or not me["profile_done"]:
        return await c.answer("Pehle /start se profile banayein.", show_alert=True)
    prem = is_premium(me)

    if action == "rewind":
        if not prem:
            return await c.answer("↩️ Rewind sirf 💎 Premium ke liye", show_alert=True)
        last = await db.last_swipe(uid)
        if not last:
            return await c.answer("Rewind karne ke liye kuch nahi", show_alert=True)
        await db.delete_swipe(last["id"])
        await c.answer("↩️ Wapas!")
        await safe_delete(c.message)
        return await show_next(bot, uid, last["to_id"])

    if tid == uid:
        return await c.answer()
    if await db.has_swiped(uid, tid):
        await c.answer("Aap pehle hi swipe kar chuke hain")
        return await safe_delete(c.message)

    if action == "report":
        total = await db.add_report(uid, tid)
        await db.add_swipe(uid, tid, "pass")
        for a in ADMIN_IDS:
            try:
                await bot.send_message(
                    a, f"🚩 <b>Report</b>: <code>{uid}</code> ➜ <code>{tid}</code> (total {total})",
                    reply_markup=k.kb([[k.B(text="👤 Open user", callback_data=f"adm:user:{tid}")]]))
            except Exception:
                pass
        await c.answer("Report ho gaya 🙏")
        await safe_delete(c.message)
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
    elif action != "pass":
        return await c.answer()

    await db.add_swipe(uid, tid, action)
    target = await db.get_user(tid)
    if target and action in ("like", "super", "pass"):
        try:
            label = "❤️ Like" if action == "like" else ("⭐ Super Like" if action == "super" else "👎 Skip")
            await bot.send_message(tid, f"🔔 <b>Profile Activity</b>\n<b>{esc(me.get('name') or 'Someone')}</b> ne aapki profile par {label} kiya.")
        except Exception: pass
    if action in ("like", "super") and target:
        # Popularity achievements based on received likes.
        recv = int((await db.get_user(tid)).get("likes_received") or 0)
        thresholds = [(10,"likes_10","❤️ Loved Profile","10 likes receive hue!"),
                      (25,"likes_25","💖 Crowd Favourite","25 likes receive hue!"),
                      (50,"likes_50","🔥 Most Wanted","50 likes receive hue!")]
        for threshold,key,title,desc in thresholds:
            if recv >= threshold and await db.unlock_achievement(tid,key,title,desc):
                try: await bot.send_message(tid, f"🏆 <b>Achievement Unlocked!</b>\n{title}\n{desc}")
                except Exception: pass
        if await db.liked_me(uid, tid):
            await notify_match(bot, me, target)
        elif action == "super":
            try:
                if is_premium(target):
                    await bot.send_message(
                        tid, f"⭐ <b>{esc(me['name'] or '')}</b> ne aapko Super Like kiya!")
                else:
                    await bot.send_message(
                        tid, "⭐ Kisi ne aapko Super Like kiya! Dekhne ke liye 💎 Premium lein.")
            except Exception:
                pass
    await c.answer()
    await safe_delete(c.message)
    await show_next(bot, uid)


# ---------- matches / likes ----------
@router.message(Command("matches"))
async def cmd_matches(m: Message, bot: Bot):
    await send_matches(bot, m.from_user.id)


async def send_matches(bot, uid, page=0):
    ms = await db.get_matches(uid)
    if not ms:
        return await bot.send_message(uid, "💔 Abhi koi match nahi. /find karte rahein!")
    page=max(0,int(page)); per_page=10; total_pages=(len(ms)+per_page-1)//per_page
    if page>=total_pages: page=total_pages-1
    await bot.send_message(uid, f"💞 <b>Your Matches</b> — {len(ms)} total\\nPage {page+1}/{total_pages}")
    for u in ms[page*per_page:(page+1)*per_page]:
        markup = k.match_actions(u["id"])
        if u.get("photo"):
            await bot.send_photo(uid, u["photo"], caption=card(u, viewer=await db.get_user(uid)), reply_markup=markup)
        else:
            await bot.send_message(uid, card(u, viewer=await db.get_user(uid)), reply_markup=markup)
    nav=[]
    if page>0: nav.append(k.B(text="⬅️ Previous",callback_data=f"matches:page:{page-1}"))
    if page<total_pages-1: nav.append(k.B(text="Next ➡️",callback_data=f"matches:page:{page+1}"))
    if nav: await bot.send_message(uid,"📚 More matches:",reply_markup=k.kb([nav,[k.B(text="🏠 Menu",callback_data="m:menu")]]))

@router.callback_query(F.data.startswith("matches:page:"))
async def matches_page(c: CallbackQuery, bot: Bot):
    page=int(c.data.split(":")[2]); await c.answer(); await send_matches(bot,c.from_user.id,page)


@router.message(Command("likes"))
async def cmd_likes(m: Message, bot: Bot):
    await send_likes(bot, m.from_user.id)


async def send_likes(bot, uid):
    me = await db.get_user(uid)
    incoming = await db.who_liked_me(uid)
    outgoing = await db.get_liked_profiles(uid)
    if not incoming and not outgoing:
        return await bot.send_message(uid, "👀 Abhi Likes section me koi profile nahi hai.")
    await bot.send_message(uid, f"👀 <b>Likes</b>\n❤️ Aapne like kiya: <b>{len(outgoing)}</b>\n💌 Aapko like mila: <b>{len(incoming)}</b>")
    if outgoing:
        await bot.send_message(uid, "❤️ <b>Your Likes</b>")
        for u in outgoing[:30]:
            await send_profile(bot, uid, u, me)
    if incoming:
        if not is_premium(me):
            return await bot.send_message(uid,
                f"💌 <b>{len(incoming)}</b> users ne aapko like kiya hai.\n💎 Premium lekar sabhi profiles dekhein aur match karein.",
                reply_markup=k.premium_kb())
        await bot.send_message(uid, "💌 <b>People Who Liked You</b>")
        for u in incoming[:30]:
            await send_profile(bot, uid, u, me)


# ---------- daily pick ----------
async def send_pick(bot, uid):
    me = await db.get_user(uid)
    pool = await db.get_pool(me)
    if not pool:
        return await bot.send_message(uid, "Abhi koi pick available nahi.")
    pool.sort(key=lambda u: compat(me, u), reverse=True)
    top = pool[:3] if is_premium(me) else pool[:1]
    await bot.send_message(uid, "🌟 <b>Aapke Daily Picks</b>" +
                           ("" if is_premium(me) else "\n(💎 Premium me top 3)"))
    for u in top:
        await send_profile(bot, uid, u, me)


@router.message(Command("dailypick"))
async def cmd_pick(m: Message, bot: Bot):
    await send_pick(bot, m.from_user.id)


# ---------- nearby ----------
async def send_nearby(bot, uid):
    me = await db.get_user(uid)
    if me["lat"] is None:
        return await bot.send_message(
            uid,
            "📍 <b>Nearby ke liye location zaroori hai.</b>\nLocation share karne ke baad main aapko nearest profiles distance ke order me dikhaunga.",
            reply_markup=k.location_kb())
    pool = await db.get_pool(me, limit=300, need_location=True)
    pool = sorted(((distance_km(me, u), u) for u in pool), key=lambda x: x[0])
    if not pool:
        return await bot.send_message(
            uid,
            "📍 <b>Aas-paas abhi koi suitable profile nahi mili.</b>\n\n"
            "⚙️ Distance filter badhayein ya Discover me broader matches dekhein.",
            reply_markup=k.kb([[k.B(text="⚙️ Filters", callback_data="m:filters"), k.B(text="🔥 Discover", callback_data="m:find")],
                               [k.B(text="🏠 Menu", callback_data="m:menu")]]))
    limit = 10 if is_premium(me) else 3
    for _, u in pool[:limit]:
        await send_profile(bot, uid, u, me)
    if not is_premium(me):
        await bot.send_message(uid, "💎 Premium me 10 nearby users dikhte hain.")


@router.message(Command("nearby"))
async def cmd_nearby(m: Message, bot: Bot):
    await send_nearby(bot, m.from_user.id)


@router.callback_query(F.data.startswith("contact:"))
async def contacts(c: CallbackQuery):
    target = int(c.data.split(":")[1]); me = c.from_user.id
    if not await db.can_view_contacts(me, target):
        await c.answer("💎 Premium required", show_alert=True)
        return await c.message.answer(
            "🔐 <b>Premium Contacts Locked</b>\n\n"
            "💎 Premium Membership ke baad mutual matches ke phone, Telegram username aur social links dekh sakte hain.\n"
            "♾ Unlimited new chats bhi unlock honge.",
            reply_markup=k.premium_kb())
    x = await db.get_contacts(target)
    if not x:
        return await c.answer("Is user ne contact details add nahi ki hain.", show_alert=True)
    lines = ["🔐 <b>Premium Contact Access</b>"]
    if x.get("show_telegram") and x.get("telegram_username"): lines.append(f"Telegram: @{esc(str(x['telegram_username']).lstrip('@'))}")
    if x.get("show_phone") and x.get("phone"): lines.append(f"📞 Phone: <code>{esc(str(x['phone']))}</code>")
    if x.get("show_social"):
        for key, label in (("instagram","Instagram"),("facebook","Facebook"),("other_social","Social")):
            if x.get(key): lines.append(f"{label}: {esc(str(x[key]))}")
    if len(lines) == 1: lines.append("Owner ne abhi koi Premium-visible contact set nahi kiya.")
    await c.answer()
    await c.message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("rate:"))
async def rate_start(c: CallbackQuery):
    target = int(c.data.split(":")[1])
    if not any(int(x["id"]) == target for x in await db.get_matches(c.from_user.id)):
        return await c.answer("Rating sirf matched users ko de sakte hain.", show_alert=True)
    await c.answer("Rating choose karein")
    await c.message.answer("⭐ Profile ko rate karein:", reply_markup=k.rating_kb(target))


@router.callback_query(F.data.startswith("rating:"))
async def rate_save(c: CallbackQuery):
    _, target, value = c.data.split(":")
    target, value = int(target), int(value)
    if not any(int(x["id"]) == target for x in await db.get_matches(c.from_user.id)):
        return await c.answer("Rating sirf matched users ko de sakte hain.", show_alert=True)
    avg, count = await db.add_rating(c.from_user.id, target, value)
    rater = await db.get_user(c.from_user.id)
    try:
        await c.bot.send_message(target, f"⭐ <b>{esc(rater.get('name') or 'Someone')}</b> ne aapki profile ko {value}/5 rate kiya. New rating: {avg:.1f}/5")
    except Exception: pass
    if count >= 10 and await db.unlock_achievement(target,"rated_10","⭐ Highly Rated","Aapki profile ko 10 ratings mil chuki hain!"):
        try: await c.bot.send_message(target,"🏆 <b>Achievement Unlocked!</b> ⭐ Highly Rated\n10 ratings complete!")
        except Exception: pass
    await c.answer(f"⭐ Rating saved: {value}/5")
    await c.message.answer(f"✅ Rating saved. Profile rating: {avg:.1f}/5 ({count} ratings)")
