import sqlite3

conn = sqlite3.connect("user_data.sqlite")
cursor = conn.cursor()

# Create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash BLOB NOT NULL
)
""")

# Create saved_items table
cursor.execute("""
CREATE TABLE IF NOT EXISTS saved_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_type TEXT CHECK(item_type IN ('team', 'event')) NOT NULL,
    item_key TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

conn.commit()
conn.close()

print("✅ user_data.sqlite initialized.")
