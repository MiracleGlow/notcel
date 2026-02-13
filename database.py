import sqlite3
import os
from flask import g

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nocel.db')


def get_db():
    """Get database connection for current request (stored in Flask's g object)."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialize database: create tables if not exist, register teardown."""
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('public', 'private')),
                private_code TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, type)
            );

            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                content     TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS files (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                filename     TEXT NOT NULL,
                filepath     TEXT,
                mimetype     TEXT,
                kind         TEXT,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, filename)
            );
        ''')
        db.commit()
        db.close()

    app.teardown_appcontext(close_db)


# --- Cleanup ---

def delete_expired_sessions(hours=24):
    """Delete sessions older than `hours` hours. Returns list of deleted session IDs."""
    db = get_db()
    expired = db.execute(
        "SELECT id FROM sessions WHERE created_at <= datetime('now', ?)",
        (f'-{hours} hours',)
    ).fetchall()
    expired_ids = [row['id'] for row in expired]
    if expired_ids:
        placeholders = ','.join('?' * len(expired_ids))
        db.execute(f"DELETE FROM notes WHERE session_id IN ({placeholders})", expired_ids)
        db.execute(f"DELETE FROM files WHERE session_id IN ({placeholders})", expired_ids)
        db.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", expired_ids)
        db.commit()
    return expired_ids


# --- Session Helpers ---

def create_session(name, session_type, private_code=None):
    """Create a new session. Returns the session row or None if name already exists."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO sessions (name, type, private_code) VALUES (?, ?, ?)",
            (name, session_type, private_code)
        )
        db.commit()
        return db.execute(
            "SELECT * FROM sessions WHERE name = ? AND type = ?",
            (name, session_type)
        ).fetchone()
    except sqlite3.IntegrityError:
        return None


def get_session(name, session_type):
    """Get a session by name and type."""
    db = get_db()
    return db.execute(
        "SELECT * FROM sessions WHERE name = ? AND type = ?",
        (name, session_type)
    ).fetchone()


def get_public_sessions(search_query=None):
    """Get all public session names, optionally filtered by search query."""
    import re
    db = get_db()
    rows = db.execute(
        "SELECT name FROM sessions WHERE type = 'public' ORDER BY name"
    ).fetchall()

    if not search_query:
        return [row['name'] for row in rows]

    clean_query = re.sub(r'[\W_]+', '', search_query).lower()

    results = []
    for row in rows:
        clean_name = re.sub(r'[\W_]+', '', row['name']).lower()
        if clean_query in clean_name:
            results.append(row['name'])
    return results


# --- Note Helpers ---

def add_note(session_id, content):
    """Add a note to a session."""
    db = get_db()
    db.execute(
        "INSERT INTO notes (session_id, content) VALUES (?, ?)",
        (session_id, content)
    )
    db.commit()


def get_session_notes(session_id):
    """Get all notes for a session, ordered by creation time (oldest first)."""
    db = get_db()
    return db.execute(
        "SELECT * FROM notes WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    ).fetchall()


def get_note(note_id):
    """Get a single note by ID."""
    db = get_db()
    return db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()


def update_note(note_id, content):
    """Update a note's content."""
    db = get_db()
    db.execute("UPDATE notes SET content = ? WHERE id = ?", (content, note_id))
    db.commit()


def delete_note(note_id):
    """Delete a note by ID."""
    db = get_db()
    db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    db.commit()


# --- File Helpers ---

def get_session_files(session_id):
    """Get all files for a session, ordered by creation time (oldest first)."""
    db = get_db()
    return db.execute(
        "SELECT * FROM files WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    ).fetchall()


def save_file(session_id, filename, filepath=None, mimetype=None, kind=None):
    """Save a file record to a session."""
    db = get_db()
    db.execute(
        """INSERT INTO files (session_id, filename, filepath, mimetype, kind)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(session_id, filename) DO UPDATE SET
               filepath = excluded.filepath,
               mimetype = excluded.mimetype,
               kind = excluded.kind""",
        (session_id, filename, filepath, mimetype, kind)
    )
    db.commit()


def get_file(session_id, filename):
    """Get a single file by session_id and filename."""
    db = get_db()
    return db.execute(
        "SELECT * FROM files WHERE session_id = ? AND filename = ?",
        (session_id, filename)
    ).fetchone()


def get_file_by_id(file_id):
    """Get a single file by ID."""
    db = get_db()
    return db.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()


def delete_file_record(file_id):
    """Delete a file record by ID."""
    db = get_db()
    db.execute("DELETE FROM files WHERE id = ?", (file_id,))
    db.commit()
