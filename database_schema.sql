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
