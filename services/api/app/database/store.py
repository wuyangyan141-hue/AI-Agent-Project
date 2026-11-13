"""Small SQLite repository for local conversations, tasks and preferences."""
import os
import sqlite3
import json
from datetime import datetime, timezone, timedelta
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
        CREATE TABLE IF NOT EXISTS plan_drafts (
            id INTEGER PRIMARY KEY, payload TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY, task_id INTEGER REFERENCES tasks(id), started_at TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL, completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS review_sessions (
            id INTEGER PRIMARY KEY, topic TEXT NOT NULL, question TEXT NOT NULL,
            answer TEXT, feedback TEXT, status TEXT NOT NULL DEFAULT 'waiting'
        );
    ''')
    review_columns = {row['name'] for row in connection.execute('PRAGMA table_info(review_sessions)')}
    if 'session_id' not in review_columns:
        connection.execute('ALTER TABLE review_sessions ADD COLUMN session_id TEXT')
    if 'snapshot_json' not in review_columns:
        connection.execute("ALTER TABLE review_sessions ADD COLUMN snapshot_json TEXT NOT NULL DEFAULT '{}'")
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(tasks)')}
    if 'scheduled_day' not in columns:
        connection.execute('ALTER TABLE tasks ADD COLUMN scheduled_day INTEGER')
    if 'estimated_minutes' not in columns:
        connection.execute('ALTER TABLE tasks ADD COLUMN estimated_minutes INTEGER NOT NULL DEFAULT 30')
    if 'deleted_at' not in columns:
        connection.execute('ALTER TABLE tasks ADD COLUMN deleted_at TEXT')
    if 'bones_awarded' not in columns:
        connection.execute('ALTER TABLE tasks ADD COLUMN bones_awarded INTEGER NOT NULL DEFAULT 0')
    return connection


def _task_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    return {
        'id': data['id'],
        'title': data['title'],
        'done': bool(data['done']),
        'estimated_minutes': data['estimated_minutes'],
        'scheduled_day': data['scheduled_day'],
        'deleted_at': data.get('deleted_at'),
        'bones_awarded': bool(data.get('bones_awarded')),
    }


def add_message(db: sqlite3.Connection, role: str, content: str) -> None:
    db.execute('INSERT INTO messages(role, content) VALUES (?, ?)', (role, content))
    db.commit()


def recent_messages(db: sqlite3.Connection, limit: int = 12) -> list[dict[str, str]]:
    rows = db.execute('SELECT role, content FROM messages ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(row) for row in reversed(rows)]


def list_tasks(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        'SELECT id, title, done, scheduled_day, estimated_minutes, deleted_at, bones_awarded FROM tasks '
        'WHERE deleted_at IS NULL ORDER BY id DESC'
    )
    return [_task_row(row) for row in rows]


def list_trashed_tasks(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        'SELECT id, title, done, scheduled_day, estimated_minutes, deleted_at, bones_awarded FROM tasks '
        'WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC, id DESC'
    )
    return [_task_row(row) for row in rows]


def add_task(db: sqlite3.Connection, title: str, minutes: int = 30, day: int | None = None) -> dict:
    cursor = db.execute('INSERT INTO tasks(title, estimated_minutes, scheduled_day) VALUES (?, ?, ?)', (title, minutes, day))
    db.commit()
    return {
        'id': cursor.lastrowid, 'title': title, 'done': False, 'estimated_minutes': minutes,
        'scheduled_day': day, 'deleted_at': None, 'bones_awarded': False,
    }


def set_task_done(db: sqlite3.Connection, task_id: int, done: bool) -> bool:
    cursor = db.execute('UPDATE tasks SET done = ? WHERE id = ? AND deleted_at IS NULL', (int(done), task_id))
    db.commit()
    return cursor.rowcount > 0


def soft_delete_task(db: sqlite3.Connection, task_id: int) -> dict | None:
    row = db.execute('SELECT * FROM tasks WHERE id = ? AND deleted_at IS NULL', (task_id,)).fetchone()
    if row is None:
        return None
    stamp = datetime.now(timezone.utc).isoformat()
    db.execute('UPDATE tasks SET deleted_at = ? WHERE id = ?', (stamp, task_id))
    db.commit()
    return _task_row(db.execute(
        'SELECT id, title, done, scheduled_day, estimated_minutes, deleted_at, bones_awarded FROM tasks WHERE id=?',
        (task_id,),
    ).fetchone())


def restore_task(db: sqlite3.Connection, task_id: int) -> dict | None:
    row = db.execute('SELECT * FROM tasks WHERE id = ? AND deleted_at IS NOT NULL', (task_id,)).fetchone()
    if row is None:
        return None
    db.execute('UPDATE tasks SET deleted_at = NULL WHERE id = ?', (task_id,))
    db.commit()
    return _task_row(db.execute(
        'SELECT id, title, done, scheduled_day, estimated_minutes, deleted_at, bones_awarded FROM tasks WHERE id=?',
        (task_id,),
    ).fetchone())


def purge_task(db: sqlite3.Connection, task_id: int) -> bool:
    cursor = db.execute('DELETE FROM tasks WHERE id = ? AND deleted_at IS NOT NULL', (task_id,))
    db.commit()
    return cursor.rowcount > 0


def edit_task(db: sqlite3.Connection, task_id: int, title: str | None, minutes: int | None, done: bool | None) -> dict | None:
    row = db.execute('SELECT * FROM tasks WHERE id = ? AND deleted_at IS NULL', (task_id,)).fetchone()
    if row is None:
        return None
    was_done = bool(row['done'])
    already_awarded = bool(row['bones_awarded'] if 'bones_awarded' in row.keys() else 0)
    next_done = bool(done) if done is not None else was_done
    db.execute('UPDATE tasks SET title=?, estimated_minutes=?, done=? WHERE id=?',
               (title if title is not None else row['title'], minutes if minutes is not None else row['estimated_minutes'],
                int(next_done), task_id))
    db.commit()
    reward = None
    # Each task can earn bones only once, even if later unchecked and re-checked.
    if done is not None and next_done and not already_awarded:
        from ..skills.learning_loop import award_task_completion
        minutes_value = int((minutes if minutes is not None else row['estimated_minutes']) or 30)
        task_title = str(title if title is not None else row['title'] or '')
        reward = award_task_completion(db, minutes_value, title=task_title)
        db.execute('UPDATE tasks SET bones_awarded = 1 WHERE id = ?', (task_id,))
        db.commit()
    updated = _task_row(db.execute(
        'SELECT id, title, done, scheduled_day, estimated_minutes, deleted_at, bones_awarded FROM tasks WHERE id=?',
        (task_id,),
    ).fetchone())
    if updated is None:
        return None
    if reward is not None:
        updated = {**updated, 'reward': reward}
    return updated


def save_plan_draft(db: sqlite3.Connection, payload: dict) -> dict:
    cursor = db.execute('INSERT INTO plan_drafts(payload) VALUES (?)', (json.dumps(payload, ensure_ascii=False),))
    db.commit()
    return {'id': cursor.lastrowid, **payload}


def apply_plan_draft(db: sqlite3.Connection, draft_id: int) -> dict | None:
    db.execute('BEGIN IMMEDIATE')
    row = db.execute('SELECT payload, applied FROM plan_drafts WHERE id=?', (draft_id,)).fetchone()
    if row is None or row['applied']:
        db.rollback()
        return None
    payload = json.loads(row['payload'])
    created = []
    for step in payload['steps']:
        cursor = db.execute('INSERT INTO tasks(title, estimated_minutes, scheduled_day) VALUES (?,?,?)',
                            (step['title'], step['minutes'], step['day']))
        created.append(cursor.lastrowid)
    db.execute('UPDATE plan_drafts SET applied=1 WHERE id=?', (draft_id,))
    db.commit()
    return {'id': draft_id, 'task_ids': created, 'applied': True}


def start_focus(db: sqlite3.Connection, task_id: int | None, minutes: float) -> dict | None:
    duration = float(minutes)
    if duration <= 0 or duration > 240:
        raise ValueError('Invalid focus duration')
    if task_id is not None and db.execute('SELECT 1 FROM tasks WHERE id=?', (task_id,)).fetchone() is None:
        return None
    if db.execute('SELECT 1 FROM focus_sessions WHERE completed_at IS NULL').fetchone():
        raise ValueError('A focus session is already active')
    now = datetime.now(timezone.utc)
    cursor = db.execute('INSERT INTO focus_sessions(task_id, started_at, duration_minutes) VALUES (?,?,?)',
                        (task_id, now.isoformat(), duration))
    db.commit()
    return {'id': cursor.lastrowid, 'task_id': task_id, 'duration_minutes': duration,
            'started_at': now.isoformat(), 'ends_at': (now + timedelta(minutes=duration)).isoformat()}


def focus_status(db: sqlite3.Connection) -> dict | None:
    row = db.execute('SELECT * FROM focus_sessions WHERE completed_at IS NULL ORDER BY id DESC LIMIT 1').fetchone()
    if row is None:
        return None
    duration = float(row['duration_minutes'])
    ends_at = datetime.fromisoformat(row['started_at']) + timedelta(minutes=duration)
    task_id = row['task_id']
    task_title = None
    if task_id is not None:
        task_row = db.execute(
            'SELECT title FROM tasks WHERE id=? AND deleted_at IS NULL',
            (task_id,),
        ).fetchone()
        task_title = task_row['title'] if task_row else None
    return {
        'id': row['id'],
        'task_id': task_id,
        'task_title': task_title,
        'duration_minutes': duration,
        'ends_at': ends_at.isoformat(),
        'remaining_seconds': max(0, int((ends_at - datetime.now(timezone.utc)).total_seconds())),
    }


def finish_focus(db: sqlite3.Connection, session_id: int) -> bool:
    cursor = db.execute('UPDATE focus_sessions SET completed_at=? WHERE id=? AND completed_at IS NULL',
                        (datetime.now(timezone.utc).isoformat(), session_id))
    db.commit()
    return cursor.rowcount == 1


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
        updated = db.execute(
            'UPDATE tasks SET scheduled_day = ?, estimated_minutes = ? WHERE id = ? AND done = 0 AND deleted_at IS NULL',
            (item['day'], item['minutes'], item['task_id']),
        )
        if updated.rowcount != 1:
            db.rollback()
            return None
    db.execute('UPDATE replan_drafts SET applied = 1 WHERE id = ?', (draft_id,))
    db.commit()
    return {'id': draft_id, 'applied': True, **payload}
