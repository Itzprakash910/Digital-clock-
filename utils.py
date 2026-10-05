import html
import math
from datetime import datetime, timezone

from db import now
from config import PRICE_SYMBOL

esc = html.escape


def is_premium(u) -> bool:
    return (u.get("premium_until") or 0) > now()


def is_boosted(u) -> bool:
    return (u.get("boost_until") or 0) > now()


def interest_list(u):
    return sorted(x for x in (u.get("interests") or "").split("|") if x)


def compat(a, b) -> int:
    sa, sb = set(interest_list(a)), set(interest_list(b))
    if not sa or not sb:
        return 0
    return round(len(sa & sb) / len(sa | sb) * 100)


def haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def distance_km(a, b):
    if a.get("lat") is None or b.get("lat") is None:
        return None
    return haversine(a["lat"], a["lon"], b["lat"], b["lon"])


def fmt_ts(ts) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%d %b %Y %H:%M UTC")


def fmt_price(x) -> str:
    s = f"{float(x):,.2f}"
    if s.endswith(".00"):
        s = s[:-3]
    return f"{PRICE_SYMBOL}{s}"


async def safe_delete(msg):
    try:
        await msg.delete()
    except Exception:
        pass


def card(u, viewer=None) -> str:
    badges = ""
    if u.get("verified"):
        badges += " ✅"
    if is_premium(u):
        badges += " 💎"
    if is_boosted(u):
        badges += " 🚀"
    t = f"<b>{esc(u.get('name') or 'User')}</b>, {u.get('age') or '?'}{badges}\n"
    if viewer:
        d = distance_km(viewer, u)
        if d is not None:
            t += f"📍 ~{max(1, round(d))} km\n"
        sc = compat(viewer, u)
        if sc:
            t += f"💞 Compatibility: <b>{sc}%</b>\n"
    if u.get("mood") and (u.get("mood_at") or 0) > now() - 86400:
        t += f"🎭 Mood: {esc(u['mood'])}\n"
    if u.get("interests"):
        t += "🏷 " + " · ".join(esc(i) for i in interest_list(u)) + "\n"
    if u.get("bio"):
        bio = u["bio"] if len(u["bio"]) <= 420 else u["bio"][:420] + "…"
        t += f"\n💬 {esc(bio)}\n"
    t += f"\n👁 {int(u.get('views') or 0)} views · ❤️ {int(u.get('likes_received') or 0)} likes"
    if u.get("rating_count"):
        t += f" · ⭐ {float(u.get('rating_avg') or 0):.1f}/5 ({int(u.get('rating_count') or 0)})"
    t += "\n"
    if u.get("icebreaker"):
        t += f"\n🧊 <i>{esc(u['icebreaker'])}</i>\n"
    return t
