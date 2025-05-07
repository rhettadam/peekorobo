import os
from dotenv import load_dotenv
from auth import get_pg_connection

load_dotenv()

def setup_database():
    conn = get_pg_connection()
    cursor = conn.cursor()

    try:
        # Create users table
        cursor.execute("DROP TABLE IF EXISTS users CASCADE")

        cursor.execute("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash BYTEA NOT NULL,
                avatar_key VARCHAR(50) DEFAULT 'stock'
            )
        """)



        # Create saved_items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_items (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                item_type VARCHAR(10) NOT NULL,
                item_key VARCHAR(50) NOT NULL,
                UNIQUE(user_id, item_type, item_key)
            )
        """)

        # Create epa_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS epa_history (
                id SERIAL PRIMARY KEY,
                team_key VARCHAR(10) NOT NULL,
                year INTEGER NOT NULL,
                epa FLOAT NOT NULL,
                UNIQUE(team_key, year)
            )
        """)

        conn.commit()
        print("Database schema created successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Error setting up database: {e}")

    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()