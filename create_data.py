import os
from dotenv import load_dotenv
from auth import get_pg_connection

load_dotenv()

def setup_database():
    conn = get_pg_connection()
    cursor = conn.cursor()

    try:
        # Add 'color' column to users table if it doesn't exist
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS color VARCHAR(20)
        """)
        conn.commit()
        print("Color column added successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Error updating database: {e}")

    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()
