from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import db
import keyboards as k
from config import INTERESTS, REFERRAL_COINS
from utils import card, is_premium, interest_set

router = Router()


class Reg(StatesGroup):
    age = State()
    gender = State()
    looking = State()
    bio = State()
    interests = State()
    photo = State()
    location = State()


async def finish_step(target, state: FSMContext, uid: int, bot: Bot, after):
    """Edit mode me wapas menu, warna next step."""
    data = await state.get_data()
    if data.get("editing"):
        await state.clear()
        await bot.send_message(uid, "✅ Update ho gaya!", reply_markup=k.main_menu())
    else:
        await after()


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


# ---------------- /start ----------------
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
        await db.create_user(uid, m.from_user.first_name, m.from_user.username, ref_id)
        u = await db.get_user(uid)
    if m.from_user.username != u["username"]:
        await db.update_user(uid, username=m.from_user.username)
    if u["profile_done"]:
        await m.answer(f"👋 Wapas swagat hai, <b>{u['name']}</b>!", reply_markup=k.main_menu())
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
    await finish_step(m, state, m.from_user.id, bot, lambda: ask_gender(m.from_user.id, bot, state))


@router.callback_query(Reg.gender, F.data.startswith("g:"))
async def got_gender(c: CallbackQuery, state: FSMContext, bot: Bot):
    await db.update_user(c.from_user.id, gender=c.data.split(":")[1])
    await c.message.delete()
    await ask_looking(c.from_user.id, bot, state)


@router.callback_query(Reg.looking, F.data.startswith("l:"))
async def got_looking(c: CallbackQuery, state: FSMContext, bot: Bot):
    await db.update_user(c.from_user.id, looking_for=c.data.split(":")[1])
    await c.message.delete()
    await finish_step(c, state, c.from_user.id, bot, lambda: ask_bio(c.from_user.id, bot, state))


@router.message(Reg.bio)
async def got_bio(m: Message, state: FSMContext, bot: Bot):
    if not m.text or len(m.text) > 500:
        return await m.answer("Text me bio bhejein (max 500 characters).")
    await db.update_user(m.from_user.id, bio=m.text.strip())
    await finish_step(m, state, m.from_user.id, bot, lambda: ask_interests(m.from_user.id, bot, state))


@router.callback_query(Reg.interests, F.data.startswith("i:"))
async def got_interest(c: CallbackQuery, state: FSMContext, bot: Bot):
    val = c.data.split(":")[1]
    data = await state.get_data()
    sel = data.get("sel", [])
    if val == "done":
        if not sel:
            return await c.answer("Kam se kam 1 chunein", show_alert=True)
        await db.update_user(c.from_user.id, interests="|".join(sel))
        await c.message.delete()
        return await finish_step(c, state, c.from_user.id, bot,
                                 lambda: ask_photo(c.from_user.id, bot, state))
    tag = INTERESTS[int(val)]
    if tag in sel:
        sel.remove(tag)
    elif len(sel) < 5:
        sel.append(tag)
    else:
        return await c.answer("Max 5 interests", show_alert=True)
    await state.update_data(sel=sel)
    await c.message.edit_reply_markup(reply_markup=k.interests_kb(sel))
    await c.answer()


@router.message(Reg.photo, F.photo)
async def got_photo(m: Message, state: FSMContext, bot: Bot):
    await db.update_user(m.from_user.id, photo=m.photo[-1].file_id)
    await finish_step(m, state, m.from_user.id, bot, lambda: ask_location(m.from_user.id, bot, state))


@router.message(Reg.photo)
async def need_photo(m: Message):
    await m.answer("Photo bhejein 📸")


@router.message(Reg.location)
async def got_location(m: Message, state: FSMContext, bot: Bot):
    uid = m.from_user.id
    if m.location:
        await db.update_user(uid, lat=m.location.latitude, lon=m.location.longitude)
    elif not (m.text and "skip" in m.text.lower()):
        return await m.answer("Location button dabayein ya Skip likhein.")
    u = await db.get_user(uid)
    data = await state.get_data()
    await state.clear()
    await m.answer("✅ Saved!", reply_markup=k.REMOVE)
    if data.get("editing"):
        return await show_menu(uid, bot)
    await db.update_user(uid, profile_done=1)
    if u["referred_by"]:
        await db.add_coins(u["referred_by"], REFERRAL_COINS)
        try:
            await bot.send_message(u["referred_by"],
                                   f"🎉 Aapke referral ne join kiya! +{REFERRAL_COINS} 🪙")
        except Exception:
            pass
    await m.answer("🎉 <b>Profile ready!</b>")
    await show_menu(uid, bot)


# ---------------- my profile / edit ----------------
async def send_my_profile(uid, bot):
    u = await db.get_user(uid)
    text = "👤 <b>Your Profile</b>\n\n" + card(u)
    text += f"\n👁 Views: {u['views']}\n🪙 Coins: {u['coins']}"
    text += "\n💎 Premium: Active" if is_premium(u) else "\n💎 Premium: No"
    if not u["active"]:
        text += "\n⏸ Profile paused"
    await bot.send_photo(uid, u["photo"], caption=text, reply_markup=k.edit_kb())


@router.message(Command("myprofile"))
async def cmd_my(m: Message, bot: Bot):
    await send_my_profile(m.from_user.id, bot)


@router.message(Command("editprofile"))
async def cmd_edit(m: Message):
    await m.answer("✏️ Kya edit karna hai?", reply_markup=k.edit_kb())


@router.callback_query(F.data.startswith("ed:"))
async def edit_cb(c: CallbackQuery, state: FSMContext, bot: Bot):
    what, uid = c.data.split(":")[1], c.from_user.id
    await c.answer()
    if what == "pause":
        u = await db.get_user(uid)
        await db.update_user(uid, active=0 if u["active"] else 1)
        return await c.message.answer("⏸ Paused" if u["active"] else "▶️ Resumed",
                                      reply_markup=k.main_menu())
    if what == "delete":
        return await c.message.answer(
            "⚠️ Pakka delete karna hai? Type karein: <code>/confirmdelete</code>")
    await state.clear()
    await state.update_data(editing=True)
    await {"bio": ask_bio, "age": ask_age, "photo": ask_photo, "interests": ask_interests,
           "location": ask_location, "looking": ask_looking}[what](uid, bot, state)
    await state.update_data(editing=True)


@router.message(Command("deleteprofile"))
async def cmd_del(m: Message):
    await m.answer("⚠️ Pakka delete karna hai? Type karein: <code>/confirmdelete</code>")


@router.message(Command("confirmdelete"))
async def confirm_del(m: Message, state: FSMContext):
    uid = m.from_user.id
    await state.clear()
    await db.execute("DELETE FROM users WHERE id=?", (uid,))
    await db.execute("DELETE FROM swipes WHERE from_id=? OR to_id=?", (uid, uid))
    await m.answer("🗑 Profile delete ho gaya. Dobara /start karein.")
