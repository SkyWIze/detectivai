"""SQLite-слой (aiosqlite). Одна активная сессия на игрока.

Таблицы: users, cases, sessions, leaderboard.
Состояние дела (case) и прогресс (state) хранятся как JSON-текст.
"""
import json
import time

import aiosqlite

from config import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    created_at   INTEGER,
    games_played INTEGER DEFAULT 0,
    best_score   INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cases (
    case_id    TEXT PRIMARY KEY,
    user_id    INTEGER,
    setting    TEXT,
    data_json  TEXT,
    created_at INTEGER
);
CREATE TABLE IF NOT EXISTS sessions (
    user_id    INTEGER PRIMARY KEY,
    case_id    TEXT,
    status     TEXT,
    moves_left INTEGER,
    state_json TEXT,
    updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS leaderboard (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    case_id    TEXT,
    score      INTEGER,
    rank_name  TEXT,
    created_at INTEGER
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def get_or_create_user(user_id: int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)",
            (user_id, int(time.time())),
        )
        await db.commit()


async def get_user_stats(user_id: int) -> tuple[int, int]:
    """Возвращает (games_played, best_score)."""
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute(
            "SELECT games_played, best_score FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return (row[0], row[1]) if row else (0, 0)


async def save_case(case: dict, user_id: int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cases (case_id, user_id, setting, data_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (case["id"], user_id, case.get("setting", ""), json.dumps(case, ensure_ascii=False), int(time.time())),
        )
        await db.commit()


async def get_case(case_id: str) -> dict | None:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute("SELECT data_json FROM cases WHERE case_id = ?", (case_id,)) as cur:
            row = await cur.fetchone()
    return json.loads(row[0]) if row else None


async def save_session(user_id: int, case_id: str, status: str, moves_left: int, state: dict) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO sessions (user_id, case_id, status, moves_left, state_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, case_id, status, moves_left, json.dumps(state, ensure_ascii=False), int(time.time())),
        )
        await db.commit()


async def get_session(user_id: int) -> dict | None:
    async with aiosqlite.connect(config.db_path) as db:
        async with db.execute(
            "SELECT case_id, status, moves_left, state_json FROM sessions WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {"case_id": row[0], "status": row[1], "moves_left": row[2], "state": json.loads(row[3])}


async def delete_session(user_id: int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await db.commit()


async def add_result(user_id: int, case_id: str, score: int, rank_name: str) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT INTO leaderboard (user_id, case_id, score, rank_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, case_id, score, rank_name, int(time.time())),
        )
        await db.execute(
            "UPDATE users SET games_played = games_played + 1, best_score = MAX(best_score, ?) WHERE user_id = ?",
            (score, user_id),
        )
        await db.commit()
