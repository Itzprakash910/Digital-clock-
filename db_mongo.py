"""Persistent MongoDB database layer for Tele Tinder.

The application stores public profiles, private contacts, swipes, matches,
ratings, reports, payments, broadcasts and chat metadata in separate
collections. Telegram user id is the stable application key.
"""
import os, secrets, time
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, GEOSPHERE
from config import MONGODB_URI, MONGODB_DB

client = None
mongo = None
USE_MONGO = True
USE_PG = False


def now(): return int(time.time())


def _doc(d):
    if not d: return None
    d = dict(d)
    d.pop("_id", None)
    return d


async def init_db():
    global client, mongo
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is empty. Add it to .env")
    client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
    await client.admin.command("ping")
    mongo = client[MONGODB_DB]
    # Stable indexes. Re-running init is safe.
    await mongo.users.create_index([("id", ASCENDING)], unique=True)
    await mongo.users.create_index([("ref_code", ASCENDING)], unique=True, sparse=True)
    await mongo.users.create_index([("username", ASCENDING)])
    await mongo.users.create_index([("created", DESCENDING)])
    await mongo.users.create_index([("last_active", DESCENDING)])
    await mongo.users.create_index([("location", GEOSPHERE)], sparse=True)
    await mongo.swipes.create_index([("from_id", ASCENDING), ("to_id", ASCENDING)], unique=True)
    await mongo.swipes.create_index([("to_id", ASCENDING), ("type", ASCENDING)])
    await mongo.profile_views.create_index([("profile_id", ASCENDING), ("viewer_id", ASCENDING)], unique=True)
    await mongo.ratings.create_index([("profile_id", ASCENDING), ("rater_id", ASCENDING)], unique=True)
    await mongo.payments.create_index([("user_id", ASCENDING), ("ts", DESCENDING)])
    await mongo.reports.create_index([("reported", ASCENDING), ("ts", DESCENDING)])
    await mongo.chats.create_index([("participants", ASCENDING)])
    await mongo.chat_messages.create_index([("chat_key", ASCENDING), ("ts", ASCENDING)])
    await mongo.admin_logs.create_index([("ts", DESCENDING)])


async def close_db():
    global client
    if client:
        client.close()
        client = None


async def get_user(uid): return _doc(await mongo.users.find_one({"id": int(uid)}))
async def get_user_by_code(code): return _doc(await mongo.users.find_one({"ref_code": code}))


def _tg_fields(tg):
    return (tg.first_name, getattr(tg, "last_name", None), tg.username,
            getattr(tg, "language_code", None), 1 if getattr(tg, "is_premium", None) else 0)


async def create_user(tg, referred_by=None):
    fn, ln, un, lang, tgp = _tg_fields(tg)
    doc = {
        "id": int(tg.id), "first_name": fn, "last_name": ln, "name": fn, "username": un,
        "language": lang, "tg_premium": tgp, "age": None, "gender": None,
        "looking_for": "all", "bio": None, "interests": "", "photo": None,
        "lat": None, "lon": None, "location": None, "mood": None, "mood_at": 0,
        "icebreaker": None, "premium_until": 0, "boost_until": 0, "coins": 0,
        "ref_code": secrets.token_hex(4).upper(), "referred_by": referred_by,
        "ref_rewarded": 0, "views": 0, "likes_received": 0, "likes_given": 0,
        "rating_avg": 0.0, "rating_count": 0, "banned": 0, "verified": 0,
        "streak": 0, "last_daily": 0, "active": 1, "profile_done": 0,
        "blocked": 0, "last_active": now(), "profile_at": 0, "created": now(),
        # Private contact fields. Never render them in card().
        "contacts": {"telegram_username": None, "phone": None, "instagram": None,
                      "facebook": None, "other_social": None,
                      "show_telegram": 1, "show_phone": 0, "show_social": 0},
    }
    await mongo.users.update_one({"id": int(tg.id)}, {"$setOnInsert": doc}, upsert=True)


async def touch_user(tg):
    fn, ln, un, lang, tgp = _tg_fields(tg)
    await mongo.users.update_one({"id": int(tg.id)}, {"$set": {
        "first_name": fn, "last_name": ln, "username": un, "language": lang,
        "tg_premium": tgp, "last_active": now(), "blocked": 0,
    }}, upsert=True)


async def update_user(uid, **fields):
    if fields:
        if "lat" in fields and "lon" in fields and fields.get("lat") is not None and fields.get("lon") is not None:
            fields["location"] = {"type": "Point", "coordinates": [fields["lon"], fields["lat"]]}
        await mongo.users.update_one({"id": int(uid)}, {"$set": fields})

