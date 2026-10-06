from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton as B,
                           ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from config import INTERESTS, MOODS, PLANS, BOOST_COST_COINS, CURRENCY, PRICE_SYMBOL

REMOVE = ReplyKeyboardRemove()


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu():
    return kb([
        [B(text="🔥 Discover", callback_data="m:find"), B(text="👤 Profile", callback_data="m:me")],
        [B(text="💞 Matches", callback_data="m:matches"), B(text="👀 Likes", callback_data="m:likes")],
        [B(text="🌟 Daily Pick", callback_data="m:pick"), B(text="📍 Nearby", callback_data="m:nearby")],
        [B(text="🎭 Mood", callback_data="m:mood"), B(text="🧊 Icebreaker", callback_data="m:ice")],
        [B(text="🎁 Daily Reward", callback_data="m:daily"), B(text="🚀 Boost", callback_data="m:boost")],
        [B(text="⚙️ Filters", callback_data="m:filters"), B(text="📸 My Posts", callback_data="posts:manage")],
        [B(text="💎 Premium", callback_data="m:premium"), B(text="🪙 Coins/Refer", callback_data="m:coins")],
    ])


def gender_kb(prefix):
    rows = [[B(text="👨 Male", callback_data=f"{prefix}:male"),
             B(text="👩 Female", callback_data=f"{prefix}:female")],
            [B(text="🌈 Other", callback_data=f"{prefix}:other")]]
    if prefix == "l":
        rows[1].append(B(text="🌍 Everyone", callback_data="l:all"))
    return kb(rows)


def interests_kb(selected):
    rows, row = [], []
    for i in INTERESTS:
        row.append(B(text=("✅ " if i in selected else "") + i, callback_data=f"i:{INTERESTS.index(i)}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text=f"➡️ Done ({len(selected)}/5)", callback_data="i:done")])
    return kb(rows)


def location_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📍 Share Location", request_location=True)],
        [KeyboardButton(text="⏭ Skip")]], resize_keyboard=True, one_time_keyboard=True)


def swipe_kb(target_id):
    return kb([
        [B(text="👎 Pass", callback_data=f"sw:pass:{target_id}"),
         B(text="❤️ Like", callback_data=f"sw:like:{target_id}"),
         B(text="⭐ Super", callback_data=f"sw:super:{target_id}")],
        [B(text="📸 Posts", callback_data=f"posts:view:{target_id}"),
         B(text="↩️ Rewind 💎", callback_data="sw:rewind:0"),
         B(text="🚩 Report", callback_data=f"sw:report:{target_id}")],
        [B(text="🏠 Menu", callback_data="m:menu")],
    ])


def moods_kb():
    rows = [[B(text=m, callback_data=f"mood:{i}")] for i, m in enumerate(MOODS)]
    return kb(rows)


def edit_kb():
    return kb([
        [B(text="💬 Bio", callback_data="ed:bio"), B(text="🎂 Age", callback_data="ed:age")],
        [B(text="📸 Photo", callback_data="ed:photo"), B(text="🏷 Interests", callback_data="ed:interests")],
        [B(text="📍 Location", callback_data="ed:location"), B(text="🎯 Looking for", callback_data="ed:looking")],
        [B(text="📸 Manage Posts", callback_data="posts:manage")],
        [B(text="⏸ Pause/Resume", callback_data="ed:pause"), B(text="🗑 Delete", callback_data="ed:delete")],
        [B(text="🏠 Menu", callback_data="m:menu")],
    ])


def premium_kb():
    rows = [[B(text=f"💳 {p['title']} — {PRICE_SYMBOL}{p['price']/100:.0f} {CURRENCY}", callback_data=f"pay:{k}")]
            for k, p in PLANS.items()]
    rows += [[B(text=f"🪙 {p['title']} — {p['coins']} coins", callback_data=f"coinbuy:{k}")]
             for k, p in PLANS.items()]
    rows.append([B(text="🏠 Menu", callback_data="m:menu")])
    return kb(rows)


def url_btn(text, url):
    return kb([[B(text=text, url=url)]])


def match_actions(target_id):
    return kb([
        [B(text="💬 In-Bot Chat", callback_data=f"chat:{target_id}"),
         B(text="📸 Posts", callback_data=f"posts:view:{target_id}"),
         B(text="⭐ Rate", callback_data=f"rate:{target_id}")],
        [B(text="🔐 Premium Contacts", callback_data=f"contact:{target_id}")],
    ])


def rating_kb(target_id):
    return kb([[B(text=f"{i}⭐", callback_data=f"rating:{target_id}:{i}") for i in range(1, 6)]])
