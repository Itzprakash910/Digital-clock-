from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import db
import keyboards as k
from config import INTERESTS, REFERRAL_COINS, ADMIN_IDS, NOTIFY_NEW_USERS
from utils import card, is_premium, esc, safe_delete

router = Router()


class Reg(StatesGroup):
    age = State()
    gender = State()
    looking = State()
    bio = State()
    interests = State()
    photo = State()
    location = State()


# ---------- steps ----------
async def ask_age(uid, bot, state):
    await state.set_state(Reg.age)
    await bot.send_message(uid, "🎂 Apni <b>age</b> bhejein (18-99). Ye app sirf 18+ ke liye hai.")


async def ask_gender(uid, bot, state):
    await state.set_state(Reg.gender)
    await bot.send_message(uid, "Aap kaun hain?", reply_markup=k.gender_kb("g"))


async def ask_looking(uid, bot, state):
    await state.set_state(Reg.looking)
    await bot.send_message(uid, "Aap kise dhoondh rahe hain?", reply_markup=k.gender_kb("l"))


async def ask_bio(uid, bot, state):
    await state.set_state(Reg.bio)
    await bot.send_message(uid, "💬 Apni <b>bio</b> likhein (max 500 characters).")


async def ask_interests(uid, bot, state):
    await state.set_state(Reg.interests)
    await state.update_data(sel=[])
    await bot.send_message(uid, "🏷 Apne <b>interests</b> chunein (max 5):",
                           reply_markup=k.interests_kb([]))


async def ask_photo(uid, bot, state):
    await state.set_state(Reg.photo)
    await bot.send_message(uid, "📸 Apni <b>photo</b> bhejein (clear selfie best hai).")


async def ask_location(uid, bot, state):
    await state.set_state(Reg.location)
    await bot.send_message(uid, "📍 Nearby matches ke liye location share karein (optional).",
                           reply_markup=k.location_kb())


async def show_menu(uid, bot):
    await bot.send_message(uid, "🏠 <b>Main Menu</b>", reply_markup=k.main_menu())


async def after_step(state: FSMContext, uid: int, bot: Bot, next_step):
    """Edit mode me update ke baad menu, warna registration ka next step."""
    data = await state.get_data()
    if data.get("editing"):
        await state.clear()
        await bot.send_message(uid, "✅ Update ho gaya!", reply_markup=k.main_menu())
    else:
        await next_step(uid, bot, state)


# ---------- /start ----------
@router.message(CommandStart())
async def start(m: Message, state: FSMContext, command: CommandObject, bot: Bot):
    await state.clear()
    uid = m.from_user.id
    u = await db.get_user(uid)
    if not u:
        ref_id = None
        if command.args and command.args.startswith("ref_"):
            r = await db.get_user_by_code(command.args[4:])
            if r and r["id"] != uid:
                ref_id = r["id"]
        await db.create_user(m.from_user, ref_id)
        u = await db.get_user(uid)
        if NOTIFY_NEW_USERS:
            uname = f"@{m.from_user.username}" if m.from_user.username else "—"
            for a in ADMIN_IDS:
                try:
                    await bot.send_message(
                        a, f"🆕 <b>Naya user</b>\n{esc(m.from_user.full_name)} ({uname})\n"
                           f"🆔 <code>{uid}</code>\nTotal users: {await db.count_users()}",
                        reply_markup=k.kb([[k.B(text="👤 Open", callback_data=f"adm:user:{uid}")]]))
                except Exception:
                    pass
    if u["profile_done"]:
        await m.answer(f"👋 Wapas swagat hai, <b>{esc(u['name'] or '')}</b>!",
                       reply_markup=k.main_menu())
        return
    await m.answer("💘 <b>Tele Tinder</b> me swagat hai!\nChalo profile banate hain.")
    await ask_age(uid, bot, state)


@router.message(Reg.age)
async def got_age(m: Message, state: FSMContext, bot: Bot):
    if not (m.text and m.text.strip().isdigit()):
        return await m.answer("Sirf number bhejein (18-99).")
    age = int(m.text.strip())
    if age < 18:
        return await m.answer("🚫 Ye app sirf 18+ ke liye hai.")
    if age > 99:
        return await m.answer("Sahi age bhejein (18-99).")
    await db.update_user(m.from_user.id, age=age)
    await after_step(state, m.from_user.id, bot, ask_gender)