async def log_admin(admin_id, action, target_id=None, data=None):
    await mongo.admin_logs.insert_one({"admin_id": int(admin_id), "action": action,
                                       "target_id": int(target_id) if target_id is not None else None,
                                       "data": data or {}, "ts": now()})


async def add_coins(uid, amount):
    await mongo.users.update_one({"id": int(uid)}, {"$inc": {"coins": int(amount)}})


async def extend_premium(uid, days):
    u = await get_user(uid)
    base = max(now(), int(u.get("premium_until") or 0))
    await update_user(uid, premium_until=base + int(days) * 86400)


async def reset_profile(uid):
    await mongo.users.update_one({"id": int(uid)}, {"$set": {
        "age": None, "gender": None, "bio": None, "interests": "", "photo": None,
        "lat": None, "lon": None, "location": None, "mood": None,
        "icebreaker": None, "profile_done": 0,
    }})
    await mongo.swipes.delete_many({"$or": [{"from_id": int(uid)}, {"to_id": int(uid)}]})


async def count_referrals(uid): return await mongo.users.count_documents({"referred_by": int(uid)})
async def count_users(): return await mongo.users.count_documents({})


async def add_swipe(from_id, to_id, typ):
    await mongo.swipes.update_one({"from_id": int(from_id), "to_id": int(to_id)},
        {"$set": {"type": typ, "ts": now()}}, upsert=True)
    if typ in ("like", "super"):
        await mongo.users.update_one({"id": int(from_id)}, {"$inc": {"likes_given": 1}})
        await mongo.users.update_one({"id": int(to_id)}, {"$inc": {"likes_received": 1}})


async def has_swiped(from_id, to_id):
    return bool(await mongo.swipes.find_one({"from_id": int(from_id), "to_id": int(to_id)}))


async def count_swipes_today(uid, types):
    return await mongo.swipes.count_documents({"from_id": int(uid), "type": {"$in": list(types)},
                                                "ts": {"$gt": now() - 86400}})


async def liked_me(me, target):
    return bool(await mongo.swipes.find_one({"from_id": int(target), "to_id": int(me),
                                              "type": {"$in": ["like", "super"]}}))


async def last_swipe(uid): return _doc(await mongo.swipes.find_one({"from_id": int(uid)}, sort=[("ts", DESCENDING)]))


async def delete_swipe(sid):
    # Mongo _id is not exposed; sid can be an ObjectId string or the last swipe doc.
    from bson import ObjectId
    try: await mongo.swipes.delete_one({"_id": ObjectId(str(sid))})
    except Exception: pass


async def get_matches(uid):
    uid = int(uid)
    mine = await mongo.swipes.find({"from_id": uid, "type": {"$in": ["like", "super"]}}, {"to_id": 1}).to_list(None)
    ids = [x["to_id"] for x in mine]
    if not ids: return []
    mutual = await mongo.swipes.find({"from_id": {"$in": ids}, "to_id": uid,
                                      "type": {"$in": ["like", "super"]}}, {"from_id": 1}).to_list(None)
    mids = [x["from_id"] for x in mutual]
    return [_doc(x) async for x in mongo.users.find({"id": {"$in": mids}, "banned": 0, "profile_done": 1})]


async def who_liked_me(uid):
    uid = int(uid)
    incoming = await mongo.swipes.find({"to_id": uid, "type": {"$in": ["like", "super"]}}, {"from_id": 1}).to_list(None)
    ids = [x["from_id"] for x in incoming]
    if not ids: return []
    already = await mongo.swipes.find({"from_id": uid, "to_id": {"$in": ids}}, {"to_id": 1}).to_list(None)
    done = {x["to_id"] for x in already}
    ids = [x for x in ids if x not in done]
    return [_doc(x) async for x in mongo.users.find({"id": {"$in": ids}, "banned": 0, "profile_done": 1})]


def _eligible_filter(u):
    q = {"id": {"$ne": int(u["id"]),}, "profile_done": 1, "banned": 0, "active": 1, "blocked": 0}
    if u.get("looking_for") not in (None, "all"): q["gender"] = u["looking_for"]
    q["looking_for"] = {"$in": ["all", u.get("gender")]} if u.get("gender") else "all"
    return q


async def _seen_ids(uid):
    rows = await mongo.swipes.find({"from_id": int(uid)}, {"to_id": 1}).to_list(None)
    return [x["to_id"] for x in rows]


