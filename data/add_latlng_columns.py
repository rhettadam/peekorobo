from _latlng_env import bootstrap_env

bootstrap_env()

from run import get_pg_connection

DDL = [
    "ALTER TABLE teams ADD COLUMN IF NOT EXISTS lat double precision",
    "ALTER TABLE teams ADD COLUMN IF NOT EXISTS lng double precision",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS lat double precision",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS lng double precision",
]


def main():
    conn = get_pg_connection()
    cur = conn.cursor()
    for stmt in DDL:
        print(f"Running: {stmt}")
        cur.execute(stmt)
    conn.commit()

    cur.execute(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_name IN ('teams', 'events') AND column_name IN ('lat', 'lng')
        ORDER BY table_name, column_name
        """
    )
    print("\nColumns present:")
    for row in cur.fetchall():
        print(f"  {row[0]}.{row[1]} -> {row[2]}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
