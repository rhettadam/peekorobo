import os
import hashlib
import psycopg2
from dotenv import load_dotenv
from datagather import DatabaseConnection

load_dotenv()


def register_user(username, password):
    username = username.lower()

    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
        return False, "Password must be at least 8 characters and include upper, lower, and digits."

    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE LOWER(username) = %s", (username,))
            if cur.fetchone():
                return False, "Username already exists."

            salt = os.urandom(32)
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
            hashed = salt + key
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
                (username, psycopg2.Binary(hashed)),
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            return True, user_id

    except Exception as e:
        print("Register error:", e)
        return False, "Registration failed"


def verify_user(username, password):
    username = username.lower()

    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, password_hash FROM users WHERE LOWER(username) = %s", (username,))
            row = cur.fetchone()
            if not row:
                return False, None

            user_id, stored_hash = row
            stored_hash = stored_hash.tobytes() if isinstance(stored_hash, memoryview) else stored_hash

            salt = stored_hash[:32]
            key = stored_hash[32:]
            new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)

            return (new_key == key), user_id if new_key == key else None

    except Exception as e:
        print("Verify error:", e)
        return False, None

