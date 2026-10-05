from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
import db, keyboards as k

router = Router()
class ChatState(StatesGroup):
    target = State()

def _is_match(ms, tid): return any(int(x["id"]) == int(tid) for x in ms)

@router.callback_query(F.data.startswith("chat:"))
async def start_chat(c: CallbackQuery, state: FSMContext):
    tid = int(c.data.split(":")[1])
    if not _is_match(await db.get_matches(c.from_user.id), tid):
        return await c.answer("Chat sirf mutual match ke baad available hai.", show_alert=True)
    await state.set_state(ChatState.target); await state.update_data(target=tid)
    await c.answer(); await c.message.answer("💬 Message type karein. /endchat se chat mode band hoga.")

@router.message(Command("endchat"))
async def endchat(m: Message, state: FSMContext):
    await state.clear(); await m.answer("✅ Chat mode closed.", reply_markup=k.main_menu())

@router.message(ChatState.target)
async def relay(m: Message, state: FSMContext):
    if not m.text: return await m.answer("Abhi text chat supported hai. /endchat")
    data = await state.get_data(); tid = int(data["target"]); uid = m.from_user.id
    if not _is_match(await db.get_matches(uid), tid):
        await state.clear(); return await m.answer("Match active nahi hai.")
    # Do not use Telegram forward/copy: that can expose sender identity.
    try:
        await db.save_chat_message(uid, tid, m.text)
        await m.bot.send_message(tid, f"💬 <b>New message</b>\n{m.html_text}")
        await m.answer("✓ Sent")
    except Exception:
        await m.answer("Message deliver nahi hua. User ne bot block kiya ho sakta hai.")
