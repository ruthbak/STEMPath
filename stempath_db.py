import json
import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).parent
DB_PATH = Path(os.environ.get("STEMPATH_DB_PATH", BASE_DIR / "stempath.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firebase_uid TEXT NOT NULL UNIQUE,
                display_name TEXT,
                email TEXT UNIQUE,
                username TEXT,
                user_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT 'My Profile',
                degree TEXT,
                major TEXT,
                location TEXT,
                gpa TEXT,
                skills_json TEXT NOT NULL DEFAULT '[]',
                certifications_json TEXT NOT NULL DEFAULT '[]',
                courses_json TEXT NOT NULL DEFAULT '[]',
                optimize_for TEXT NOT NULL DEFAULT 'balanced',
                resume_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_id INTEGER,
                role_id TEXT,
                skills_json TEXT NOT NULL DEFAULT '[]',
                completed_json TEXT NOT NULL DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                UNIQUE(user_id, profile_id, role_id)
            );
            """
        )


def _json_list(value):
    if isinstance(value, list):
        return json.dumps(value)
    return json.dumps([])


def _load_list(value):
    if not value:
        return []
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    except json.JSONDecodeError:
        return []


def upsert_user(firebase_uid, display_name=None, email=None, username=None, user_type=None):
    if not firebase_uid:
        return None

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO users (firebase_uid, display_name, email, username, user_type)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(firebase_uid) DO UPDATE SET
                display_name = COALESCE(excluded.display_name, users.display_name),
                email = COALESCE(excluded.email, users.email),
                username = COALESCE(excluded.username, users.username),
                user_type = COALESCE(excluded.user_type, users.user_type),
                updated_at = CURRENT_TIMESTAMP
            """,
            (firebase_uid, display_name, email, username, user_type),
        )
        return get_user(firebase_uid, conn=conn)


def get_user(firebase_uid, conn=None):
    if not firebase_uid:
        return None
    owns_conn = conn is None
    conn = conn or get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE firebase_uid = ?",
            (firebase_uid,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        if owns_conn:
            conn.close()


def get_user_profiles(firebase_uid):
    with get_db() as conn:
        user = get_user(firebase_uid, conn=conn)
        if not user:
            return []
        rows = conn.execute(
            """
            SELECT * FROM profiles
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user["id"],),
        ).fetchall()
        return [_profile_from_row(row) for row in rows]


def get_latest_profile(firebase_uid):
    profiles = get_user_profiles(firebase_uid)
    return profiles[0] if profiles else {}


def get_profile(firebase_uid, profile_id):
    with get_db() as conn:
        user = get_user(firebase_uid, conn=conn)
        if not user:
            return {}
        row = conn.execute(
            """
            SELECT * FROM profiles
            WHERE id = ? AND user_id = ?
            """,
            (profile_id, user["id"]),
        ).fetchone()
        return _profile_from_row(row)


def delete_profile(firebase_uid, profile_id):
    with get_db() as conn:
        user = get_user(firebase_uid, conn=conn)
        if not user:
            return False

        cur = conn.execute(
            "DELETE FROM profiles WHERE id = ? AND user_id = ?",
            (profile_id, user["id"]),
        )
        return cur.rowcount > 0


def save_profile(firebase_uid, profile_data, profile_id=None, resume_path=None, create_new=False):
    with get_db() as conn:
        user = get_user(firebase_uid, conn=conn)
        if not user:
            return None

        existing = None
        if profile_id and not create_new:
            existing = conn.execute(
                "SELECT * FROM profiles WHERE id = ? AND user_id = ?",
                (profile_id, user["id"]),
            ).fetchone()

        if not existing and not create_new:
            existing = conn.execute(
                """
                SELECT * FROM profiles
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (user["id"],),
            ).fetchone()

        values = (
            profile_data.get("degree", ""),
            profile_data.get("major", ""),
            profile_data.get("location", ""),
            profile_data.get("gpa", ""),
            _json_list(profile_data.get("skills", [])),
            _json_list(profile_data.get("certifications", [])),
            _json_list(profile_data.get("courses", [])),
            profile_data.get("optimize_for", "balanced"),
            resume_path,
        )

        if existing:
            conn.execute(
                """
                UPDATE profiles
                SET degree = ?, major = ?, location = ?, gpa = ?,
                    skills_json = ?, certifications_json = ?, courses_json = ?,
                    optimize_for = ?,
                    resume_path = COALESCE(?, resume_path),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                values + (existing["id"], user["id"]),
            )
            saved_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO profiles (
                    user_id, degree, major, location, gpa, skills_json,
                    certifications_json, courses_json, optimize_for, resume_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user["id"],) + values,
            )
            saved_id = cur.lastrowid

        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?",
            (saved_id,),
        ).fetchone()
        return _profile_from_row(row)


def get_progress(firebase_uid, profile_id=None, role_id=None):
    with get_db() as conn:
        user = get_user(firebase_uid, conn=conn)
        if not user:
            return {"skills": [], "completed": []}

        query = "SELECT * FROM progress WHERE user_id = ?"
        params = [user["id"]]
        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)
        if role_id:
            query += " AND role_id = ?"
            params.append(role_id)
        query += " ORDER BY updated_at DESC, id DESC LIMIT 1"

        row = conn.execute(query, params).fetchone()
        return _progress_from_row(row) if row else {"skills": [], "completed": []}


def save_progress(firebase_uid, progress_data, profile_id=None):
    with get_db() as conn:
        user = get_user(firebase_uid, conn=conn)
        if not user:
            return {"skills": [], "completed": []}

        role_id = progress_data.get("role_id")
        skills = _json_list(progress_data.get("skills", []))
        completed = _json_list(progress_data.get("completed", []))

        conn.execute(
            """
            INSERT INTO progress (user_id, profile_id, role_id, skills_json, completed_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, profile_id, role_id) DO UPDATE SET
                skills_json = excluded.skills_json,
                completed_json = excluded.completed_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user["id"], profile_id, role_id, skills, completed),
        )

        return get_progress(firebase_uid, profile_id=profile_id, role_id=role_id)


def _profile_from_row(row):
    if not row:
        return {}
    return {
        "id": row["id"],
        "name": row["name"],
        "degree": row["degree"] or "",
        "major": row["major"] or "",
        "location": row["location"] or "",
        "gpa": row["gpa"] or "",
        "skills": _load_list(row["skills_json"]),
        "certifications": _load_list(row["certifications_json"]),
        "courses": _load_list(row["courses_json"]),
        "optimize_for": row["optimize_for"] or "balanced",
        "resume_path": row["resume_path"],
    }


def _progress_from_row(row):
    if not row:
        return {"skills": [], "completed": []}
    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "role_id": row["role_id"],
        "skills": _load_list(row["skills_json"]),
        "completed": _load_list(row["completed_json"]),
    }
