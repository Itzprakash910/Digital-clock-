"""Database selector with safe local fallback.

MongoDB is used when DATABASE_BACKEND=mongo *and* MONGODB_URI is configured.
Otherwise SQLite is used automatically for local development/testing.
"""
import os

_backend = os.getenv("DATABASE_BACKEND", "mongo").strip().lower()
_mongo_uri = os.getenv("MONGODB_URI", "").strip()

if _backend == "mongo" and _mongo_uri:
    from db_mongo import *  # noqa: F401,F403
else:
    from db_sqlite import *  # noqa: F401,F403
