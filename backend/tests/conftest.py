"""Tests run against a real Postgres with the Supabase migration applied.

Set TEST_DATABASE_URL (default: local Postgres on port 54329, database impact_test).
"""

import os

os.environ.setdefault("DATABASE_URL", os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:54329/impact_test"))
os.environ["DEMO_MODE"] = "true"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ENV"] = "development"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from scripts import migrate  # noqa: E402

TABLES = "jobs, reports, baselines, comment_labels, analysis_runs, post_metrics, posts, ig_accounts, users"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    url = get_settings().database_url
    plain = url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(plain, autocommit=True) as conn:
        conn.execute("drop schema public cascade; create schema public;")
    migrate.main(url)
    yield


@pytest.fixture(autouse=True)
def _clean():
    plain = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(plain, autocommit=True) as conn:
        conn.execute(f"truncate {TABLES} restart identity cascade")
    yield


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def demo_client(client):
    r = client.post("/auth/demo")
    assert r.status_code == 200
    return client
