import os
import psycopg2


def get_connection():

    return psycopg2.connect(
        host=os.getenv(
            "PGHOST",
            "localhost"
        ),
        port=int(
            os.getenv(
                "PGPORT",
                "5432"
            )
        ),
        dbname=os.getenv(
            "PGDATABASE",
            "ai_pollution"
        ),
        user=os.getenv(
            "PGUSER",
            "postgres"
        ),
        password=os.getenv(
            "PGPASSWORD",
            "postgres"
        ),
    )


def execute_sql(sql, params=None):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                sql,
                params
            )

        conn.commit()


def fetch_all(sql, params=None):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                sql,
                params
            )

            return cur.fetchall()
