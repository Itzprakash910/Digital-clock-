import math
from db import now

GENDER = {"male": "Male", "female": "Female", "other": "Other"}


def is_premium(u) -> bool:
    return (u.get("premium_until") or 0) > now()


def is_boosted(u) -> bool:
    return (u.get("boost_until") or 0) > now()


def interest_set(u):
    return {x for x in (u.get("interests") or "").split("|") if x}


def compat(a, b) -> int:
    sa, sb = interest_set(a), interest_set(b)
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


def card(u, viewer=None) -> str:
    badges = ""
    if u.get("verified"):
        badges += " ✅"
    if is_premium(u):
        badges += " 💎"
    if is_boosted(u):
        badges += " 🚀"
    t = f"<b>{u['name']}</b>, {u['age']}{badges}\n"
    if viewer:
        d = distance_km(viewer, u)
        if d is not None:
            t += f"📍 ~{max(1, round(d))} km door\n"
        sc = compat(viewer, u)
        if sc:
            t += f"💞 Compatibility: <b>{sc}%</b>\n"
    if u.get("mood") and (u.get("mood_at") or 0) > now() - 86400:
        t += f"🎭 Mood: {u['mood']}\n"
    if u.get("interests"):
        t += "🏷 " + " · ".join(interest_set(u)) + "\n"
    if u.get("bio"):
        t += f"\n💬 {u['bio']}\n"
    if u.get("icebreaker"):
        t += f"\n🧊 <i>{u['icebreaker']}</i>\n"
    return t
