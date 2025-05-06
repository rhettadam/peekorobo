import bcrypt
import sqlite3

DB = "user_data.sqlite"

def is_secure_password(pw):
    if len(pw) < 6:
        return False, "Password must be at least 6 characters."
    if pw.isalpha() or pw.isdigit():
        return False, "Password must include both letters and numbers."
    return True, "OK"

def register_user(username, password):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    # Check for existing user
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, "Username already taken."

    # Validate password strength
    ok, msg = is_secure_password(password)
    if not ok:
        conn.close()
        return False, msg

    # Hash and store
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
    conn.commit()
    conn.close()
    return True, "Registration successful!"


def verify_user(username, password):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    if result:
        user_id, stored_hash = result
        if bcrypt.checkpw(password.encode(), stored_hash):
            return True, user_id
    return False, None
