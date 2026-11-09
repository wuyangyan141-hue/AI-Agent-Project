"""Small SQLite repository for local conversations, tasks and preferences."""
import os
import sqlite3
import json
from pathlib import Path


def connect(path: str | None = None) -> sqlite3.Connection:
    database = path or os.getenv('DATABASE_PATH', 'data/companion.db')
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS replan_drafts (
            id INTEGER PRIMARY KEY, payload TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0
        );
    ''')
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(tasks)')}
    if 'scheduled_day' not in columns:
        connection.execute('ALTER TABLE tasks ADD COLUMN scheduled_day INTEGER')
    if 'estimated_minutes' not in columns:
        connection.execute('ALTER TABLE tasks ADD COLUMN estimated_minutes INTEGER NOT NULL DEFAULT 30')
    return connection


def add_message(db: sqlite3.Connection, role: str, content: str) -> None:
    db.execute('INSERT INTO messages(role, content) VALUES (?, ?)', (role, content))
    db.commit()


def recent_messages(db: sqlite3.Connection, limit: int = 12) -> list[dict[str, str]]:
    rows = db.execute('SELECT role, content FROM messages ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(row) for row in reversed(rows)]


def list_tasks(db: sqlite3.Connection) -> list[dict]:
    return [dict(row) | {'done': bool(row['done'])} for row in db.execute('SELECT id, title, done, scheduled_day, estimated_minutes FROM tasks ORDER BY id DESC')]


def add_task(db: sqlite3.Connection, title: str) -> dict:
    cursor = db.execute('INSERT INTO tasks(title) VALUES (?)', (title,))
    db.commit()
    return {'id': cursor.lastrowid, 'title': title, 'done': False}


def set_task_done(db: sqlite3.Connection, task_id: int, done: bool) -> bool:
    cursor = db.execute('UPDATE tasks SET done = ? WHERE id = ?', (int(done), task_id))
    db.commit()
    return cursor.rowcount > 0


def set_preference(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute('INSERT INTO preferences(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
    db.commit()


def get_preference(db: sqlite3.Connection, key: str, default: str = '') -> str:
    row = db.execute('SELECT value FROM preferences WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def save_replan_draft(db: sqlite3.Connection, payload: dict) -> dict:
    cursor = db.execute('INSERT INTO replan_drafts(payload) VALUES (?)', (json.dumps(payload, ensure_ascii=False),))
    db.commit()
    return {'id': cursor.lastrowid, **payload}


def apply_replan_draft(db: sqlite3.Connection, draft_id: int) -> dict | None:
    db.execute('BEGIN IMMEDIATE')
    row = db.execute('SELECT payload, applied FROM replan_drafts WHERE id = ?', (draft_id,)).fetchone()
    if row is None or row['applied']:
        db.rollback()
        return None
    payload = json.loads(row['payload'])
    for item in payload['schedule']:
        updated = db.execute('UPDATE tasks SET scheduled_day = ?, estimated_minutes = ? WHERE id = ? AND done = 0', (item['day'], item['minutes'], item['task_id']))
        if updated.rowcount != 1:
            db.rollback()
            return None
    db.execute('UPDATE replan_drafts SET applied = 1 WHERE id = ?', (draft_id,))
    db.commit()
    return {'id': draft_id, 'applied': True, **payload}
