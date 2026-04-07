import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Load .env from the app root (cashpilot/.env)
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
dotenv_path = os.path.join(root_dir, ".env")
load_dotenv(dotenv_path)

_WARNED_MISSING_DB_URL = False


def get_db_connection():
    """
    Create and return a Postgres connection.

    Returns None when DATABASE_URL is missing or unreachable so API routers can
    gracefully fall back to demo-mode responses.
    """
    global _WARNED_MISSING_DB_URL

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        if not _WARNED_MISSING_DB_URL:
            print("DATABASE_URL not found. Backend will run in demo mode until .env is configured.")
            _WARNED_MISSING_DB_URL = True
        return None

    try:
        connect_kwargs = {
            "cursor_factory": RealDictCursor,
            "connect_timeout": 10,
        }

        # Supabase/cloud Postgres usually requires SSL, while local postgres often doesn't.
        if not any(host in database_url for host in ("localhost", "127.0.0.1")):
            connect_kwargs["sslmode"] = "require"

        return psycopg2.connect(database_url, **connect_kwargs)
    except Exception as exc:
        print(f"DB connection error (falling back to demo mode): {exc}")
        return None
