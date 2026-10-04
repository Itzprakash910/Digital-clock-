"""Admin panel (sab kuch bot ke andar): users, search, ban/premium/coins, reports,
payments, CSV export aur broadcast (image + title + description + price + discount + button)."""
import asyncio
import csv
import io

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                           InlineKeyboardButton as B, BufferedInputFile)

import db
from config import ADMIN_IDS, PRICE_SYMBOL
from utils import esc, card, fmt_ts, fmt_price, is_premium, safe_delete

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

PAGE = 8
_running = {"on": False}
_tasks: set = set()

SEGMENTS = {
    "all": "👥 Sabhi users",
    "profiles": "✅ Complete profile wale",
    "premium": "💎 Premium users",
    "free": "🆓 Free users",
    "active7": "🔥 Active (7 din)",
    "incomplete": "⏳ Incomplete profile",
}


class BC(StatesGroup):
    photo = State()
    title = State()
    desc = State()
    product = State()
    price = State()
    discount = State()
    button = State()
    segment = State()
    confirm = State()


class AFind(StatesGroup):
    query = State()


class AMsg(StatesGroup):
    text = State()


def kb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def panel_kb():
    return kb([
        [B(text="📊 Stats", callback_data="adm:stats"), B(text="👥 Users", callback_data="adm:users:0")],
        [B(text="🔍 Find User", callback_data="adm:find"), B(text="📢 Broadcast", callback_data="adm:bc")],
        [B(text="🚩 Reports", callback_data="adm:reports"), B(text="💳 Payments", callback_data="adm:pays")],
        [B(text="📜 Broadcast History", callback_data="adm:bch"),
         B(text="📤 Export CSV", callback_data="adm:csv")],
    ])


BACK = kb([[B(text="⬅️ Admin Panel", callback_data="adm:home")]])


async def safe_edit(msg: Message, text: str, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup)
    except Exception:
        try:
            await msg.answer(text, reply_markup=markup)
        except Exception:
            pass