async def get_pool(u, limit=300, need_location=False):
    q = _eligible_filter(u)
    q["id"] = {"$ne": int(u["id"]), "$nin": await _seen_ids(u["id"])}
    if need_location: q["lat"] = {"$ne": None}
    rows = [_doc(x) async for x in mongo.users.find(q).limit(int(limit))]
    return rows


async def get_candidate(u):
    rows = await get_pool(u, 100)
    if not rows: return None
    # Ranking: nearby first, then engagement/reputation/recent activity, with boost first.
    from utils import distance_km
    def score(x):
        d = distance_km(u, x)
        dist = 0 if d is None else min(d, 500)
        engagement = min(100, (x.get("views", 0) or 0) * .02 + (x.get("likes_received", 0) or 0) * 2 + (x.get("rating_avg", 0) or 0) * 10)
        recent = min(30, max(0, (x.get("last_active", 0) - (now()-7*86400)) / (7*86400) * 30))
        boost = 1000 if (x.get("boost_until") or 0) > now() else 0
        return boost + (300 - min(dist, 300)) + engagement + recent
    rows.sort(key=score, reverse=True)
    return rows[0]


async def add_view(uid, viewer_id=None):
    await mongo.users.update_one({"id": int(uid)}, {"$inc": {"views": 1}})
    if viewer_id is not None and int(viewer_id) != int(uid):
        await mongo.profile_views.update_one({"profile_id": int(uid), "viewer_id": int(viewer_id)},
            {"$set": {"ts": now()}}, upsert=True)


async def add_report(reporter, reported):
    await mongo.reports.insert_one({"reporter": int(reporter), "reported": int(reported), "ts": now()})
    return await mongo.reports.count_documents({"reported": int(reported)})


async def add_rating(rater, profile_id, value):
    value = max(1, min(5, int(value)))
    await mongo.ratings.update_one({"profile_id": int(profile_id), "rater_id": int(rater)},
                                   {"$set": {"rating": value, "ts": now()}}, upsert=True)
    vals = await mongo.ratings.find({"profile_id": int(profile_id)}, {"rating": 1}).to_list(None)
    avg = round(sum(x["rating"] for x in vals) / len(vals), 2) if vals else 0
    await update_user(profile_id, rating_avg=avg, rating_count=len(vals))
    return avg, len(vals)


async def get_rating(rater, profile_id):
    x = await mongo.ratings.find_one({"profile_id": int(profile_id), "rater_id": int(rater)})
    return x.get("rating") if x else None


async def set_contacts(uid, **contacts):
    allowed = {"telegram_username", "phone", "instagram", "facebook", "other_social",
               "show_telegram", "show_phone", "show_social"}
    clean = {k: v for k, v in contacts.items() if k in allowed}
    if clean: await mongo.users.update_one({"id": int(uid)}, {"$set": {f"contacts.{k}": v for k, v in clean.items()}})


async def get_contacts(uid):
    u = await get_user(uid)
    return (u or {}).get("contacts") or {}


async def can_view_contacts(viewer_id, profile_id):
    if int(viewer_id) == int(profile_id): return True
    v = await get_user(viewer_id)
    if not v or (v.get("premium_until") or 0) <= now(): return False
    ms = await get_matches(viewer_id)
    return any(int(x["id"]) == int(profile_id) for x in ms)


async def save_chat_message(sender_id, receiver_id, text):
    a, b = sorted((int(sender_id), int(receiver_id)))
    key = f"{a}:{b}"
    await mongo.chat_messages.insert_one({"chat_key": key, "sender_id": int(sender_id),
                                          "receiver_id": int(receiver_id), "text": text, "ts": now()})

async def get_chat_messages(user_id, other_id, limit=50):
    a, b = sorted((int(user_id), int(other_id)))
    key = f"{a}:{b}"
    return [_doc(x) async for x in mongo.chat_messages.find({"chat_key": key}).sort("ts", DESCENDING).limit(int(limit))]

async def add_payment(user_id, plan, amount, currency, charge_id):
    await mongo.payments.insert_one({"user_id": int(user_id), "plan": plan, "amount": int(amount),
                                     "currency": currency, "charge_id": charge_id, "ts": now()})


async def count_likes_given(uid): return await mongo.swipes.count_documents({"from_id": int(uid), "type": {"$ne": "pass"}})
async def count_likes_received(uid): return await mongo.swipes.count_documents({"to_id": int(uid), "type": {"$ne": "pass"}})


