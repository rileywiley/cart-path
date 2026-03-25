"""
CartPath — Database Layer
===========================
SQLite database for user accounts, saved routes, and auth tokens.
Uses aiosqlite for async FastAPI compatibility.
"""

import os

import aiosqlite

DB_PATH = os.environ.get("CARTPATH_DB_PATH", "pipeline/data/cartpath.db")

_db: aiosqlite.Connection | None = None


async def init_db():
    """Initialize the database connection and create tables."""
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            vehicle_type TEXT NOT NULL DEFAULT 'golf_cart',
            tier TEXT NOT NULL DEFAULT 'free',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS saved_routes (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            route_id TEXT,
            summary TEXT,
            distance_miles REAL,
            duration_minutes REAL,
            start_lat REAL NOT NULL,
            start_lon REAL NOT NULL,
            end_lat REAL NOT NULL,
            end_lon REAL NOT NULL,
            saved_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_saved_routes_user ON saved_routes(user_id);

        CREATE TABLE IF NOT EXISTS verification_codes (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_verification_codes_email ON verification_codes(email);

        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
    """)
    await _db.commit()


async def get_db() -> aiosqlite.Connection:
    """Get the database connection. Must call init_db() first."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db():
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None
