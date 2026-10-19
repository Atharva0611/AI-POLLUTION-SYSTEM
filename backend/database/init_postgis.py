import os
from pathlib import Path
import psycopg2

ROOT = Path(
    r"C:\final year project\AI-POLLUTION-SYSTEM"
)

SCHEMA_FILE = (
    ROOT
    / "backend"
    / "database"
    / "schema.sql"
)

DB_NAME = os.getenv(
    "PGDATABASE",
    "ai_pollution"
)

HOST = os.getenv(
    "PGHOST",
    "localhost"
)

PORT = int(
    os.getenv(
        "PGPORT",
        "5432"
    )
)

USER = os.getenv(
    "PGUSER",
    "postgres"
)

PASSWORD = os.getenv(
    "PGPASSWORD",
    "postgres"
)


def main():

    # Connect to the default postgres database
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname="postgres",
        user=USER,
        password=PASSWORD,
    )

    conn.autocommit = True

    with conn.cursor() as cur:

        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,)
        )

        exists = cur.fetchone()

        if not exists:

            cur.execute(
                f'CREATE DATABASE "{DB_NAME}"'
            )

            print(
                f"Created database: {DB_NAME}"
            )

        else:

            print(
                f"Database already exists: {DB_NAME}"
            )

    conn.close()

    # Connect to project DB
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=DB_NAME,
        user=USER,
        password=PASSWORD,
    )

    with conn.cursor() as cur:

        schema = SCHEMA_FILE.read_text(
            encoding="utf-8"
        )

        cur.execute(schema)

    conn.commit()
    conn.close()

    print(
        "PostgreSQL + PostGIS schema initialized successfully."
    )


if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        print(
            f"ERROR: {type(exc).__name__}: {exc}"
        )

        print(
            "\nCheck that PostgreSQL and PostGIS are installed "
            "and that the database credentials are correct."
        )
