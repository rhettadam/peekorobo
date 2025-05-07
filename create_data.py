import os
from dotenv import load_dotenv
from auth import get_pg_connection

load_dotenv()

def setup_database():
    conn = get_pg_connection()
    cursor = conn.cursor()

    try:
        # Drop and re-add followers/following columns with correct type (JSONB)
        cursor.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='followers') THEN
                    ALTER TABLE users DROP COLUMN followers;
                END IF;
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='following') THEN
                    ALTER TABLE users DROP COLUMN following;
                END IF;
            END $$;
        """)

        # Add columns (JSONB)
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user',
            ADD COLUMN IF NOT EXISTS team VARCHAR(20),
            ADD COLUMN IF NOT EXISTS bio TEXT,
            ADD COLUMN IF NOT EXISTS followers JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS following JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS avatar_key TEXT DEFAULT 'stock'
        """)

        # Create saved_items table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_items (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                item_type VARCHAR(10) NOT NULL,
                item_key VARCHAR(50) NOT NULL,
                UNIQUE(user_id, item_type, item_key)
            )
        """)

        # Create epa_history table if it doesn't exist
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
        print("Database updated successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Error updating database: {e}")

    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()
