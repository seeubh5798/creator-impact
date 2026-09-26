"""Apply supabase/migrations/*.sql to DATABASE_URL in order, once each.

Usage (from backend/):  python -m scripts.migrate
Alternative: `supabase db push` with the Supabase CLI, which reads the same folder.
"""

import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def main(database_url: str | None = None) -> None:
    url = (database_url or get_settings().database_url).replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("create table if not exists schema_migrations (name text primary key, applied_at timestamptz default now())")
        done = {r[0] for r in conn.execute("select name from schema_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            print(f"applying {path.name}")
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
    print("migrations up to date")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
