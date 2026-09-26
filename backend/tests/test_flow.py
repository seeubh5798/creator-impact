"""End to end in demo mode: login -> sync -> tag sponsored -> worker -> report -> share link."""

import base64
import hashlib
import hmac
import json

from sqlalchemy import select

from app import worker
from app.config import get_settings
from app.db import SessionLocal
from app.models import AnalysisRun, CommentLabel, Job, Post, User


def _sync(client):
    worker.drain()
    return client.get("/posts").json()["posts"]


def test_demo_end_to_end(demo_client):
    c = demo_client
    me = c.get("/auth/me").json()
    assert me["account"]["username"] == "demo.creator"
    assert me["usage"]["monthly_limit"] is None  # demo has the founding plan

    posts = _sync(c)
    assert len(posts) == 24
    sponsored_like = next(p for p in posts if "#ad" in p["caption"])

    r = c.post(f"/posts/{sponsored_like['id']}/sponsor", json={"brand_name": "GlowLab"})
    assert r.status_code == 200, r.text
    report_id, slug = r.json()["report_id"], r.json()["slug"]
    assert c.get(f"/reports/{report_id}").json()["status"] == "processing"
    assert c.get(f"/public/reports/{slug}").status_code == 404  # not ready yet

    worker.drain()
    rep = c.get(f"/reports/{report_id}").json()
    assert rep["status"] == "ready", rep
    d = rep["data"]
    assert 0 <= rep["score"] <= 100
    assert d["brand_name"] == "GlowLab"
    assert d["comments"]["total"] > 300
    assert d["comments"]["spam_removed"] > 0
    assert d["buying_intent"]["count"] > 0 and 0.05 < d["buying_intent"]["rate"] < 0.3
    assert d["metrics"]["saves"]["ratio"] > 1.2  # demo sponsored posts get more saves
    assert d["baseline"]["sample_size"] == 20
    assert d["top_questions"] and d["objections"] and d["quotes"]
    assert d["percentile"] is not None

    # Public view hides internals and counts views
    pub = c.get(f"/public/reports/{slug}").json()
    assert "id" not in pub and "score_parts" not in pub["data"]
    assert c.get(f"/reports/{report_id}").json()["view_count"] == 1

    # Re-analysis only classifies new comments (labels cached)
    with SessionLocal() as db:
        n_labels = len(db.scalars(select(CommentLabel)).all())
    assert c.post(f"/reports/{report_id}/refresh").json()["queued"] is True
    assert c.post(f"/reports/{report_id}/refresh").json()["queued"] is False  # deduped while queued
    worker.drain()
    with SessionLocal() as db:
        assert len(db.scalars(select(CommentLabel)).all()) == n_labels
        runs = db.scalars(select(AnalysisRun)).all()
        assert [r.status for r in runs] == ["done", "done"]

    # Hide from public
    c.patch(f"/reports/{report_id}", json={"is_public": False})
    assert c.get(f"/public/reports/{slug}").status_code == 404

    # Reports list
    assert c.get("/reports").json()["reports"][0]["brand_name"] == "GlowLab"

    # Untag deletes the report
    assert c.delete(f"/posts/{sponsored_like['id']}/sponsor").status_code == 200
    assert c.get(f"/reports/{report_id}").status_code == 404


def test_scheduling_creates_rerun_jobs(demo_client):
    posts = _sync(demo_client)
    recent = posts[0]  # posted ~2 days ago -> 72h and 7d re-runs are in the future
    demo_client.post(f"/posts/{recent['id']}/sponsor", json={})
    with SessionLocal() as db:
        kinds = sorted(j.payload["run_kind"] for j in db.scalars(select(Job).where(Job.kind == "analyze_post")))
    assert kinds == ["72h", "7d", "initial"]


def test_free_plan_quota(demo_client):
    posts = _sync(demo_client)
    with SessionLocal() as db:
        user = db.scalars(select(User)).one()
        user.plan = "free"
        db.commit()
    for p in posts[:3]:
        assert demo_client.post(f"/posts/{p['id']}/sponsor", json={}).status_code == 200
    r = demo_client.post(f"/posts/{posts[3]['id']}/sponsor", json={})
    assert r.status_code == 402
    # Re-tagging an already tagged post doesn't count again
    assert demo_client.post(f"/posts/{posts[0]['id']}/sponsor", json={"brand_name": "X"}).status_code == 200


def test_auth_required(client):
    assert client.get("/posts").status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_other_users_cannot_see_reports(demo_client, client):
    posts = _sync(demo_client)
    report_id = demo_client.post(f"/posts/{posts[1]['id']}/sponsor", json={}).json()["report_id"]
    demo_client.cookies.clear()
    assert demo_client.get(f"/reports/{report_id}").status_code == 401


def _signed_request(payload: dict, secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=") + "." + body


def test_meta_data_deletion(demo_client, monkeypatch):
    _sync(demo_client)
    monkeypatch.setattr(get_settings(), "instagram_app_secret", "shh")
    bad = demo_client.post("/meta/data-deletion", data={"signed_request": _signed_request({"user_id": "demo-0001"}, "nope")})
    assert bad.status_code == 400
    ok = demo_client.post("/meta/data-deletion", data={"signed_request": _signed_request({"user_id": "demo-0001"}, "shh")})
    assert ok.status_code == 200 and "confirmation_code" in ok.json()
    with SessionLocal() as db:
        assert db.scalars(select(User)).first() is None
        assert db.scalars(select(Post)).first() is None


def test_delete_me(demo_client):
    _sync(demo_client)
    assert demo_client.delete("/auth/me").status_code == 200
    with SessionLocal() as db:
        assert db.scalars(select(Post)).first() is None
