"""Tagging sponsored posts, plan limits, scheduling re-analysis, serializing reports."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import queue
from app.config import get_settings
from app.models import Post, Report, User, utcnow
from app.security import new_slug

UNLIMITED_PLANS = {"pro", "pro_plus", "founding"}
# Re-run the analysis as comments keep arriving.
RERUN_OFFSETS = {"24h": timedelta(hours=24), "72h": timedelta(hours=72), "7d": timedelta(days=7)}


class QuotaExceeded(Exception):
    pass


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def reports_this_month(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count(Report.id)).where(Report.user_id == user.id, Report.created_at >= month_start())
    ) or 0


def effective_plan(user: User) -> str:
    if user.plan in ("pro", "pro_plus") and user.plan_expires_at and user.plan_expires_at < utcnow():
        return "free"
    return user.plan


def usage(db: Session, user: User) -> dict:
    plan = effective_plan(user)
    limit = None if plan in UNLIMITED_PLANS else get_settings().free_reports_per_month
    used = reports_this_month(db, user)
    return {"plan": plan, "reports_this_month": used, "monthly_limit": limit,
            "remaining": None if limit is None else max(0, limit - used)}


def tag_sponsored(db: Session, user: User, post: Post, brand_name: str | None) -> Report:
    report = db.scalar(select(Report).where(Report.post_id == post.id))
    if report is None:
        u = usage(db, user)
        if u["remaining"] is not None and u["remaining"] <= 0:
            raise QuotaExceeded(f"Free plan includes {u['monthly_limit']} reports per month")
        report = Report(post_id=post.id, user_id=user.id, slug=new_slug(), status="processing")
        db.add(report)
    post.is_sponsored = True
    post.brand_name = (brand_name or "").strip()[:80] or None
    post.sponsored_at = post.sponsored_at or utcnow()
    db.flush()
    schedule_analysis(db, post)
    return report


def untag_sponsored(db: Session, post: Post) -> None:
    post.is_sponsored = False
    report = db.scalar(select(Report).where(Report.post_id == post.id))
    if report:
        db.delete(report)
    db.flush()


def schedule_analysis(db: Session, post: Post) -> None:
    queue.enqueue(db, "analyze_post", {"post_id": str(post.id), "run_kind": "initial"},
                  dedupe_key=f"analyze:{post.id}:initial")
    if post.posted_at is None:
        return
    now = utcnow()
    for kind, offset in RERUN_OFFSETS.items():
        when = post.posted_at + offset
        if when > now:
            queue.enqueue(db, "analyze_post", {"post_id": str(post.id), "run_kind": kind},
                          run_at=when, dedupe_key=f"analyze:{post.id}:{kind}")


def request_refresh(db: Session, post: Post) -> bool:
    job = queue.enqueue(db, "analyze_post", {"post_id": str(post.id), "run_kind": "manual"},
                        dedupe_key=f"analyze:{post.id}:manual")
    return job is not None


def serialize(report: Report, public: bool) -> dict:
    out = {
        "id": str(report.id) if not public else None,
        "slug": report.slug,
        "status": report.status,
        "score": report.score,
        "verdict": report.verdict,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        "data": report.data or {},
    }
    if public:
        out.pop("id")
        data = dict(out["data"])
        data.pop("score_parts", None)  # internal detail
        out["data"] = data
    else:
        out["post_id"] = str(report.post_id)
        out["is_public"] = report.is_public
        out["view_count"] = report.view_count
    return out
