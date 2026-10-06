"""Database layer: PostgreSQL (DATABASE_URL set ho to) ya SQLite (default)."""
import secrets
import time

import aiosqlite

from config import DB_PATH, DATABASE_URL

USE_PG = bool(DATABASE_URL)
_pool = None


def now() -> int:
    return int(time.time())


# Purane DB ke liye auto-migration (naye columns)
USER_COLUMNS = {
    "first_name": "TEXT", "last_name": "TEXT", "language": "TEXT",
    "min_age": "BIGINT DEFAULT 18", "max_age": "BIGINT DEFAULT 99", "max_distance": "DOUBLE PRECISION DEFAULT 100", "online_only": "BIGINT DEFAULT 0",
    "tg_premium": "BIGINT DEFAULT 0", "ref_rewarded": "BIGINT DEFAULT 0",
    "blocked": "BIGINT DEFAULT 0", "last_active": "BIGINT DEFAULT 0",
    "profile_at": "BIGINT DEFAULT 0",
    "likes_received": "BIGINT DEFAULT 0", "likes_given": "BIGINT DEFAULT 0",
    "rating_avg": "DOUBLE PRECISION DEFAULT 0", "rating_count": "BIGINT DEFAULT 0",
}


def _schema() -> str:
    pk = "BIGSERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    return f"""
CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY, first_name TEXT, last_name TEXT, name TEXT, username TEXT,
  language TEXT, tg_premium BIGINT DEFAULT 0,
  age BIGINT, gender TEXT, looking_for TEXT DEFAULT 'all', min_age BIGINT DEFAULT 18, max_age BIGINT DEFAULT 99, max_distance DOUBLE PRECISION DEFAULT 100, online_only BIGINT DEFAULT 0,
  bio TEXT, interests TEXT DEFAULT '', photo TEXT,
  lat DOUBLE PRECISION, lon DOUBLE PRECISION, mood TEXT, mood_at BIGINT DEFAULT 0,
  icebreaker TEXT, premium_until BIGINT DEFAULT 0, boost_until BIGINT DEFAULT 0,
  coins BIGINT DEFAULT 0, ref_code TEXT, referred_by BIGINT, ref_rewarded BIGINT DEFAULT 0,
  views BIGINT DEFAULT 0, banned BIGINT DEFAULT 0, verified BIGINT DEFAULT 0,
  streak BIGINT DEFAULT 0, last_daily BIGINT DEFAULT 0, active BIGINT DEFAULT 1,
  profile_done BIGINT DEFAULT 0, blocked BIGINT DEFAULT 0, last_active BIGINT DEFAULT 0,
  profile_at BIGINT DEFAULT 0, created BIGINT,
  likes_received BIGINT DEFAULT 0, likes_given BIGINT DEFAULT 0,
  rating_avg DOUBLE PRECISION DEFAULT 0, rating_count BIGINT DEFAULT 0
);
CREATE TABLE IF NOT EXISTS swipes (
  id {pk}, from_id BIGINT, to_id BIGINT, type TEXT, ts BIGINT
);
CREATE INDEX IF NOT EXISTS idx_sw_from ON swipes(from_id, to_id);
CREATE INDEX IF NOT EXISTS idx_sw_to ON swipes(to_id, type);
CREATE TABLE IF NOT EXISTS profile_views (profile_id BIGINT, viewer_id BIGINT, ts BIGINT, UNIQUE(profile_id,viewer_id));
CREATE TABLE IF NOT EXISTS achievements (user_id BIGINT, achievement_key TEXT, title TEXT, description TEXT, unlocked BIGINT DEFAULT 0, ts BIGINT, UNIQUE(user_id,achievement_key));
CREATE TABLE IF NOT EXISTS ratings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id BIGINT, rater_id BIGINT, rating BIGINT, ts BIGINT,
  UNIQUE(profile_id,rater_id)
);
CREATE TABLE IF NOT EXISTS contacts (
  user_id BIGINT PRIMARY KEY, telegram_username TEXT, phone TEXT, instagram TEXT,
  facebook TEXT, other_social TEXT, show_telegram BIGINT DEFAULT 1,
  show_phone BIGINT DEFAULT 0, show_social BIGINT DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, chat_key TEXT, sender_id BIGINT,
  receiver_id BIGINT, text TEXT, ts BIGINT
);
CREATE INDEX IF NOT EXISTS idx_chat_messages ON chat_messages(chat_key,ts);
CREATE TABLE IF NOT EXISTS reports (
  id {pk}, reporter BIGINT, reported BIGINT, ts BIGINT
);
CREATE TABLE IF NOT EXISTS payments (
  id {pk}, user_id BIGINT, plan TEXT, amount BIGINT, currency TEXT,
  charge_id TEXT, ts BIGINT
);
CREATE TABLE IF NOT EXISTS profile_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id BIGINT, photo TEXT NOT NULL,
  caption TEXT, position BIGINT DEFAULT 0, created BIGINT
);
CREATE INDEX IF NOT EXISTS idx_posts_user ON profile_posts(user_id, position);
CREATE TABLE IF NOT EXISTS chat_sessions (
  chat_key TEXT PRIMARY KEY, user_a BIGINT, user_b BIGINT,
  first_started BIGINT, last_started BIGINT
);
CREATE TABLE IF NOT EXISTS broadcasts (
  id {pk}, admin_id BIGINT, title TEXT, description TEXT, image TEXT,
  is_product BIGINT DEFAULT 0, price DOUBLE PRECISION, discount BIGINT DEFAULT 0,
  btn_text TEXT, btn_url TEXT, segment TEXT,
  total BIGINT DEFAULT 0, sent BIGINT DEFAULT 0, failed BIGINT DEFAULT 0,
  blocked BIGINT DEFAULT 0, status TEXT DEFAULT 'running', ts BIGINT
);
"""


def _pg(q: str) -> str:
    out, n = [], 0
    for ch in q:
        if ch == "?":
            n += 1
            out.append(f"${n}")
        else:
            out.append(ch)
    return "".join(out)


async def init_db():
    global _pool
    if USE_PG:
        import asyncpg
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with _pool.acquire() as c:
            await c.execute(_schema())
            for n, t in USER_COLUMNS.items():
                await c.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {n} {t}")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(_schema())
            cur = await db.execute("PRAGMA table_info(users)")
            have = {r[1] for r in await cur.fetchall()}
            for n, t in USER_COLUMNS.items():
                if n not in have:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {n} {t}")
            await db.commit()


async def close_db():
    if _pool:
        await _pool.close()


# ---------- low level ----------
async def fetchone(q, args=()):
    if USE_PG:
        async with _pool.acquire() as c:
            r = await c.fetchrow(_pg(q), *args)
            return dict(r) if r else None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(q, args)
        r = await cur.fetchone()
        return dict(r) if r else None


async def fetchall(q, args=()):
    if USE_PG:
        async with _pool.acquire() as c:
            return [dict(r) for r in await c.fetch(_pg(q), *args)]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(q, args)
        return [dict(r) for r in await cur.fetchall()]


async def execute(q, args=()):
    if USE_PG:
        async with _pool.acquire() as c:
            await c.execute(_pg(q), *args)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(q, args)
        await db.commit()


async def insert_id(q, args=()):
    if USE_PG:
        async with _pool.acquire() as c:
            return await c.fetchval(_pg(q) + " RETURNING id", *args)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(q, args)
        await db.commit()
        return cur.lastrowid


# ---------- users ----------
async def get_user(uid):
    return await fetchone("SELECT * FROM users WHERE id=?", (uid,))


async def get_user_by_code(code):
    return await fetchone("SELECT * FROM users WHERE ref_code=?", (code,))


def _tg_fields(tg):
    return (tg.first_name, getattr(tg, "last_name", None), tg.username,
            getattr(tg, "language_code", None), 1 if getattr(tg, "is_premium", None) else 0)


async def create_user(tg, referred_by=None):
    fn, ln, un, lang, tgp = _tg_fields(tg)
    await execute(
        """INSERT INTO users(id,first_name,last_name,name,username,language,tg_premium,
                             ref_code,referred_by,last_active,created)
           VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING""",
        (tg.id, fn, ln, fn, un, lang, tgp, secrets.token_hex(4).upper(),
         referred_by, now(), now()))


async def touch_user(tg):
    """Har interaction par telegram info + last_active update."""
    fn, ln, un, lang, tgp = _tg_fields(tg)
    await execute(
        """UPDATE users SET first_name=?, last_name=?, username=?, language=?, tg_premium=?,
                            last_active=?, blocked=0 WHERE id=?""",
        (fn, ln, un, lang, tgp, now(), tg.id))
    if un:
        await execute("UPDATE contacts SET telegram_username=? WHERE user_id=?", (un,tg.id))


async def update_user(uid, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k}=?" for k in fields)
    await execute(f"UPDATE users SET {keys} WHERE id=?", (*fields.values(), uid))


async def add_coins(uid, amount):
    await execute("UPDATE users SET coins=coins+? WHERE id=?", (int(amount), uid))


async def extend_premium(uid, days):
    u = await get_user(uid)
    base = max(now(), u["premium_until"] or 0)
    await update_user(uid, premium_until=base + int(days) * 86400)


async def reset_profile(uid):
    await execute(
        """UPDATE users SET age=NULL, gender=NULL, bio=NULL, interests='', photo=NULL,
           lat=NULL, lon=NULL, mood=NULL, icebreaker=NULL, profile_done=0 WHERE id=?""", (uid,))
    await execute("DELETE FROM swipes WHERE from_id=? OR to_id=?", (uid, uid))
    await execute("DELETE FROM profile_posts WHERE user_id=?", (uid,))


async def count_referrals(uid):
    r = await fetchone("SELECT COUNT(*) AS c FROM users WHERE referred_by=?", (uid,))
    return r["c"]


# ---------- swipes ----------
async def add_swipe(from_id, to_id, typ):
    # One active swipe per direction; counters stay exact when a user changes like/pass.
    old = await fetchone("SELECT type FROM swipes WHERE from_id=? AND to_id=? ORDER BY id DESC LIMIT 1", (from_id, to_id))
    if old:
        old_type = old.get("type")
        if old_type == typ:
            return False
        await execute("UPDATE swipes SET type=?, ts=? WHERE from_id=? AND to_id=?",
                      (typ, now(), from_id, to_id))
        if old_type in ("like", "super"):
            await execute("UPDATE users SET likes_given=MAX(0,likes_given-1) WHERE id=?", (from_id,))
            await execute("UPDATE users SET likes_received=MAX(0,likes_received-1) WHERE id=?", (to_id,))
    else:
        await execute("INSERT INTO swipes(from_id,to_id,type,ts) VALUES(?,?,?,?)",
                      (from_id, to_id, typ, now()))
    if typ in ("like", "super"):
        await execute("UPDATE users SET likes_given=likes_given+1 WHERE id=?", (from_id,))
        await execute("UPDATE users SET likes_received=likes_received+1 WHERE id=?", (to_id,))
    return True


async def has_swiped(from_id, to_id):
    return bool(await fetchone("SELECT 1 AS x FROM swipes WHERE from_id=? AND to_id=?",
                               (from_id, to_id)))


async def count_swipes_today(uid, types):
    ph = ",".join("?" * len(types))
    r = await fetchone(
        f"SELECT COUNT(*) AS c FROM swipes WHERE from_id=? AND type IN ({ph}) AND ts>?",
        (uid, *types, now() - 86400))
    return r["c"]


async def liked_me(me, target):
    return bool(await fetchone(
        "SELECT 1 AS x FROM swipes WHERE from_id=? AND to_id=? AND type IN ('like','super')",
        (target, me)))


async def last_swipe(uid):
    return await fetchone("SELECT * FROM swipes WHERE from_id=? ORDER BY id DESC LIMIT 1", (uid,))


async def delete_swipe(sid):
    row = await fetchone("SELECT from_id,to_id,type FROM swipes WHERE id=?", (sid,))
    if not row:
        return
    await execute("DELETE FROM swipes WHERE id=?", (sid,))
    if row.get("type") in ("like", "super"):
        await execute("UPDATE users SET likes_given=MAX(0,likes_given-1) WHERE id=?", (row["from_id"],))
        await execute("UPDATE users SET likes_received=MAX(0,likes_received-1) WHERE id=?", (row["to_id"],))


async def get_matches(uid):
    return await fetchall(
        """SELECT u.* FROM users u WHERE u.id IN (
             SELECT a.to_id FROM swipes a JOIN swipes b
             ON a.to_id=b.from_id AND b.to_id=a.from_id
             WHERE a.from_id=? AND a.type IN ('like','super') AND b.type IN ('like','super'))
           AND u.banned=0 AND u.profile_done=1""", (uid,))


async def who_liked_me(uid):
    return await fetchall(
        """SELECT u.* FROM users u WHERE u.id IN (
             SELECT from_id FROM swipes WHERE to_id=? AND type IN ('like','super'))
           AND u.id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)
           AND u.banned=0 AND u.profile_done=1""", (uid, uid))


_BASE = """FROM users WHERE id!=? AND profile_done=1 AND banned=0 AND active=1 AND blocked=0
           AND id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)
           AND (?='all' OR lower(gender)=lower(?))
           AND (lower(looking_for)='all' OR lower(looking_for)=lower(?))"""


async def get_candidate(u):
    rows = await get_pool(u, 100)
    if not rows: return None
    # Simple ranking: boosted, nearby, recent activity.
    from utils import distance_km
    def score(x):
        d=distance_km(u,x)
        dist=0 if d is None else min(d,500)
        engagement=min(100,(x.get("views",0) or 0)*.02+(x.get("likes_received",0) or 0)*2+(x.get("rating_avg",0) or 0)*10)
        recent=min(30,max(0,(x.get("last_active",0)-(now()-7*86400))/(7*86400)*30))
        boost=1000 if (x.get("boost_until") or 0)>now() else 0
        return boost+(300-min(dist,300))+engagement+recent
    rows.sort(key=score,reverse=True)
    return rows[0]


async def get_pool(u, limit=300, need_location=False):
    extra = " AND lat IS NOT NULL" if need_location else ""
    rows = await fetchall(f"SELECT * {_BASE}{extra} ORDER BY boost_until DESC, last_active DESC LIMIT {int(limit)}",
        (u["id"], u["id"], u.get("looking_for") or "all", u.get("looking_for") or "all", u.get("gender") or ""))
    from utils import distance_km
    out=[]
    my_age=int(u.get("age") or 0)
    min_age=int(u.get("min_age") or 18); max_age=int(u.get("max_age") or 99)
    for x in rows:
        age=x.get("age")
        if age is None or not (min_age <= int(age) <= max_age): continue
        # Candidate must also accept my gender and age. This is the reciprocal preference check.
        if u.get("gender") and (x.get("looking_for") or "all").lower() not in ("all", str(u.get("gender")).lower()): continue
        cmin=int(x.get("min_age") or 18); cmax=int(x.get("max_age") or 99)
        if my_age and not (cmin <= my_age <= cmax): continue
        if int(u.get("online_only") or 0) and x.get("last_active",0) < now()-900: continue
        if u.get("lat") is not None and x.get("lat") is not None:
            d=distance_km(u,x)
            if d is not None and d > float(u.get("max_distance") or 100): continue
        out.append(x)
    return out


async def add_view(uid, viewer_id=None):
    if viewer_id is None or int(viewer_id)==int(uid):
        await execute("UPDATE users SET views=views+1 WHERE id=?", (uid,))
        r=await fetchone("SELECT views FROM users WHERE id=?",(uid,)); return int(r["views"] or 0), True
    existing=await fetchone("SELECT 1 AS x FROM profile_views WHERE profile_id=? AND viewer_id=?",(uid,viewer_id))
    if existing:
        await execute("UPDATE profile_views SET ts=? WHERE profile_id=? AND viewer_id=?",(now(),uid,viewer_id))
        r=await fetchone("SELECT views FROM users WHERE id=?",(uid,)); return int(r["views"] or 0), False
    await execute("INSERT INTO profile_views(profile_id,viewer_id,ts) VALUES(?,?,?)",(uid,viewer_id,now()))
    await execute("UPDATE users SET views=views+1 WHERE id=?", (uid,))
    r=await fetchone("SELECT views FROM users WHERE id=?",(uid,)); return int(r["views"] or 0), True


async def add_report(reporter, reported):
    await execute("INSERT INTO reports(reporter,reported,ts) VALUES(?,?,?)",
                  (reporter, reported, now()))
    r = await fetchone("SELECT COUNT(*) AS c FROM reports WHERE reported=?", (reported,))
    return r["c"]


# ---------- admin ----------
async def stats_global():
    t = now()
    s = await fetchone(
        """SELECT
          (SELECT COUNT(*) FROM users) AS users,
          (SELECT COUNT(*) FROM users WHERE profile_done=1) AS profiles,
          (SELECT COUNT(*) FROM users WHERE premium_until>?) AS premium,
          (SELECT COUNT(*) FROM users WHERE banned=1) AS banned,
          (SELECT COUNT(*) FROM users WHERE blocked=1) AS blocked,
          (SELECT COUNT(*) FROM users WHERE last_active>?) AS active24,
          (SELECT COUNT(*) FROM users WHERE last_active>?) AS active7,
          (SELECT COUNT(*) FROM users WHERE created>?) AS new24,
          (SELECT COUNT(*) FROM swipes) AS swipes,
          (SELECT COUNT(*) FROM payments) AS payments,
          (SELECT COUNT(*) FROM reports) AS reports""",
        (t, t - 86400, t - 7 * 86400, t - 86400))
    m = await fetchone(
        """SELECT COUNT(*) AS c FROM swipes a JOIN swipes b
           ON a.to_id=b.from_id AND a.from_id=b.to_id
           WHERE a.from_id<a.to_id AND a.type IN ('like','super') AND b.type IN ('like','super')""")
    s["matches"] = m["c"]
    rev = await fetchall("SELECT currency, SUM(amount) AS s FROM payments GROUP BY currency")
    s["revenue"] = {r["currency"]: int(r["s"] or 0) for r in rev}
    return s


async def count_users():
    return (await fetchone("SELECT COUNT(*) AS c FROM users"))["c"]


async def users_page(offset, limit):
    return await fetchall("SELECT * FROM users ORDER BY created DESC LIMIT ? OFFSET ?",
                          (limit, offset))


async def search_users(q):
    q = q.strip().lstrip("@").lower()
    uid = int(q) if q.isdigit() else -1
    like = f"%{q}%"
    return await fetchall(
        """SELECT * FROM users WHERE id=? OR LOWER(username)=? OR LOWER(name) LIKE ?
           OR LOWER(first_name) LIKE ? LIMIT 10""", (uid, q, like, like))


async def all_users():
    return await fetchall("SELECT * FROM users ORDER BY created")


async def recent_reports(limit=10):
    return await fetchall(
        """SELECT r.reported, COUNT(*) AS c, MAX(r.ts) AS t, u.name, u.username
           FROM reports r LEFT JOIN users u ON u.id=r.reported
           GROUP BY r.reported, u.name, u.username ORDER BY t DESC LIMIT ?""", (limit,))


async def recent_payments(limit=10):
    return await fetchall(
        """SELECT p.*, u.name, u.username FROM payments p
           LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id DESC LIMIT ?""", (limit,))


_SEG = {
    "all": ("", ()),
    "profiles": (" AND profile_done=1", ()),
    "premium": (" AND premium_until>?", "now"),
    "free": (" AND premium_until<=?", "now"),
    "active7": (" AND last_active>?", "week"),
    "incomplete": (" AND profile_done=0", ()),
}


async def audience(segment):
    cond, arg = _SEG[segment]
    args = ()
    if arg == "now":
        args = (now(),)
    elif arg == "week":
        args = (now() - 7 * 86400,)
    rows = await fetchall(f"SELECT id FROM users WHERE banned=0 AND blocked=0{cond}", args)
    return [r["id"] for r in rows]


async def create_broadcast(admin_id, d, segment, total):
    return await insert_id(
        """INSERT INTO broadcasts(admin_id,title,description,image,is_product,price,discount,
                                  btn_text,btn_url,segment,total,ts)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (admin_id, d["title"], d["desc"], d.get("photo"), 1 if d.get("is_product") else 0,
         d.get("price"), int(d.get("discount") or 0), d.get("btn_text"), d.get("btn_url"),
         segment, total, now()))


