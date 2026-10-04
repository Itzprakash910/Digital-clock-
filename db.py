import secrets
import time
import aiosqlite
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, name TEXT, username TEXT,
  age INTEGER, gender TEXT, looking_for TEXT DEFAULT 'all',
  bio TEXT, interests TEXT DEFAULT '', photo TEXT,
  lat REAL, lon REAL, mood TEXT, mood_at INTEGER DEFAULT 0,
  icebreaker TEXT, premium_until INTEGER DEFAULT 0, boost_until INTEGER DEFAULT 0,
  coins INTEGER DEFAULT 0, ref_code TEXT, referred_by INTEGER,
  views INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, verified INTEGER DEFAULT 0,
  streak INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0,
  active INTEGER DEFAULT 1, profile_done INTEGER DEFAULT 0, created INTEGER
);
CREATE TABLE IF NOT EXISTS swipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER, to_id INTEGER,
  type TEXT, ts INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sw_from ON swipes(from_id, to_id);
CREATE INDEX IF NOT EXISTS idx_sw_to ON swipes(to_id, type);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, reporter INTEGER, reported INTEGER, ts INTEGER
);
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan TEXT,
  amount INTEGER, currency TEXT, charge_id TEXT, ts INTEGER
);
"""


def now() -> int:
    return int(time.time())


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def fetchone(q, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(q, args)
        r = await cur.fetchone()
        return dict(r) if r else None


async def fetchall(q, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(q, args)
        return [dict(r) for r in await cur.fetchall()]


async def execute(q, args=()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(q, args)
        await db.commit()


# ---------- users ----------
async def get_user(uid):
    return await fetchone("SELECT * FROM users WHERE id=?", (uid,))


async def get_user_by_code(code):
    return await fetchone("SELECT * FROM users WHERE ref_code=?", (code,))


async def create_user(uid, name, username, referred_by=None):
    await execute(
        "INSERT OR IGNORE INTO users(id,name,username,ref_code,referred_by,created) VALUES(?,?,?,?,?,?)",
        (uid, name, username, secrets.token_hex(4).upper(), referred_by, now()))


async def update_user(uid, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k}=?" for k in fields)
    await execute(f"UPDATE users SET {keys} WHERE id=?", (*fields.values(), uid))


async def add_coins(uid, amount):
    await execute("UPDATE users SET coins=coins+? WHERE id=?", (amount, uid))


async def extend_premium(uid, days):
    u = await get_user(uid)
    base = max(now(), u["premium_until"] or 0)
    await update_user(uid, premium_until=base + days * 86400)


# ---------- swipes ----------
async def add_swipe(from_id, to_id, typ):
    await execute("INSERT INTO swipes(from_id,to_id,type,ts) VALUES(?,?,?,?)",
                  (from_id, to_id, typ, now()))


async def count_swipes_today(uid, types):
    ph = ",".join("?" * len(types))
    r = await fetchone(
        f"SELECT COUNT(*) c FROM swipes WHERE from_id=? AND type IN ({ph}) AND ts>?",
        (uid, *types, now() - 86400))
    return r["c"]


async def liked_me(me, target):
    r = await fetchone(
        "SELECT 1 x FROM swipes WHERE from_id=? AND to_id=? AND type IN ('like','super')",
        (target, me))
    return bool(r)


async def last_swipe(uid):
    return await fetchone("SELECT * FROM swipes WHERE from_id=? ORDER BY id DESC LIMIT 1", (uid,))


async def delete_swipe(sid):
    await execute("DELETE FROM swipes WHERE id=?", (sid,))


async def get_matches(uid):
    return await fetchall(
        """SELECT u.* FROM users u WHERE u.id IN (
             SELECT a.to_id FROM swipes a JOIN swipes b
             ON a.to_id=b.from_id AND b.to_id=a.from_id
             WHERE a.from_id=? AND a.type IN ('like','super') AND b.type IN ('like','super'))""",
        (uid,))


async def who_liked_me(uid):
    return await fetchall(
        """SELECT u.* FROM users u WHERE u.id IN (
             SELECT from_id FROM swipes WHERE to_id=? AND type IN ('like','super'))
           AND u.id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)""", (uid, uid))


async def get_candidate(u):
    return await fetchone(
        """SELECT * FROM users WHERE id!=? AND profile_done=1 AND banned=0 AND active=1
           AND id NOT IN (SELECT to_id FROM swipes WHERE from_id=?)
           AND (?='all' OR gender=?)
           AND (looking_for='all' OR looking_for=? OR ?='other')
           ORDER BY (boost_until>?) DESC,
                    (mood IS NOT NULL AND mood=? AND mood_at>?) DESC,
                    RANDOM() LIMIT 1""",
        (u["id"], u["id"], u["looking_for"], u["looking_for"], u["gender"], u["gender"],
         now(), u["mood"] or "", now() - 86400))


async def nearby_pool(u, limit=300):
    return await fetchall(
        """SELECT * FROM users WHERE id!=? AND profile_done=1 AND banned=0 AND active=1
           AND lat IS NOT NULL AND (?='all' OR gender=?) LIMIT ?""",
        (u["id"], u["looking_for"], u["looking_for"], limit))


async def add_view(uid):
    await execute("UPDATE users SET views=views+1 WHERE id=?", (uid,))


async def add_report(reporter, reported):
    await execute("INSERT INTO reports(reporter,reported,ts) VALUES(?,?,?)",
                  (reporter, reported, now()))
    r = await fetchone("SELECT COUNT(*) c FROM reports WHERE reported=?", (reported,))
    return r["c"]


async def stats_global():
    return await fetchone(
        """SELECT (SELECT COUNT(*) FROM users) users,
                  (SELECT COUNT(*) FROM users WHERE profile_done=1) profiles,
                  (SELECT COUNT(*) FROM users WHERE premium_until>strftime('%s','now')) premium,
                  (SELECT COUNT(*) FROM swipes) swipes,
                  (SELECT COUNT(*) FROM payments) payments""")


async def all_user_ids():
    return [r["id"] for r in await fetchall("SELECT id FROM users WHERE banned=0")]
