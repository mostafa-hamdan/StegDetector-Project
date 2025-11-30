# auth_db.py
import sqlite3
import bcrypt
import re
from pathlib import Path
from typing import Optional, Tuple

DB_PATH = Path(__file__).resolve().parent / "users.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create users table if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()


def is_strong_password(password: str) -> Tuple[bool, str]:
    """
    Basic strong password check:
    - At least 8 chars
    - At least one lowercase
    - At least one uppercase
    - At least one digit
    - At least one special char
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[^\w\s]", password):
        return False, "Password must contain at least one special character (e.g. !@#$%)."
    return True, ""


def create_user(username: str, password: str) -> Tuple[bool, str]:
    """
    Create a new user with a bcrypt-hashed password.
    Returns (success, message).
    """
    strong, msg = is_strong_password(password)
    if not strong:
        return False, msg

    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hashed),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists."
    conn.close()
    return True, "Account created successfully."


def verify_user(username: str, password: str) -> bool:
    """Return True if username/password combination is valid."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return False

    stored_hash = row["password_hash"]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode("utf-8")

    return bcrypt.checkpw(password.encode("utf-8"), stored_hash)