async def finish_broadcast(bid, sent, failed, blocked):
    await execute("UPDATE broadcasts SET sent=?, failed=?, blocked=?, status='done' WHERE id=?",
                  (sent, failed, blocked, bid))


async def recent_broadcasts(limit=10):
    return await fetchall("SELECT * FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,))


# ---------- ConnectMate additions ----------
async def add_post(uid, photo, caption=""):
    r = await fetchone("SELECT COALESCE(MAX(position),0)+1 AS p FROM profile_posts WHERE user_id=?", (uid,))
    pos = int(r["p"] or 1)
    return await insert_id("INSERT INTO profile_posts(user_id,photo,caption,position,created) VALUES(?,?,?,?,?)",
                           (uid, photo, caption, pos, now()))

async def list_posts(uid):
    return await fetchall("SELECT * FROM profile_posts WHERE user_id=? ORDER BY position,id", (uid,))

async def delete_post(uid, post_id):
    r = await fetchone("SELECT id FROM profile_posts WHERE id=? AND user_id=?", (post_id, uid))
    if not r: return False
    await execute("DELETE FROM profile_posts WHERE id=? AND user_id=?", (post_id, uid))
    rows = await list_posts(uid)
    for i,row in enumerate(rows,1):
        await execute("UPDATE profile_posts SET position=? WHERE id=?", (i,row["id"]))
    return True

async def add_rating(rater, profile_id, value):
    value=max(1,min(5,int(value)))
    # one rating per rater/profile
    await execute("DELETE FROM ratings WHERE profile_id=? AND rater_id=?", (profile_id,rater))
    await execute("INSERT INTO ratings(profile_id,rater_id,rating,ts) VALUES(?,?,?,?)",
                  (profile_id,rater,value,now()))
    r=await fetchone("SELECT AVG(rating) AS avg, COUNT(*) AS c FROM ratings WHERE profile_id=?", (profile_id,))
    avg=round(float(r["avg"] or 0),2); count=int(r["c"] or 0)
    await update_user(profile_id,rating_avg=avg,rating_count=count)
    return avg,count

async def get_rating(rater, profile_id):
    r=await fetchone("SELECT rating FROM ratings WHERE profile_id=? AND rater_id=?", (profile_id,rater))
    return r["rating"] if r else None

async def set_contacts(uid, **contacts):
    allowed={"telegram_username","phone","instagram","facebook","other_social","show_telegram","show_phone","show_social"}
    vals={k:v for k,v in contacts.items() if k in allowed}
    if not vals: return
    existing=await fetchone("SELECT * FROM contacts WHERE user_id=?", (uid,))
    if not existing:
        await execute("INSERT INTO contacts(user_id) VALUES(?)",(uid,))
    for k,v in vals.items():
        await execute(f"UPDATE contacts SET {k}=? WHERE user_id=?",(v,uid))

async def get_contacts(uid):
    return await fetchone("SELECT * FROM contacts WHERE user_id=?", (uid,))

async def can_view_contacts(viewer_id, profile_id):
    if int(viewer_id)==int(profile_id): return True
    v=await get_user(viewer_id)
    if not v or (v.get("premium_until") or 0)<=now(): return False
    ms=await get_matches(viewer_id)
    return any(int(x["id"])==int(profile_id) for x in ms)

async def _chat_key(a,b):
    a,b=sorted((int(a),int(b))); return f"{a}:{b}"

async def has_chat_session(a,b):
    return bool(await fetchone("SELECT 1 FROM chat_sessions WHERE chat_key=?", (await _chat_key(a,b),)))

async def start_chat_session(a,b):
    key=await _chat_key(a,b); t=now()
    await execute("""INSERT INTO chat_sessions(chat_key,user_a,user_b,first_started,last_started)
                     VALUES(?,?,?,?,?) ON CONFLICT(chat_key) DO UPDATE SET last_started=excluded.last_started""",
                  (key,*sorted((int(a),int(b))),t,t))

async def count_chat_starts_today(uid):
    r=await fetchone("SELECT COUNT(*) AS c FROM chat_sessions WHERE first_started> ? AND (user_a=? OR user_b=?)",
                     (now()-86400,uid,uid))
    return int(r["c"] or 0)

async def save_chat_message(sender_id, receiver_id, text):
    key=await _chat_key(sender_id,receiver_id)
    await execute("INSERT INTO chat_messages(chat_key,sender_id,receiver_id,text,ts) VALUES(?,?,?,?,?)",
                  (key,sender_id,receiver_id,text,now()))

async def get_chat_messages(user_id,other_id,limit=50):
    key=await _chat_key(user_id,other_id)
    return await fetchall("SELECT * FROM chat_messages WHERE chat_key=? ORDER BY ts DESC LIMIT ?",(key,limit))

async def count_likes_given(uid):
    r=await fetchone("SELECT COUNT(*) AS c FROM swipes WHERE from_id=? AND type IN ('like','super')",(uid,))
    return int(r["c"] or 0)
async def count_likes_received(uid):
    r=await fetchone("SELECT COUNT(*) AS c FROM swipes WHERE to_id=? AND type IN ('like','super')",(uid,))
    return int(r["c"] or 0)
async def get_liked_profiles(uid):
    return await fetchall("""SELECT u.* FROM users u JOIN swipes s ON s.to_id=u.id
                           WHERE s.from_id=? AND s.type IN ('like','super')
                           AND u.banned=0 AND u.profile_done=1 ORDER BY s.ts DESC""",(uid,))
async def get_profile_viewers(uid, limit=50):
    return await fetchall("""SELECT u.*, pv.ts AS viewed_at FROM profile_views pv
                           JOIN users u ON u.id=pv.viewer_id
                           WHERE pv.profile_id=? AND u.profile_done=1 AND u.banned=0
                           ORDER BY pv.ts DESC LIMIT ?""",(uid,int(limit)))

async def unlock_achievement(uid, key, title, description):
    try:
        await execute("INSERT INTO achievements(user_id,achievement_key,title,description,unlocked,ts) VALUES(?,?,?,?,1,?)",
                      (uid,key,title,description,now()))
        return True
    except Exception:
        return False


async def delete_user(uid):
    for table,col in (("swipes","from_id"),("swipes","to_id"),("reports","reporter"),("reports","reported"),
                      ("payments","user_id"),("profile_posts","user_id"),("profile_views","profile_id"),
                      ("ratings","profile_id")):
        await execute(f"DELETE FROM {table} WHERE {col}=?", (uid,))
    await execute("DELETE FROM users WHERE id=?", (uid,))