# ======================= commands =======================
@router.message(Command("admin"))
async def cmd_admin(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🛠 <b>Admin Panel</b>", reply_markup=panel_kb())


@router.message(Command("totalusers"))
async def cmd_total(m: Message):
    await m.answer(f"👥 Total users: <b>{await db.count_users()}</b>")


@router.message(Command("userinfo"))
async def cmd_userinfo(m: Message, command: CommandObject):
    res = await db.search_users(command.args or "")
    if not res:
        return await m.answer("Usage: /userinfo id/@username")
    text, markup = await user_view(res[0]["id"])
    await m.answer(text, reply_markup=markup)


@router.message(Command("ban", "unban"))
async def cmd_ban(m: Message, command: CommandObject):
    try:
        uid = int(command.args)
    except Exception:
        return await m.answer("Usage: /ban id  ya  /unban id")
    val = 1 if m.text.startswith("/ban") else 0
    await db.update_user(uid, banned=val)
    await m.answer("🚫 Banned" if val else "✅ Unbanned")


@router.message(Command("verify"))
async def cmd_verify(m: Message, command: CommandObject):
    try:
        await db.update_user(int(command.args), verified=1)
        await m.answer("✅ Verified badge diya")
    except Exception:
        await m.answer("Usage: /verify id")


@router.message(Command("givepremium"))
async def cmd_give(m: Message, command: CommandObject):
    try:
        uid, days = command.args.split()
        await db.extend_premium(int(uid), int(days))
        await m.answer("💎 Done")
    except Exception:
        await m.answer("Usage: /givepremium id days")


@router.message(Command("addcoins"))
async def cmd_coins(m: Message, command: CommandObject):
    try:
        uid, n = command.args.split()
        await db.add_coins(int(uid), int(n))
        await m.answer("🪙 Done")
    except Exception:
        await m.answer("Usage: /addcoins id amount")


@router.message(Command("broadcast"))
async def cmd_broadcast(m: Message, state: FSMContext):
    await start_bc(m, state)


# ======================= panel callbacks =======================
@router.callback_query(F.data == "adm:home")
async def cb_home(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.answer()
    await safe_edit(c.message, "🛠 <b>Admin Panel</b>", panel_kb())


@router.callback_query(F.data == "adm:stats")
async def cb_stats(c: CallbackQuery):
    s = await db.stats_global()
    rev = ", ".join(f"{v / 100:.2f} {cur}" for cur, v in s["revenue"].items()) or "0"
    text = (f"📊 <b>Stats</b>\n\n👥 Total users: <b>{s['users']}</b>\n✅ Complete profiles: {s['profiles']}\n"
            f"🆕 Naye (24h): {s['new24']}\n🔥 Active 24h: {s['active24']} · 7d: {s['active7']}\n"
            f"💎 Premium: {s['premium']}\n🚫 Banned: {s['banned']}\n⛔ Bot block kiya: {s['blocked']}\n\n"
            f"👆 Swipes: {s['swipes']}\n💞 Matches: {s['matches']}\n🚩 Reports: {s['reports']}\n"
            f"💳 Payments: {s['payments']}\n💰 Revenue: {rev}")
    await c.answer()
    await safe_edit(c.message, text, BACK)


# ----- users list -----
@router.callback_query(F.data.startswith("adm:users:"))
async def cb_users(c: CallbackQuery):
    page = int(c.data.split(":")[2])
    total = await db.count_users()
    pages = max(1, -(-total // PAGE))
    page = max(0, min(page, pages - 1))
    rows = await db.users_page(page * PAGE, PAGE)
    btns = []
    for u in rows:
        flag = "✅" if u["profile_done"] else "⏳"
        if u["banned"]:
            flag = "🚫"
        label = f"{flag} {(u['name'] or u['first_name'] or '?')[:14]}"
        if u["username"]:
            label += f" @{u['username'][:14]}"
        btns.append([B(text=label, callback_data=f"adm:user:{u['id']}")])
    nav = []
    if page > 0:
        nav.append(B(text="⬅️", callback_data=f"adm:users:{page - 1}"))
    nav.append(B(text=f"{page + 1}/{pages}", callback_data="adm:noop"))
    if page < pages - 1:
        nav.append(B(text="➡️", callback_data=f"adm:users:{page + 1}"))
    btns.append(nav)
    btns.append([B(text="⬅️ Admin Panel", callback_data="adm:home")])
    await c.answer()
    await safe_edit(c.message, f"👥 <b>Users</b> ({total}) — naye pehle", kb(btns))


@router.callback_query(F.data == "adm:noop")
async def cb_noop(c: CallbackQuery):
    await c.answer()


# ----- user detail -----
async def user_view(uid: int):
    u = await db.get_user(uid)
    if not u:
        return "❌ User nahi mila.", BACK
    refs = await db.count_referrals(uid)
    name = " ".join(x for x in (u["first_name"], u["last_name"]) if x) or "—"
    un = f"@{u['username']}" if u["username"] else "—"
    loc = f"{u['lat']:.4f}, {u['lon']:.4f}" if u["lat"] is not None else "—"
    prem = f"Yes (till {fmt_ts(u['premium_until'])})" if is_premium(u) else "No"
    text = (
        f"👤 <b>{esc(name)}</b> {un}\n🆔 <code>{u['id']}</code>\n"
        f"🌐 Lang: {u['language'] or '—'} · TG Premium: {'Yes' if u['tg_premium'] else 'No'}\n\n"
        f"🎂 Age: {u['age'] or '—'} · ⚧ {u['gender'] or '—'} · 🎯 Looking: {u['looking_for'] or '—'}\n"
        f"🏷 Interests: {esc((u['interests'] or '—').replace('|', ', '))}\n"
        f"💬 Bio: {esc(u['bio'] or '—')}\n📍 Location: {loc}\n🎭 Mood: {esc(u['mood'] or '—')}\n\n"
        f"✅ Profile: {'Done' if u['profile_done'] else 'Incomplete'} · ⏸ Active: {'Yes' if u['active'] else 'Paused'}\n"
        f"💎 Premium: {prem}\n🪙 Coins: {u['coins']} · 👥 Referrals: {refs}\n"
        f"👁 Views: {u['views']} · 🔥 Streak: {u['streak']}\n"
        f"🚫 Banned: {'Yes' if u['banned'] else 'No'} · ✔️ Verified: {'Yes' if u['verified'] else 'No'} · "
        f"⛔ Blocked bot: {'Yes' if u['blocked'] else 'No'}\n"
        f"🕒 Joined: {fmt_ts(u['created'])}\n🕒 Last active: {fmt_ts(u['last_active'])}")
    ban_btn = (B(text="✅ Unban", callback_data=f"adm:act:unban:{uid}") if u["banned"]
               else B(text="🚫 Ban", callback_data=f"adm:act:ban:{uid}"))
    ver_btn = (B(text="❌ Unverify", callback_data=f"adm:act:unverify:{uid}") if u["verified"]
               else B(text="✅ Verify", callback_data=f"adm:act:verify:{uid}"))
    markup = kb([
        [ban_btn, ver_btn],
        [B(text="💎 +7d", callback_data=f"adm:act:prem7:{uid}"),
         B(text="💎 +30d", callback_data=f"adm:act:prem30:{uid}"),
         B(text="💎 Remove", callback_data=f"adm:act:premoff:{uid}")],
        [B(text="🪙 +50", callback_data=f"adm:act:coin50:{uid}"),
         B(text="🪙 +200", callback_data=f"adm:act:coin200:{uid}")],
        [B(text="✉️ Message", callback_data=f"adm:msg:{uid}"),
         B(text="🖼 Profile", callback_data=f"adm:pic:{uid}")],
        [B(text="⬅️ Users", callback_data="adm:users:0")],
    ])
    return text, markup


@router.callback_query(F.data.startswith("adm:user:"))
async def cb_user(c: CallbackQuery):
    text, markup = await user_view(int(c.data.split(":")[2]))
    await c.answer()
    await safe_edit(c.message, text, markup)


@router.callback_query(F.data.startswith("adm:act:"))
async def cb_act(c: CallbackQuery, bot: Bot):
    _, _, action, uid = c.data.split(":")
    uid = int(uid)
    note = None
    if action == "ban":
        await db.update_user(uid, banned=1)
    elif action == "unban":
        await db.update_user(uid, banned=0)
    elif action == "verify":
        await db.update_user(uid, verified=1)
        note = "✅ Aapki profile verify ho gayi!"
    elif action == "unverify":
        await db.update_user(uid, verified=0)
    elif action in ("prem7", "prem30"):
        days = 7 if action == "prem7" else 30
        await db.extend_premium(uid, days)
        note = f"🎁 Aapko {days} din ka 💎 Premium mila!"
    elif action == "premoff":
        await db.update_user(uid, premium_until=0)
    elif action in ("coin50", "coin200"):
        n = 50 if action == "coin50" else 200
        await db.add_coins(uid, n)
        note = f"🎁 Aapko {n} 🪙 coins mile!"
    if note:
        try:
            await bot.send_message(uid, note)
        except Exception:
            pass
    await c.answer("Done ✅")
    text, markup = await user_view(uid)
    await safe_edit(c.message, text, markup)


@router.callback_query(F.data.startswith("adm:pic:"))
async def cb_pic(c: CallbackQuery):
    u = await db.get_user(int(c.data.split(":")[2]))
    await c.answer()
    if not u or not u["profile_done"]:
        return await c.message.answer("Profile complete nahi hai.")
    if u["photo"]:
        await c.message.answer_photo(u["photo"], caption=card(u))
    else:
        await c.message.answer(card(u))


# ----- direct message to a user -----
@router.callback_query(F.data.startswith("adm:msg:"))
async def cb_msg(c: CallbackQuery, state: FSMContext):
    uid = int(c.data.split(":")[2])
    await state.set_state(AMsg.text)
    await state.update_data(uid=uid)
    await c.answer()
    await c.message.answer(f"✉️ User <code>{uid}</code> ko bhejne ke liye message likhein (/admin = cancel):")


@router.message(AMsg.text, ~F.text.startswith("/"))
async def got_msg(m: Message, state: FSMContext, bot: Bot):
    uid = (await state.get_data())["uid"]
    await state.clear()
    try:
        await bot.send_message(uid, f"📩 <b>Admin:</b>\n{esc(m.text or '')}")
        await m.answer("✅ Message bhej diya.", reply_markup=panel_kb())
    except Exception as e:
        await m.answer(f"❌ Nahi gaya: {esc(str(e))}", reply_markup=panel_kb())


# ----- find user -----
@router.callback_query(F.data == "adm:find")
async def cb_find(c: CallbackQuery, state: FSMContext):
    await state.set_state(AFind.query)
    await c.answer()
    await c.message.answer("🔍 User ID, @username ya naam bhejein (/admin = cancel):")


@router.message(AFind.query, ~F.text.startswith("/"))
async def got_find(m: Message, state: FSMContext):
    await state.clear()
    res = await db.search_users(m.text or "")
    if not res:
        return await m.answer("❌ Koi user nahi mila.", reply_markup=panel_kb())
    btns = [[B(text=f"{(u['name'] or '?')[:16]} {'@' + u['username'] if u['username'] else ''} · {u['id']}",
               callback_data=f"adm:user:{u['id']}")] for u in res]
    btns.append([B(text="⬅️ Admin Panel", callback_data="adm:home")])
    await m.answer(f"🔍 {len(res)} result:", reply_markup=kb(btns))


# ----- reports / payments / history / csv -----
@router.callback_query(F.data == "adm:reports")
async def cb_reports(c: CallbackQuery):
    rows = await db.recent_reports()
    await c.answer()
    if not rows:
        return await safe_edit(c.message, "🚩 Koi report nahi.", BACK)
    btns = [[B(text=f"🚩 {(r['name'] or '?')[:16]} · {r['c']} reports",
               callback_data=f"adm:user:{r['reported']}")] for r in rows]
    btns.append([B(text="⬅️ Admin Panel", callback_data="adm:home")])
    await safe_edit(c.message, "🚩 <b>Recent reports</b> (user kholne ke liye tap karein)", kb(btns))


@router.callback_query(F.data == "adm:pays")
async def cb_pays(c: CallbackQuery):
    rows = await db.recent_payments()
    await c.answer()
    if not rows:
        return await safe_edit(c.message, "💳 Abhi koi payment nahi.", BACK)
    t = "💳 <b>Recent payments</b>\n\n"
    for p in rows:
        t += (f"• {esc(p['name'] or '?')} (<code>{p['user_id']}</code>) · {p['plan']} · "
              f"{p['amount'] / 100:.2f} {p['currency']} · {fmt_ts(p['ts'])}\n")
    await safe_edit(c.message, t, BACK)


@router.callback_query(F.data == "adm:bch")
async def cb_bch(c: CallbackQuery):
    rows = await db.recent_broadcasts()
    await c.answer()
    if not rows:
        return await safe_edit(c.message, "📜 Abhi tak koi broadcast nahi.", BACK)
    t = "📜 <b>Broadcast history</b>\n\n"
    for b in rows:
        t += (f"#{b['id']} · <b>{esc(b['title'] or '')}</b> · {b['segment']}\n"
              f"   ✅ {b['sent']}/{b['total']} · ❌ {b['failed']} · ⛔ {b['blocked']} · "
              f"{b['status']} · {fmt_ts(b['ts'])}\n")
    await safe_edit(c.message, t, BACK)


@router.callback_query(F.data == "adm:csv")
async def cb_csv(c: CallbackQuery, bot: Bot):
    await c.answer("Export ho raha hai…")
    users = await db.all_users()
    if not users:
        return await c.message.answer("Koi user nahi.")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(users[0].keys()), extrasaction="ignore")
    w.writeheader()
    for u in users:
        row = dict(u)
        for key in ("created", "last_active", "premium_until", "profile_at"):
            row[key] = fmt_ts(row.get(key)) if row.get(key) else ""
        w.writerow(row)
    data = buf.getvalue().encode("utf-8-sig")
    await bot.send_document(c.from_user.id, BufferedInputFile(data, filename="users.csv"),
                            caption=f"📤 {len(users)} users")


# ======================= broadcast =======================
def build_text(d: dict) -> str:
    t = f"📢 <b>{esc(d['title'])}</b>\n\n{esc(d['desc'])}"
    if d.get("is_product"):
        price, disc = float(d["price"]), int(d.get("discount") or 0)
        if disc > 0:
            final = round(price * (100 - disc) / 100, 2)
            t += (f"\n\n🏷 <s>{fmt_price(price)}</s> ➜ <b>{fmt_price(final)}</b>  🔥 {disc}% OFF"
                  f"\n💰 Bachat: {fmt_price(price - final)}")
        else:
            t += f"\n\n💰 Price: <b>{fmt_price(price)}</b>"
    return t


def build_markup(d: dict):
    if d.get("btn_url"):
        return kb([[B(text=d["btn_text"], url=d["btn_url"])]])
    return None


async def send_one(bot: Bot, uid: int, d: dict):
    text, markup = build_text(d), build_markup(d)
    if d.get("photo"):
        await bot.send_photo(uid, d["photo"], caption=text, reply_markup=markup)
    else:
        await bot.send_message(uid, text, reply_markup=markup)


CANCEL_ROW = [B(text="❌ Cancel", callback_data="bc:cancel")]


async def start_bc(m: Message, state: FSMContext):
    await state.clear()
    await state.set_state(BC.photo)
    await m.answer("📢 <b>Broadcast</b>\n\nStep 1: 🖼 <b>Image</b> bhejein (photo ki tarah).",
                   reply_markup=kb([[B(text="⏭ Image skip", callback_data="bc:skip")], CANCEL_ROW]))


@router.callback_query(F.data == "adm:bc")
async def cb_bc(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await start_bc(c.message, state)


@router.callback_query(F.data == "bc:cancel")
async def bc_cancel(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.answer("Cancel")
    await safe_edit(c.message, "❌ Broadcast cancel.", panel_kb())


async def ask_title(msg: Message, state: FSMContext):
    await state.set_state(BC.title)
    await msg.answer("Step 2: 📝 <b>Title</b> likhein (max 100 characters).",
                     reply_markup=kb([CANCEL_ROW]))


@router.message(BC.photo, F.photo)
async def bc_photo(m: Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id)
    await ask_title(m, state)


@router.callback_query(BC.photo, F.data == "bc:skip")
async def bc_photo_skip(c: CallbackQuery, state: FSMContext):
    await state.update_data(photo=None)
    await c.answer()
    await ask_title(c.message, state)


@router.message(BC.title, F.text)
async def bc_title(m: Message, state: FSMContext):
    if len(m.text) > 100:
        return await m.answer("Title max 100 characters. Chhota likhein.")
    await state.update_data(title=m.text.strip())
    await state.set_state(BC.desc)
    await m.answer("Step 3: 📄 <b>Description</b> likhein (max 700 characters).",
                   reply_markup=kb([CANCEL_ROW]))


@router.message(BC.desc, F.text)
async def bc_desc(m: Message, state: FSMContext):
    if len(m.text) > 700:
        return await m.answer("Description max 700 characters. Chhota likhein.")
    await state.update_data(desc=m.text.strip())
    await state.set_state(BC.product)
    await m.answer("Step 4: Ye <b>product / offer</b> hai (price ke saath)?",
                   reply_markup=kb([[B(text="🛍 Haan, product", callback_data="bc:prod:1"),
                                     B(text="📝 Nahi, announcement", callback_data="bc:prod:0")],
                                    CANCEL_ROW]))


async def ask_button(msg: Message, state: FSMContext):
    await state.set_state(BC.button)
    await msg.answer("Step 6: 🔘 Button chahiye? Is format me bhejein:\n"
                     "<code>Buy Now | https://example.com</code>\n(Telegram link bhi chalega: https://t.me/...)",
                     reply_markup=kb([[B(text="⏭ Button skip", callback_data="bc:skip")], CANCEL_ROW]))


@router.callback_query(BC.product, F.data.startswith("bc:prod:"))
async def bc_product(c: CallbackQuery, state: FSMContext):
    is_p = c.data.endswith(":1")
    await state.update_data(is_product=is_p, price=None, discount=0)
    await c.answer()
    if is_p:
        await state.set_state(BC.price)
        await c.message.answer(f"Step 5a: 💰 <b>Price</b> likhein (sirf number, jaise 999). Symbol: {PRICE_SYMBOL}",
                               reply_markup=kb([CANCEL_ROW]))
    else:
        await ask_button(c.message, state)


@router.message(BC.price, F.text)
async def bc_price(m: Message, state: FSMContext):
    try:
        price = float(m.text.replace(",", "").replace(PRICE_SYMBOL, "").strip())
        assert price > 0
    except Exception:
        return await m.answer("Sahi price number bhejein (jaise 499 ya 499.50).")
    await state.update_data(price=price)
    await state.set_state(BC.discount)
    await m.answer("Step 5b: 🔥 <b>Discount %</b> likhein (0 = koi discount nahi, max 95).",
                   reply_markup=kb([CANCEL_ROW]))


@router.message(BC.discount, F.text)
async def bc_discount(m: Message, state: FSMContext):
    t = m.text.strip().replace("%", "")
    if not t.isdigit() or not (0 <= int(t) <= 95):
        return await m.answer("0 se 95 ke beech number bhejein.")
    await state.update_data(discount=int(t))
    await ask_button(m, state)


async def ask_segment(msg: Message, state: FSMContext):
    await state.set_state(BC.segment)
    rows = []
    for key, label in SEGMENTS.items():
        n = len(await db.audience(key))
        rows.append([B(text=f"{label} ({n})", callback_data=f"bc:seg:{key}")])
    rows.append(CANCEL_ROW)
    await msg.answer("Step 7: 🎯 <b>Kise bhejna hai?</b>", reply_markup=kb(rows))


@router.message(BC.button, F.text)
async def bc_button(m: Message, state: FSMContext):
    parts = [p.strip() for p in m.text.split("|", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1].startswith(("http://", "https://", "tg://")):
        return await m.answer("Format galat. Aise bhejein: <code>Buy Now | https://example.com</code>")
    if len(parts[0]) > 40:
        return await m.answer("Button text max 40 characters.")
    await state.update_data(btn_text=parts[0], btn_url=parts[1])
    await ask_segment(m, state)


@router.callback_query(BC.button, F.data == "bc:skip")
async def bc_button_skip(c: CallbackQuery, state: FSMContext):
    await state.update_data(btn_text=None, btn_url=None)
    await c.answer()
    await ask_segment(c.message, state)


@router.callback_query(BC.segment, F.data.startswith("bc:seg:"))
async def bc_segment(c: CallbackQuery, state: FSMContext, bot: Bot):
    seg = c.data.split(":")[2]
    ids = await db.audience(seg)
    await c.answer()
    if not ids:
        return await c.message.answer("Is audience me koi user nahi. Dusra chunein.")
    d = await state.get_data()
    if d.get("photo") and len(build_text(d)) > 1024:
        await state.clear()
        return await c.message.answer(
            "❌ Image ke saath caption 1024 characters se lamba hai. Title/description chhota karke dobara try karein.",
            reply_markup=panel_kb())
    await state.update_data(segment=seg)
    await state.set_state(BC.confirm)
    await c.message.answer("👀 <b>Preview:</b>")
    await send_one(bot, c.from_user.id, d)
    await c.message.answer(
        f"🎯 Audience: <b>{SEGMENTS[seg]}</b> — <b>{len(ids)}</b> users\n\nBhejein?",
        reply_markup=kb([[B(text="✅ Send Now", callback_data="bc:send"),
                          B(text="🧪 Test (mujhe)", callback_data="bc:test")],
                         CANCEL_ROW]))


@router.callback_query(BC.confirm, F.data == "bc:test")
async def bc_test(c: CallbackQuery, state: FSMContext, bot: Bot):
    await c.answer("Test bheja")
    await send_one(bot, c.from_user.id, await state.get_data())


@router.callback_query(BC.confirm, F.data == "bc:send")
async def bc_send(c: CallbackQuery, state: FSMContext, bot: Bot):
    if _running["on"]:
        return await c.answer("Ek broadcast pehle se chal raha hai, wait karein.", show_alert=True)
    d = await state.get_data()
    await state.clear()
    ids = await db.audience(d["segment"])
    await c.answer()
    bid = await db.create_broadcast(c.from_user.id, d, d["segment"], len(ids))
    status = await c.message.answer(f"📤 Broadcast #{bid} shuru… 0/{len(ids)}")
    task = asyncio.create_task(run_broadcast(bot, c.from_user.id, d, ids, bid, status))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def run_broadcast(bot: Bot, admin_id: int, d: dict, ids: list, bid: int, status: Message):
    _running["on"] = True
    sent = failed = blocked = 0
    try:
        for i, uid in enumerate(ids, 1):
            try:
                await send_one(bot, uid, d)
                sent += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                try:
                    await send_one(bot, uid, d)
                    sent += 1
                except Exception:
                    failed += 1
            except TelegramForbiddenError:
                blocked += 1
                await db.update_user(uid, blocked=1)
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)  # ~20 msg/sec (Telegram limit ke andar)
            if i % 50 == 0:
                try:
                    await status.edit_text(f"📤 Broadcast #{bid}… {i}/{len(ids)}")
                except Exception:
                    pass
    finally:
        _running["on"] = False
        await db.finish_broadcast(bid, sent, failed, blocked)
    try:
        await status.edit_text(
            f"✅ <b>Broadcast #{bid} complete</b>\n\n📨 Sent: {sent}\n⛔ Blocked: {blocked}\n"
            f"❌ Failed: {failed}\n👥 Total: {len(ids)}", reply_markup=panel_kb())
    except Exception:
        await bot.send_message(admin_id, f"✅ Broadcast #{bid}: sent {sent}, blocked {blocked}, failed {failed}")
