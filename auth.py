import os
import hashlib
import psycopg2
from dotenv import load_dotenv
from datagather import DatabaseConnection

load_dotenv()


def register_user(username, password, email=None):
    username = username.lower()
    email = email.lower().strip() if email else None

    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
        return False, "Password must be at least 8 characters and include upper, lower, and digits."

    # Basic email validation if provided
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        return False, "Invalid email format."

    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE LOWER(username) = %s", (username,))
            if cur.fetchone():
                return False, "Username already exists."
            
            # Check if email is already in use (if provided)
            if email:
                cur.execute("SELECT 1 FROM users WHERE LOWER(email) = %s", (email,))
                if cur.fetchone():
                    return False, "Email already in use."

            salt = os.urandom(32)
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
            hashed = salt + key
            cur.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING id",
                (username, psycopg2.Binary(hashed), email),
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            return True, user_id

    except Exception as e:
        print("Register error:", e)
        return False, "Registration failed"


def verify_user(username_or_email, password):
    username_or_email = username_or_email.lower()

    try:
        with DatabaseConnection() as conn:
            cur = conn.cursor()
            # Check both username and email
            cur.execute("SELECT id, password_hash FROM users WHERE LOWER(username) = %s OR LOWER(email) = %s", 
                       (username_or_email, username_or_email))
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

def hash_password(password):
    """Hash a password using the same method as registration"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    hashed = salt + key
    return psycopg2.Binary(hashed)

