"""Profile post/gallery system: up to MAX_PROFILE_POSTS additional photos per profile."""
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
import db, keyboards as k
from config import MAX_PROFILE_POSTS
from utils import esc, is_premium

router = Router()

class PostState(StatesGroup):
    photo = State()
    caption = State()

async def manage(bot: Bot, uid: int):
    rows = await db.list_posts(uid)
    text = f"📸 <b>My Posts</b> — {len(rows)}/{MAX_PROFILE_POSTS}\n\n"
    if rows:
        text += "\n".join(f"{i+1}. {esc((x.get('caption') or 'No caption')[:80])}" for i,x in enumerate(rows))
    else:
        text += "Abhi koi post nahi hai.\n"
    buttons = []
    if len(rows) < MAX_PROFILE_POSTS:
        buttons.append([k.B(text="➕ Add Post", callback_data="posts:add")])
    for x in rows:
        buttons.append([k.B(text=f"🗑 Delete #{x.get('position',0)}", callback_data=f"posts:del:{x['id']}")])
    buttons.append([k.B(text="🏠 Menu", callback_data="m:menu")])
    await bot.send_message(uid, text, reply_markup=k.kb(buttons))

@router.callback_query(F.data == "posts:manage")
async def cb_manage(c: CallbackQuery, bot: Bot):
    await c.answer()
    await manage(bot, c.from_user.id)

@router.message(Command("posts"))
async def cmd_posts(m: Message, bot: Bot):
    await manage(bot, m.from_user.id)

@router.callback_query(F.data == "posts:add")
async def cb_add(c: CallbackQuery, state: FSMContext):
    rows = await db.list_posts(c.from_user.id)
    if len(rows) >= MAX_PROFILE_POSTS:
        return await c.answer(f"Maximum {MAX_PROFILE_POSTS} posts allowed.", show_alert=True)
    await state.set_state(PostState.photo)
    await c.answer()
    await c.message.answer("📸 Post photo bhejein. /cancel se cancel.")

@router.message(PostState.photo, F.photo)
async def post_photo(m: Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id)
    await state.set_state(PostState.caption)
    await m.answer("✍️ Caption bhejein (optional, max 250 chars).")

@router.message(PostState.photo)
async def post_need_photo(m: Message):
    await m.answer("Normal Telegram photo bhejein 📸.")

@router.message(PostState.caption)
async def post_caption(m: Message, state: FSMContext):
    if not m.text:
        return await m.answer("Caption text bhejein ya `-` likhein.")
    caption = "" if m.text.strip() == "-" else m.text.strip()
    if len(caption) > 250:
        return await m.answer("Caption max 250 characters.")
    d = await state.get_data()
    await state.clear()
    uid=m.from_user.id
    rows=await db.list_posts(uid)
    if len(rows)>=MAX_PROFILE_POSTS:
        return await m.answer("Maximum posts reached.")
    await db.add_post(uid,d["photo"],caption)
    await m.answer("✅ Post added! Aapki profile gallery me dikhegi.", reply_markup=k.main_menu())

@router.callback_query(F.data.startswith("posts:del:"))
async def cb_del(c: CallbackQuery):
    try: pid=int(c.data.split(":")[2])
    except: return await c.answer()
    ok=await db.delete_post(c.from_user.id,pid)
    await c.answer("Deleted ✅" if ok else "Post nahi mila.", show_alert=not ok)
    if ok:
        await c.message.answer("📸 Post delete ho gayi.", reply_markup=k.main_menu())

@router.callback_query(F.data.startswith("posts:view:"))
async def cb_view(c: CallbackQuery, bot: Bot):
    uid=int(c.data.split(":")[2])
    posts=await db.list_posts(uid)
    if not posts:
        return await c.answer("Is profile par extra posts nahi hain.", show_alert=True)
    await c.answer()
    for i,p in enumerate(posts,1):
        cap=f"📸 <b>Post {i}/{len(posts)}</b>"
        if p.get("caption"): cap += f"\n{esc(p['caption'])}"
        await bot.send_photo(c.from_user.id,p["photo"],caption=cap)
