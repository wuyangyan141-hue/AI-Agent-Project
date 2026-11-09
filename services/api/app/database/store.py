"""SQLite connection factory; schema migrations and repositories follow later."""
import sqlite3
from pathlib import Path

def connect(path: str = 'data/companion.db') -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA foreign_keys = ON')
    return connection
