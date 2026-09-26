"""Tiny Postgres-backed job queue.

enqueue() inserts a row; claim() atomically moves one due row from 'queued' to
'running' with an optimistic UPDATE, so several workers can run safely without
Redis. Failed jobs retry with exponential backoff up to max_attempts.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Job, utcnow

log = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=15)


def enqueue(
    db: Session,
    kind: str,
    payload: dict | None = None,
    run_at: datetime | None = None,
    dedupe_key: str | None = None,
    max_attempts: int = 5,
) -> Job | None:
    """Adds a job. With dedupe_key, a second enqueue of the same key is a no-op
    while the first is still queued/running (returns None)."""
    if dedupe_key:
        existing = db.scalar(select(Job).where(Job.dedupe_key == dedupe_key))
        if existing:
            if existing.status in ("queued", "running"):
                return None
            # Finished jobs release their key so the work can be scheduled again.
            existing.dedupe_key = None
            db.flush()
    job = Job(kind=kind, payload=payload or {}, run_at=run_at or utcnow(), dedupe_key=dedupe_key, max_attempts=max_attempts)
    try:
        with db.begin_nested():  # savepoint: a dedupe race must not roll back the caller's work
            db.add(job)
    except IntegrityError:
        return None
    return job


def claim(db: Session) -> Job | None:
    now = utcnow()
    # Recover jobs whose worker died mid-run.
    db.execute(
        update(Job)
        .where(Job.status == "running", Job.locked_at < now - STALE_AFTER)
        .values(status="queued", locked_at=None)
    )
    for _ in range(5):
        candidate = db.scalar(
            select(Job.id).where(Job.status == "queued", Job.run_at <= now).order_by(Job.run_at).limit(1)
        )
        if candidate is None:
            db.commit()
            return None
        result = db.execute(
            update(Job)
            .where(Job.id == candidate, Job.status == "queued")
            .values(status="running", locked_at=now, attempts=Job.attempts + 1)
        )
        db.commit()
        if result.rowcount == 1:
            return db.get(Job, candidate)
    return None


def complete(db: Session, job: Job) -> None:
    job.status = "done"
    job.locked_at = None
    job.last_error = None
    db.commit()


def fail(db: Session, job: Job, error: str, retry: bool = True) -> None:
    job.last_error = error[:2000]
    job.locked_at = None
    if retry and job.attempts < job.max_attempts:
        job.status = "queued"
        job.run_at = datetime.now(timezone.utc) + timedelta(seconds=30 * 2 ** (job.attempts - 1))
    else:
        job.status = "failed"
    db.commit()