@router.callback_query(Reg.gender, F.data.startswith("g:"))
async def got_gender(c: CallbackQuery, state: FSMContext, bot: Bot):
    await db.update_user(c.from_user.id, gender=c.data.split(":")[1])
    await c.answer()
    await safe_delete(c.message)
    await ask_looking(c.from_user.id, bot, state)


@router.callback_query(Reg.looking, F.data.startswith("l:"))
async def got_looking(c: CallbackQuery, state: FSMContext, bot: Bot):
    await db.update_user(c.from_user.id, looking_for=c.data.split(":")[1])
    await c.answer()
    await safe_delete(c.message)
    await after_step(state, c.from_user.id, bot, ask_bio)


@router.message(Reg.bio)
async def got_bio(m: Message, state: FSMContext, bot: Bot):
    if not m.text or len(m.text) > 500:
        return await m.answer("Text me bio bhejein (max 500 characters).")
    await db.update_user(m.from_user.id, bio=m.text.strip())
    await after_step(state, m.from_user.id, bot, ask_interests)


@router.callback_query(Reg.interests, F.data.startswith("i:"))
async def got_interest(c: CallbackQuery, state: FSMContext, bot: Bot):
    val = c.data.split(":")[1]
    data = await state.get_data()
    sel = data.get("sel", [])
    if val == "done":
        if not sel:
            return await c.answer("Kam se kam 1 chunein", show_alert=True)
        await db.update_user(c.from_user.id, interests="|".join(sel))
        await c.answer()
        await safe_delete(c.message)
        return await after_step(state, c.from_user.id, bot, ask_photo)
    tag = INTERESTS[int(val)]
    if tag in sel:
        sel.remove(tag)
    elif len(sel) < 5:
        sel.append(tag)
    else:
        return await c.answer("Max 5 interests", show_alert=True)
    await state.update_data(sel=sel)
    try:
        await c.message.edit_reply_markup(reply_markup=k.interests_kb(sel))
    except Exception:
        pass
    await c.answer()


@router.message(Reg.photo, F.photo)
async def got_photo(m: Message, state: FSMContext, bot: Bot):
    await db.update_user(m.from_user.id, photo=m.photo[-1].file_id)
    await after_step(state, m.from_user.id, bot, ask_location)


@router.message(Reg.photo)
async def need_photo(m: Message):
    await m.answer("Photo bhejein 📸 (file nahi, normal photo).")


@router.message(Reg.location)
async def got_location(m: Message, state: FSMContext, bot: Bot):
    uid = m.from_user.id
    if m.location:
        await db.update_user(uid, lat=m.location.latitude, lon=m.location.longitude)
    elif not (m.text and "skip" in m.text.lower()):
        return await m.answer("Location button dabayein ya Skip likhein.")
    data = await state.get_data()
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=k.REMOVE)
    if data.get("editing"):
        return await show_menu(uid, bot)
    u = await db.get_user(uid)
    await db.update_user(uid, profile_done=1, profile_at=db.now())
    if u["referred_by"] and not u["ref_rewarded"]:
        await db.add_coins(u["referred_by"], REFERRAL_COINS)
        await db.update_user(uid, ref_rewarded=1)
        try:
            await bot.send_message(u["referred_by"],
                                   f"🎉 Aapke referral ne join kiya! +{REFERRAL_COINS} 🪙")
        except Exception:
            pass
    await m.answer("🎉 <b>Profile ready!</b>")
    await show_menu(uid, bot)


# ---------- my profile / edit ----------
async def send_my_profile(uid, bot):
    u = await db.get_user(uid)
    text = "👤 <b>Your Profile</b>\n\n" + card(u)
    text += f"\n👁 Views: {u['views']}\n🪙 Coins: {u['coins']}"
    try:
        posts = await db.list_posts(uid)
        text += f"\n📸 Posts: {len(posts)}/4"
    except Exception:
        pass
    text += "\n💎 Premium: Active" if is_premium(u) else "\n💎 Premium: No"
    if not u["active"]:
        text += "\n⏸ Profile paused"
    if u["photo"]:
        await bot.send_photo(uid, u["photo"], caption=text, reply_markup=k.edit_kb())
    else:
        await bot.send_message(uid, text, reply_markup=k.edit_kb())


