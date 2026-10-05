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
    "tg_premium": "BIGINT DEFAULT 0", "ref_rewarded": "BIGINT DEFAULT 0",
    "blocked": "BIGINT DEFAULT 0", "last_active": "BIGINT DEFAULT 0",
    "profile_at": "BIGINT DEFAULT 0",
}


def _schema() -> str:
    pk = "BIGSERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    return f"""
CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY, first_name TEXT, last_name TEXT, name TEXT, username TEXT,
  language TEXT, tg_premium BIGINT DEFAULT 0,
  age BIGINT, gender TEXT, looking_for TEXT DEFAULT 'all',
  bio TEXT, interests TEXT DEFAULT '', photo TEXT,
  lat DOUBLE PRECISION, lon DOUBLE PRECISION, mood TEXT, mood_at BIGINT DEFAULT 0,
  icebreaker TEXT, premium_until BIGINT DEFAULT 0, boost_until BIGINT DEFAULT 0,
  coins BIGINT DEFAULT 0, ref_code TEXT, referred_by BIGINT, ref_rewarded BIGINT DEFAULT 0,
  views BIGINT DEFAULT 0, banned BIGINT DEFAULT 0, verified BIGINT DEFAULT 0,
  streak BIGINT DEFAULT 0, last_daily BIGINT DEFAULT 0, active BIGINT DEFAULT 1,
  profile_done BIGINT DEFAULT 0, blocked BIGINT DEFAULT 0, last_active BIGINT DEFAULT 0,
  profile_at BIGINT DEFAULT 0, created BIGINT
);
CREATE TABLE IF NOT EXISTS swipes (
  id {pk}, from_id BIGINT, to_id BIGINT, type TEXT, ts BIGINT
);
CREATE INDEX IF NOT EXISTS idx_sw_from ON swipes(from_id, to_id);
CREATE INDEX IF NOT EXISTS idx_sw_to ON swipes(to_id, type);
CREATE TABLE IF NOT EXISTS reports (
  id {pk}, reporter BIGINT, reported BIGINT, ts BIGINT
);
CREATE TABLE IF NOT EXISTS payments (
  id {pk}, user_id BIGINT, plan TEXT, amount BIGINT, currency TEXT,
  charge_id TEXT, ts BIGINT
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


async def count_referrals(uid):
    r = await fetchone("SELECT COUNT(*) AS c FROM users WHERE referred_by=?", (uid,))
    return r["c"]


# ---------- swipes ----------
async def add_swipe(from_id, to_id, typ):
    await execute("INSERT INTO swipes(from_id,to_id,type,ts) VALUES(?,?,?,?)",
                  (from_id, to_id, typ, now()))


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
    await execute("DELETE FROM swipes WHERE id=?", (sid,))


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
           AND (CAST(? AS TEXT)='all' OR gender=?)
           AND (looking_for='all' OR looking_for=?)"""


async def get_candidate(u):
    t = now()
    return await fetchone(
        f"""SELECT * {_BASE}
            ORDER BY (boost_until>?) DESC,
                     (mood IS NOT NULL AND mood=? AND mood_at>?) DESC,
                     RANDOM() LIMIT 1""",
        (u["id"], u["id"], u["looking_for"], u["looking_for"], u["gender"],
         t, u["mood"] or "", t - 86400))


async def get_pool(u, limit=300, need_location=False):
    extra = " AND lat IS NOT NULL" if need_location else ""
    return await fetchall(
        f"SELECT * {_BASE}{extra} ORDER BY RANDOM() LIMIT {int(limit)}",
        (u["id"], u["id"], u["looking_for"], u["looking_for"], u["gender"]))


async def add_view(uid):
    await execute("UPDATE users SET views=views+1 WHERE id=?", (uid,))


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
