from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import db, keyboards as k

router=Router()

async def send_filters(bot, uid):
    u=await db.get_user(uid)
    await bot.send_message(uid,"⚙️ <b>Discover Filters</b>\nAge, distance aur online status choose karein.",reply_markup=kb_filters(u))

def kb_filters(u):
    return k.kb([
        [k.B(text=f"🎂 Age: {u.get('min_age',18)}–{u.get('max_age',99)}",callback_data="flt:age")],
        [k.B(text=f"📍 Distance: {u.get('max_distance',100)} km",callback_data="flt:dist")],
        [k.B(text=f"🟢 Online only: {'ON' if u.get('online_only') else 'OFF'}",callback_data="flt:online")],
        [k.B(text="🏠 Menu",callback_data="m:menu")]
    ])

@router.message(Command("filters"))
async def cmd_filters(m:Message):
    u=await db.get_user(m.from_user.id)
    await m.answer("⚙️ <b>Discover Filters</b>\nAge, distance aur online status choose karein.",reply_markup=kb_filters(u))

@router.callback_query(F.data=="flt:age")
async def age(c:CallbackQuery):
    u=await db.get_user(c.from_user.id)
    opts=[(18,25),(18,35),(21,30),(21,40),(25,45),(30,60),(18,99)]
    rows=[[k.B(text=f"{a}–{b}",callback_data=f"flt:setage:{a}:{b}") for a,b in opts[i:i+2]] for i in range(0,len(opts),2)]
    rows.append([k.B(text="⬅️ Back",callback_data="flt:back")])
    await c.answer(); await c.message.edit_text("🎂 Age range",reply_markup=k.kb(rows))

@router.callback_query(F.data.startswith("flt:setage:"))
async def setage(c:CallbackQuery):
    _,_,a,b=c.data.split(":")
    await db.update_user(c.from_user.id,min_age=int(a),max_age=int(b))
    u=await db.get_user(c.from_user.id)
    await c.answer("Saved ✅"); await c.message.edit_text("⚙️ Filters updated.",reply_markup=kb_filters(u))

@router.callback_query(F.data=="flt:dist")
async def dist(c:CallbackQuery):
    rows=[[k.B(text=f"{x} km",callback_data=f"flt:setdist:{x}") for x in (5,10,25)],
          [k.B(text=f"{x} km",callback_data=f"flt:setdist:{x}") for x in (50,100,250)],
          [k.B(text="🌎 Any",callback_data="flt:setdist:99999")],[k.B(text="⬅️ Back",callback_data="flt:back")]]
    await c.answer(); await c.message.edit_text("📍 Maximum distance",reply_markup=k.kb(rows))

@router.callback_query(F.data.startswith("flt:setdist:"))
async def setdist(c:CallbackQuery):
    d=float(c.data.split(":")[2]); await db.update_user(c.from_user.id,max_distance=d)
    u=await db.get_user(c.from_user.id); await c.answer("Saved ✅"); await c.message.edit_text("⚙️ Filters updated.",reply_markup=kb_filters(u))

@router.callback_query(F.data=="flt:online")
async def online(c:CallbackQuery):
    u=await db.get_user(c.from_user.id); val=0 if u.get("online_only") else 1
    await db.update_user(c.from_user.id,online_only=val); u=await db.get_user(c.from_user.id)
    await c.answer("Updated ✅"); await c.message.edit_text("⚙️ Filters",reply_markup=kb_filters(u))

@router.callback_query(F.data=="flt:back")
async def back(c:CallbackQuery):
    u=await db.get_user(c.from_user.id); await c.answer(); await c.message.edit_text("⚙️ Filters",reply_markup=kb_filters(u))
