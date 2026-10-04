import json
import sqlite3
from datetime import datetime

DB = "sessions.db"


def _conn():
    return sqlite3.connect(DB)


def init():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                friend TEXT, role TEXT, created TEXT,
                avg_score REAL, data TEXT)"""
        )


def save_session(friend: str, role: str, avg: float, data: dict):
    with _conn() as c:
        c.execute(
            "INSERT INTO sessions (friend, role, created, avg_score, data) VALUES (?,?,?,?,?)",
            (friend, role, datetime.now().strftime("%Y-%m-%d %H:%M"), avg, json.dumps(data)),
        )


def history(friend: str) -> list[tuple[str, float]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT created, avg_score FROM sessions WHERE friend = ? ORDER BY id", (friend,)
        ).fetchall()
    return rows


def past_questions(friend: str) -> list[str]:
    with _conn() as c:
        rows = c.execute("SELECT data FROM sessions WHERE friend = ?", (friend,)).fetchall()
    qs = []
    for (data,) in rows:
        for t in json.loads(data).get("turns", []):
            if not t["followup"]:
                qs.append(t["question"])
    return qs