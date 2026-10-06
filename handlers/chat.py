from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
import db, keyboards as k
from config import FREE_CHAT_STARTS_PER_DAY
from utils import is_premium, esc

router=Router()

class ChatState(StatesGroup):
    target=State()

def _is_match(ms,tid): return any(int(x["id"])==int(tid) for x in ms)

async def _open(uid,tid,state,message):
    if not _is_match(await db.get_matches(uid),tid):
        return await message.answer("💞 Chat sirf mutual match ke baad available hai.")
    u=await db.get_user(uid)
    existing=await db.has_chat_session(uid,tid)
    if not is_premium(u) and not existing:
        used=await db.count_chat_starts_today(uid)
        if used>=FREE_CHAT_STARTS_PER_DAY:
            return await message.answer(
                f"🔒 Aaj ke {FREE_CHAT_STARTS_PER_DAY} new chats use ho chuke hain.\n"
                "💎 Premium se unlimited new chats + contact/social access unlock karein.",
                reply_markup=k.premium_kb())
        await db.start_chat_session(uid,tid)
    else:
        await db.start_chat_session(uid,tid)
    await state.set_state(ChatState.target); await state.update_data(target=tid)
    await message.answer("💬 <b>Private ConnectMate Chat</b>\n"
                         "Aapki identity relay ke through protected rahegi. /endchat se exit karein.")

@router.callback_query(F.data.startswith("chat:"))
async def start_chat(c:CallbackQuery,state:FSMContext):
    tid=int(c.data.split(":")[1])
    await c.answer()
    await _open(c.from_user.id,tid,state,c.message)

@router.message(Command("chat"))
async def cmd_chat(m:Message,state:FSMContext):
    # /chat alone shows guidance; match buttons are the preferred route.
    await m.answer("💬 Chat start karne ke liye /matches me kisi mutual match par Chat button dabayein.")

@router.message(Command("endchat"))
async def endchat(m:Message,state:FSMContext):
    await state.clear(); await m.answer("✅ Chat mode closed.",reply_markup=k.main_menu())

async def _target(m,state):
    d=await state.get_data(); tid=int(d["target"]); uid=m.from_user.id
    if not _is_match(await db.get_matches(uid),tid):
        await state.clear(); await m.answer("Match active nahi hai."); return None
    return tid

@router.message(ChatState.target)
async def relay(m:Message,state:FSMContext):
    tid=await _target(m,state)
    if tid is None:return
    uid=m.from_user.id
    try:
        if m.text:
            await db.save_chat_message(uid,tid,m.text)
            sender = await db.get_user(uid)
            sender_name = esc(sender.get("name") or m.from_user.full_name or "ConnectMate User")
            await m.bot.send_message(tid,f"💬 <b>New message from {sender_name}</b>\n{esc(m.text)}")
        elif m.photo:
            fid=m.photo[-1].file_id
            cap=m.caption or ""
            await db.save_chat_message(uid,tid,"[PHOTO] "+cap)
            sender = await db.get_user(uid); sender_name = esc(sender.get("name") or m.from_user.full_name or "ConnectMate User")
            await m.bot.send_photo(tid,fid,caption=f"💬 <b>Photo from {sender_name}</b>\n{esc(cap)}" if cap else f"💬 <b>Photo from {sender_name}</b>")
        elif m.voice:
            await db.save_chat_message(uid,tid,"[VOICE]")
            sender = await db.get_user(uid); sender_name = esc(sender.get("name") or m.from_user.full_name or "ConnectMate User")
            await m.bot.send_voice(tid,m.voice.file_id,caption=f"💬 Voice from {sender_name}")
        elif m.video:
            await db.save_chat_message(uid,tid,"[VIDEO] "+(m.caption or ""))
            sender = await db.get_user(uid); sender_name = esc(sender.get("name") or m.from_user.full_name or "ConnectMate User")
            await m.bot.send_video(tid,m.video.file_id,caption=f"💬 <b>Video from {sender_name}</b>\n{esc(m.caption)}" if m.caption else f"💬 <b>Video from {sender_name}</b>")
        else:
            return await m.answer("Text, photo, video ya voice bhej sakte hain.")
        await m.answer("✓ Delivered")
    except Exception:
        await m.answer("Message deliver nahi hua. User ne bot block kiya ho sakta hai.")