@router.message(Command("myprofile"))
async def cmd_my(m: Message, bot: Bot):
    await send_my_profile(m.from_user.id, bot)


@router.message(Command("editprofile"))
async def cmd_edit(m: Message):
    await m.answer("✏️ Kya edit karna hai?", reply_markup=k.edit_kb())


EDIT_STEPS = {"bio": ask_bio, "age": ask_age, "photo": ask_photo, "interests": ask_interests,
              "location": ask_location, "looking": ask_looking}


def delete_confirm_kb():
    return k.kb([[k.B(text="✅ Haan, delete karo", callback_data="del:yes"),
                  k.B(text="❌ Nahi", callback_data="m:menu")]])


@router.callback_query(F.data.startswith("ed:"))
async def edit_cb(c: CallbackQuery, state: FSMContext, bot: Bot):
    what, uid = c.data.split(":")[1], c.from_user.id
    await c.answer()
    if what == "pause":
        u = await db.get_user(uid)
        await db.update_user(uid, active=0 if u["active"] else 1)
        return await c.message.answer("⏸ Profile paused" if u["active"] else "▶️ Profile resumed",
                                      reply_markup=k.main_menu())
    if what == "delete":
        return await c.message.answer("⚠️ Profile delete karna hai? Aapke matches aur likes hat jayenge.",
                                      reply_markup=delete_confirm_kb())
    if what in EDIT_STEPS:
        await state.clear()
        await EDIT_STEPS[what](uid, bot, state)
        await state.update_data(editing=True)


@router.message(Command("deleteprofile"))
async def cmd_del(m: Message):
    await m.answer("⚠️ Profile delete karna hai? Aapke matches aur likes hat jayenge.",
                   reply_markup=delete_confirm_kb())


@router.callback_query(F.data == "del:yes")
async def confirm_del(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await db.reset_profile(c.from_user.id)
    await c.answer()
    await c.message.answer("🗑 Profile delete ho gaya. Dobara banane ke liye /start karein.")

@router.message(Command("contacts"))
async def cmd_contacts(m: Message):
    u = await db.get_user(m.from_user.id)
    if not is_premium(u):
        return await m.answer("🔐 Contact details manage karna Premium feature hai.", reply_markup=k.premium_kb())
    await m.answer("📇 Contact details ko update karne ke liye /setcontacts use karein.\n\nFormat:\n/setcontacts telegram=@name phone=... instagram=https://instagram.com/... facebook=https://facebook.com/... other=https://... show_phone=1 show_social=1\n\nPrivacy: contacts mutual-match Premium viewers ko hi dikhte hain.")

@router.message(Command("setcontacts"))
async def setcontacts(m: Message):
    u = await db.get_user(m.from_user.id)
    if not is_premium(u):
        return await m.answer("🔐 Contact details sirf Premium users set kar sakte hain.", reply_markup=k.premium_kb())
    text = (m.text or "").partition(" ")[2].strip()
    if not text:
        return await m.answer("Example: /setcontacts telegram=@name phone=9999999999 instagram=https://instagram.com/name")
    vals = {}
    for token in text.split():
        if "=" in token:
            key, val = token.split("=", 1); key = key.strip().lower(); val = val.strip()
            if key == "telegram": vals["telegram_username"] = val.lstrip("@")
            elif key == "phone": vals["phone"] = val
            elif key == "instagram": vals["instagram"] = val
            elif key == "facebook": vals["facebook"] = val
            elif key == "other": vals["other_social"] = val
            elif key in ("show_telegram","show_phone","show_social"):
                vals[key] = 1 if val.lower() in ("1","yes","true","on") else 0
    if not vals:
        return await m.answer("Koi valid contact field nahi mila.")
    await db.set_contacts(m.from_user.id, **vals)
    await m.answer("✅ Contact details saved. Ye mutual-match Premium viewers ko hi visible honge.")
