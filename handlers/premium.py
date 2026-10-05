from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

import db
import keyboards as k
from config import PLANS, PAYMENT_PROVIDER_TOKEN, CURRENCY, ADMIN_IDS
from utils import is_premium, fmt_ts, esc

router = Router()

BENEFITS = ("♾ Unlimited likes\n↩️ Rewind (last swipe wapas)\n👀 Dekhein kaun ne like kiya\n"
            "⭐ 10 Super Likes/day\n🌟 Top-3 compatibility picks\n📍 10 nearby users\n💎 Profile pe badge")


def premium_text(u) -> str:
    t = "💎 <b>Premium Membership</b>\n\n" + BENEFITS + "\n\n"
    if is_premium(u):
        t += "✅ Active till: " + fmt_ts(u["premium_until"]) + "\n\n"
    t += "Plan chunein:"
    return t


@router.message(Command("premium"))
async def cmd_premium(m: Message):
    u = await db.get_user(m.from_user.id)
    await m.answer(premium_text(u), reply_markup=k.premium_kb())


@router.callback_query(F.data.startswith("pay:"))
async def pay(c: CallbackQuery, bot: Bot):
    key = c.data.split(":")[1]
    plan = PLANS.get(key)
    if not plan:
        return await c.answer()
    await c.answer()
    if not PAYMENT_PROVIDER_TOKEN:
        return await c.message.answer("Payment abhi configure nahi hai.")
    await bot.send_invoice(
        chat_id=c.from_user.id,
        title=plan["title"],
        description="Tele Tinder Premium: unlimited likes, rewind, who-liked-me aur zyada.",
        payload=f"premium:{key}",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=[LabeledPrice(label=plan["title"], amount=plan["price"])],
    )


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def paid(m: Message, bot: Bot):
    sp = m.successful_payment
    key = sp.invoice_payload.split(":")[1]
    plan = PLANS[key]
    await db.extend_premium(m.from_user.id, plan["days"])
    await db.add_payment(m.from_user.id, key, sp.total_amount, sp.currency,
                         sp.provider_payment_charge_id or sp.telegram_payment_charge_id)
    await m.answer(f"🎉 Payment successful! 💎 {plan['title']} activate ho gaya.",
                   reply_markup=k.main_menu())
    for a in ADMIN_IDS:
        try:
            await bot.send_message(
                a, f"💳 <b>Payment</b>: {esc(m.from_user.full_name)} (<code>{m.from_user.id}</code>)\n"
                   f"{plan['title']} · {sp.total_amount / 100:.2f} {sp.currency}")
        except Exception:
            pass


@router.callback_query(F.data.startswith("coinbuy:"))
async def coinbuy(c: CallbackQuery):
    plan = PLANS.get(c.data.split(":")[1])
    if not plan:
        return await c.answer()
    u = await db.get_user(c.from_user.id)
    if u["coins"] < plan["coins"]:
        return await c.answer(f"{plan['coins']} coins chahiye, aapke paas {u['coins']}", show_alert=True)
    await db.add_coins(c.from_user.id, -plan["coins"])
    await db.extend_premium(c.from_user.id, plan["days"])
    await c.answer()
    await c.message.answer(f"🎉 {plan['title']} activate ho gaya (coins se)!", reply_markup=k.main_menu())
