"""Background worker. Run with:  python -m app.worker

Processes jobs from the Postgres queue and schedules periodic maintenance
(token refresh, raw comment purge). Safe to run several copies.
"""

import logging
import signal
import time
import uuid
from datetime import timedelta

from sqlalchemy import select, update

from app import queue
from app.config import get_settings
from app.db import SessionLocal
from app.instagram import InstagramError, client_for, is_demo_account
from app.instagram.client import refresh_long_lived_token
from app.models import CommentLabel, IgAccount, Job, Report, utcnow
from app.security import decrypt_token, encrypt_token
from app.services import baseline as baseline_svc
from app.services import billing
from app.services.pipeline import analyze_post
from app.services.sync import sync_media, update_profile

log = logging.getLogger("worker")


# ---------------------------------------------------------------- handlers


def handle_analyze_post(db, payload: dict) -> None:
    analyze_post(db, uuid.UUID(payload["post_id"]), payload.get("run_kind", "manual"))


def handle_sync_account(db, payload: dict) -> None:
    account = db.get(IgAccount, uuid.UUID(payload["ig_account_id"]))
    if account is None:
        return
    client = client_for(account)
    update_profile(account, client.get_profile())
    sync_media(db, account, client)
    baseline_svc.compute(db, account, client)


def handle_refresh_tokens(db, payload: dict) -> None:
    soon = utcnow() + timedelta(days=10)
    accounts = db.scalars(select(IgAccount).where(IgAccount.token_expires_at < soon)).all()
    for account in accounts:
        if is_demo_account(account):
            continue
        try:
            result = refresh_long_lived_token(decrypt_token(account.access_token_enc))
        except InstagramError as e:
            log.warning("token refresh failed for %s: %s", account.username, e)
            continue
        account.access_token_enc = encrypt_token(result.access_token)
        account.token_expires_at = result.expires_at


def handle_purge_raw_comments(db, payload: dict) -> None:
    cutoff = utcnow() - timedelta(days=get_settings().raw_comment_retention_days)
    db.execute(
        update(CommentLabel)
        .where(CommentLabel.created_at < cutoff, CommentLabel.text_excerpt.is_not(None))
        .values(text_excerpt=None)
    )


def handle_expire_plans(db, payload: dict) -> None:
    n = billing.expire_plans(db)
    if n:
        log.info("downgraded %d expired plans", n)


HANDLERS = {
    "analyze_post": handle_analyze_post,
    "expire_plans": handle_expire_plans,
    "sync_account": handle_sync_account,
    "refresh_tokens": handle_refresh_tokens,
    "purge_raw_comments": handle_purge_raw_comments,
}


# -------------------------------------------------------------------- loop


def run_job(job: Job) -> None:
    handler = HANDLERS.get(job.kind)
    db = SessionLocal()
    try:
        if handler is None:
            raise ValueError(f"unknown job kind {job.kind}")
        handler(db, job.payload or {})
        db.commit()
        tracked = db.get(Job, job.id)
        queue.complete(db, tracked)
    except InstagramError as e:
        db.rollback()
        tracked = db.get(Job, job.id)
        queue.fail(db, tracked, f"InstagramError: {e}", retry=not e.is_auth_error)
        if tracked.status == "failed":
            msg = ("Instagram access expired. Please reconnect your account." if e.is_auth_error
                   else "We couldn't read this post from Instagram. Try refreshing later.")
            _mark_report_failed(db, job, msg)
    except Exception as e:  # noqa: BLE001
        log.exception("job %s (%s) failed", job.id, job.kind)
        db.rollback()
        tracked = db.get(Job, job.id)
        queue.fail(db, tracked, f"{type(e).__name__}: {e}")
        if tracked.status == "failed":
            _mark_report_failed(db, job, "Analysis failed. We've been notified; try refreshing later.")
    finally:
        db.close()


def _mark_report_failed(db, job: Job, message: str) -> None:
    """Only a report that never succeeded is marked failed; a ready report keeps its last good data."""
    post_id = (job.payload or {}).get("post_id") if job.kind == "analyze_post" else None
    if not post_id:
        return
    report = db.scalar(select(Report).where(Report.post_id == uuid.UUID(post_id)))
    if report and report.status == "processing":
        report.status = "failed"
        report.data = {**(report.data or {}), "error": message}
        db.commit()


def schedule_periodic(db) -> None:
    hour = utcnow().strftime("%Y%m%d%H")
    day = utcnow().strftime("%Y%m%d")
    queue.enqueue(db, "refresh_tokens", dedupe_key=f"periodic:refresh_tokens:{day}")
    queue.enqueue(db, "purge_raw_comments", dedupe_key=f"periodic:purge:{day}")
    queue.enqueue(db, "expire_plans", dedupe_key=f"periodic:expire_plans:{day}")
    db.commit()
    log.debug("periodic jobs scheduled for %s", hour)


def run_once() -> bool:
    """Processes one job if available. Returns True if a job ran."""
    db = SessionLocal()
    try:
        job = queue.claim(db)
    finally:
        db.close()
    if job is None:
        return False
    log.info("running job %s %s %s", job.id, job.kind, job.payload)
    run_job(job)
    return True


def drain(max_jobs: int = 1000) -> int:
    """Run jobs until the queue has nothing due (used by tests and `--drain`)."""
    n = 0
    while n < max_jobs and run_once():
        n += 1
    return n


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_periodic = 0.0
    log.info("worker started")
    while not stopping:
        if time.time() - last_periodic > 3600:
            db = SessionLocal()
            try:
                schedule_periodic(db)
            finally:
                db.close()
            last_periodic = time.time()
        if not run_once():
            time.sleep(2)
    log.info("worker stopped")


if __name__ == "__main__":
    import sys

    if "--drain" in sys.argv:
        logging.basicConfig(level=logging.INFO)
        print(f"ran {drain()} jobs")
    else:
        main()
