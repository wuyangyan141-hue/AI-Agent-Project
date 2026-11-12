from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid4().hex


class Database:
    def __init__(self, data_dir: Path, database_path: Path | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads = self.data_dir / "uploads"
        self.uploads.mkdir(exist_ok=True)
        self.path = database_path or self.data_dir / "knowledge.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, filename TEXT NOT NULL,
                    suffix TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
                    status TEXT NOT NULL, chunk_count INTEGER NOT NULL DEFAULT 0,
                    embedding_id TEXT, error TEXT, created_at TEXT NOT NULL,
                    UNIQUE(user_id, sha256)
                );
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL, page INTEGER, section TEXT,
                    content TEXT NOT NULL, vector BLOB NOT NULL,
                    UNIQUE(document_id, position)
                );
                CREATE INDEX IF NOT EXISTS chunks_document ON knowledge_chunks(document_id);
                CREATE INDEX IF NOT EXISTS documents_user ON knowledge_documents(user_id);
                CREATE TABLE IF NOT EXISTS knowledge_sessions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user ON knowledge_sessions(user_id);
                CREATE TABLE IF NOT EXISTS knowledge_messages (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES knowledge_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_preferences (
                    user_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                    updated_at TEXT NOT NULL, PRIMARY KEY(user_id, key)
                );
                CREATE TABLE IF NOT EXISTS knowledge_memories (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, key TEXT NOT NULL,
                    content TEXT NOT NULL, tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(user_id, key)
                );
                CREATE TABLE IF NOT EXISTS knowledge_document_meta (
                    document_id TEXT PRIMARY KEY REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    keywords_json TEXT NOT NULL, outline_json TEXT NOT NULL,
                    summary TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_bookmarks (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    chunk_id TEXT, note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS bookmarks_user ON knowledge_bookmarks(user_id);
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def all(self, sql, params=()):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params)]

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        with self.connect() as conn:
            conn.execute(sql, params)

    def document_path(self, document):
        return self.uploads / (document["id"] + document["suffix"])

    def messages(self, user_id, session_id):
        return [dict(row, metadata=json.loads(row["metadata_json"])) for row in self.all(
            "SELECT m.* FROM knowledge_messages m JOIN knowledge_sessions s ON s.id=m.session_id "
            "WHERE s.user_id=? AND s.id=? ORDER BY m.created_at,m.rowid", (user_id, session_id)
        )]
