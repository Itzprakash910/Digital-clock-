"""One-time migration: tele_tinder.db -> MongoDB.

Usage:
  pip install -r requirements.txt
  cp .env.example .env and set MONGODB_URI/MONGODB_DB
  python migrate_sqlite_to_mongo.py tele_tinder.db

The script is idempotent: user/payment/swipe records use stable keys where
possible and are upserted rather than blindly duplicated.
"""
import os, sys, sqlite3
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
load_dotenv()

uri=os.getenv("MONGODB_URI", "").strip(); dbname=os.getenv("MONGODB_DB", "tele_tinder")
if not uri: raise SystemExit("MONGODB_URI set karein")
path=sys.argv[1] if len(sys.argv)>1 else os.getenv("DB_PATH", "tele_tinder.db")
con=sqlite3.connect(path); con.row_factory=sqlite3.Row
mc=MongoClient(uri); db=mc[dbname]

users=list(con.execute("SELECT * FROM users"))
for r in users:
    d=dict(r); d.setdefault("likes_received", 0); d.setdefault("likes_given", 0); d.setdefault("rating_avg", 0.0); d.setdefault("rating_count", 0)
    d.setdefault("contacts", {"telegram_username": d.get("username"), "phone": None, "instagram": None, "facebook": None, "other_social": None, "show_telegram": 1, "show_phone": 0, "show_social": 0})
    if d.get("lat") is not None and d.get("lon") is not None: d["location"]={"type":"Point","coordinates":[d["lon"],d["lat"]]}
    db.users.update_one({"id": d["id"]},{"$set":d},upsert=True)

for r in con.execute("SELECT * FROM swipes"):
    d=dict(r); d.pop("id",None); db.swipes.update_one({"from_id":d["from_id"],"to_id":d["to_id"]},{"$set":d},upsert=True)
for r in con.execute("SELECT * FROM reports"):
    db.reports.update_one(dict(r),{"$setOnInsert":dict(r)},upsert=True)
for r in con.execute("SELECT * FROM payments"):
    d=dict(r); d.pop("id",None); db.payments.update_one({"charge_id":d.get("charge_id")},{"$set":d},upsert=True)
for r in con.execute("SELECT * FROM broadcasts"):
    d=dict(r); d.pop("id",None); db.broadcasts.update_one({"admin_id":d.get("admin_id"),"ts":d.get("ts")},{"$set":d},upsert=True)

# Recalculate engagement counters from swipes.
for u in db.users.find({}, {"id":1}):
    uid=u["id"]
    given=db.swipes.count_documents({"from_id":uid,"type":{"$in":["like","super"]}})
    recv=db.swipes.count_documents({"to_id":uid,"type":{"$in":["like","super"]}})
    db.users.update_one({"id":uid},{"$set":{"likes_given":given,"likes_received":recv}})
print(f"Migrated {len(users)} users to {dbname}")
