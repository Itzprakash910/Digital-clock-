"""Database selector.

Set DATABASE_BACKEND=mongo to use MongoDB Atlas. Otherwise the legacy SQLite
backend remains available for local development/backward compatibility.
"""
import os

if os.getenv("DATABASE_BACKEND", "mongo").strip().lower() == "mongo":
    from db_mongo import *  # noqa: F401,F403
else:
    from db_sqlite import *  # noqa: F401,F403
