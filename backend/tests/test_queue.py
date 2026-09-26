from datetime import timedelta

from app import queue
from app.db import SessionLocal
from app.models import Job, utcnow


def test_enqueue_dedupe_and_claim_order():
    with SessionLocal() as db:
        a = queue.enqueue(db, "x", {"n": 1}, dedupe_key="k1")
        assert queue.enqueue(db, "x", {"n": 2}, dedupe_key="k1") is None
        queue.enqueue(db, "x", {"n": 3}, run_at=utcnow() + timedelta(hours=1))
        db.commit()
        job = queue.claim(db)
        assert job.id == a.id and job.status == "running" and job.attempts == 1
        assert queue.claim(db) is None  # the other job is not due yet
        queue.complete(db, job)
        # key is released once the job is done
        assert queue.enqueue(db, "x", {"n": 4}, dedupe_key="k1") is not None
        db.commit()


def test_fail_retries_with_backoff_then_gives_up():
    with SessionLocal() as db:
        queue.enqueue(db, "x", max_attempts=2)
        db.commit()
        job = queue.claim(db)
        queue.fail(db, job, "boom")
        assert job.status == "queued" and job.run_at > utcnow()
        job.run_at = utcnow()
        db.commit()
        job = queue.claim(db)
        queue.fail(db, job, "boom again")
        assert job.status == "failed" and job.last_error == "boom again"


def test_stale_running_jobs_are_recovered():
    with SessionLocal() as db:
        job = queue.enqueue(db, "x")
        db.commit()
        claimed = queue.claim(db)
        claimed.locked_at = utcnow() - timedelta(hours=1)
        db.commit()
        again = queue.claim(db)
        assert again is not None and again.id == job.id and again.attempts == 2
        assert db.get(Job, job.id).status == "running"
