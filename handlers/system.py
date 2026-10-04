"""Sabse last router: unknown callbacks/messages + bot block/unblock tracking."""
from aiogram import Router
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated

import db
import keyboards as k

router = Router()


@router.my_chat_member()
async def on_member_update(event: ChatMemberUpdated):
    if event.chat.type != "private":
        return
    status = event.new_chat_member.status
    if status in ("kicked", "left"):
        await db.update_user(event.from_user.id, blocked=1)
    elif status == "member":
        await db.update_user(event.from_user.id, blocked=0)


@router.callback_query()
async def unknown_callback(c: CallbackQuery):
    await c.answer("Ye button ab active nahi hai. /start ya /help use karein.", show_alert=False)


@router.message()
async def unknown_message(m: Message):
    u = await db.get_user(m.from_user.id)
    if u and u["profile_done"]:
        await m.answer("🏠 Menu se option chunein ya /help dekhein.", reply_markup=k.main_menu())
    else:
        await m.answer("Profile banane ke liye /start bhejein.")