async def stats_global():
    t = now()
    s = {
        "users": await mongo.users.count_documents({}),
        "profiles": await mongo.users.count_documents({"profile_done": 1}),
        "premium": await mongo.users.count_documents({"premium_until": {"$gt": t}}),
        "banned": await mongo.users.count_documents({"banned": 1}),
        "blocked": await mongo.users.count_documents({"blocked": 1}),
        "active24": await mongo.users.count_documents({"last_active": {"$gt": t-86400}}),
        "active7": await mongo.users.count_documents({"last_active": {"$gt": t-7*86400}}),
        "new24": await mongo.users.count_documents({"created": {"$gt": t-86400}}),
        "swipes": await mongo.swipes.count_documents({}),
        "payments": await mongo.payments.count_documents({}),
        "reports": await mongo.reports.count_documents({}),
    }
    matches = 0
    async for a in mongo.swipes.find({"type": {"$in": ["like", "super"]}, "from_id": {"$lt": 10**30}}):
        b = await mongo.swipes.find_one({"from_id": a["to_id"], "to_id": a["from_id"], "type": {"$in": ["like", "super"]}})
        if b and a["from_id"] < a["to_id"]: matches += 1
    s["matches"] = matches
    rev = {}
    async for r in mongo.payments.aggregate([{"$group": {"_id": "$currency", "s": {"$sum": "$amount"}}}]): rev[r["_id"]] = int(r["s"] or 0)
    s["revenue"] = rev
    return s


async def users_page(offset, limit):
    return [_doc(x) async for x in mongo.users.find({}).sort("created", DESCENDING).skip(int(offset)).limit(int(limit))]

async def search_users(q):
    q = q.strip().lstrip("@").lower(); uid = int(q) if q.isdigit() else -1
    return [_doc(x) async for x in mongo.users.find({"$or": [{"id": uid}, {"username": {"$regex": q, "$options": "i"}},
        {"name": {"$regex": q, "$options": "i"}}, {"first_name": {"$regex": q, "$options": "i"}}]}).limit(10)]

async def all_users(): return [_doc(x) async for x in mongo.users.find({}).sort("created", ASCENDING)]

async def recent_reports(limit=10):
    return [dict(x) async for x in mongo.reports.aggregate([
        {"$group": {"_id": "$reported", "c": {"$sum": 1}, "t": {"$max": "$ts"}}},
        {"$sort": {"t": -1}}, {"$limit": int(limit)}])]

async def recent_payments(limit=10): return [_doc(x) async for x in mongo.payments.find({}).sort("ts", DESCENDING).limit(int(limit))]

async def audience(segment):
    q = {"banned": 0, "blocked": 0}; t = now()
    if segment == "profiles": q["profile_done"] = 1
    elif segment == "premium": q["premium_until"] = {"$gt": t}
    elif segment == "free": q["premium_until"] = {"$lte": t}
    elif segment == "active7": q["last_active"] = {"$gt": t-7*86400}
    elif segment == "incomplete": q["profile_done"] = 0
    return [x["id"] async for x in mongo.users.find(q, {"id": 1})]

async def create_broadcast(admin_id, d, segment, total):
    r = await mongo.broadcasts.insert_one({"admin_id": int(admin_id), "title": d["title"], "description": d["desc"],
        "image": d.get("photo"), "is_product": bool(d.get("is_product")), "price": d.get("price"),
        "discount": int(d.get("discount") or 0), "btn_text": d.get("btn_text"), "btn_url": d.get("btn_url"),
        "segment": segment, "total": total, "sent": 0, "failed": 0, "blocked": 0, "status": "running", "ts": now()})
    return str(r.inserted_id)

async def finish_broadcast(bid, sent, failed, blocked):
    from bson import ObjectId
    await mongo.broadcasts.update_one({"_id": ObjectId(str(bid))}, {"$set": {"sent": sent, "failed": failed, "blocked": blocked, "status": "done"}})

async def recent_broadcasts(limit=10): return [_doc(x) async for x in mongo.broadcasts.find({}).sort("ts", DESCENDING).limit(int(limit))]

# Compatibility helpers for the two legacy call sites. New code should use add_payment/count_*.
async def fetchone(q, args=()):
    q = q.upper()
    if "COUNT(*) AS C FROM SWIPES WHERE FROM_ID" in q: return {"c": await count_likes_given(args[0])}
    if "COUNT(*) AS C FROM SWIPES WHERE TO_ID" in q: return {"c": await count_likes_received(args[0])}
    raise RuntimeError("Raw SQL fetchone is not supported on MongoDB; use a db_* helper")

async def execute(q, args=()):
    q2 = " ".join(q.upper().split())
    if q2.startswith("INSERT INTO PAYMENTS"):
        return await add_payment(args[0], args[1], args[2], args[3], args[4])
    raise RuntimeError("Raw SQL execute is not supported on MongoDB; use a db_* helper")
