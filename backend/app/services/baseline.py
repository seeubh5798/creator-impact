"""Creator baseline: medians of the last N non-sponsored posts."""

import logging
from datetime import timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.instagram import InstagramClient, InstagramError
from app.models import Baseline, IgAccount, Post, PostMetric, utcnow

log = logging.getLogger(__name__)

STALE_AFTER = timedelta(hours=24)


def _med(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return float(median(vals)) if vals else None


def engagement_rate(saves, shares, reach) -> float | None:
    if reach and reach > 0 and (saves is not None or shares is not None):
        return ((saves or 0) + (shares or 0)) / reach
    return None


def get_or_refresh(db: Session, account: IgAccount, client: InstagramClient, force: bool = False) -> Baseline:
    baseline = db.get(Baseline, account.id)
    if baseline and not force and baseline.sample_size > 0 and utcnow() - baseline.computed_at < STALE_AFTER:
        return baseline
    return compute(db, account, client)


def compute(db: Session, account: IgAccount, client: InstagramClient) -> Baseline:
    n = get_settings().baseline_sample_size
    posts = db.scalars(
        select(Post)
        .where(Post.ig_account_id == account.id, Post.is_sponsored.is_(False))
        .order_by(Post.posted_at.desc())
        .limit(n)
    ).all()
    samples = []
    for post in posts:
        try:
            ins = client.get_media_insights(post.ig_media_id)
        except InstagramError as e:
            if e.is_auth_error:
                raise
            log.info("skipping %s in baseline: %s", post.ig_media_id, e)
            continue
        db.add(PostMetric(post_id=post.id, **ins))
        comments = ins.get("comments") if ins.get("comments") is not None else post.comments_count
        samples.append({
            "media_id": post.ig_media_id,
            "reach": ins.get("reach"),
            "saves": ins.get("saves"),
            "shares": ins.get("shares"),
            "likes": ins.get("likes") if ins.get("likes") is not None else post.like_count,
            "comments": comments,
            "comment_rate": (comments / ins["reach"]) if comments is not None and ins.get("reach") else None,
            "engagement_rate": engagement_rate(ins.get("saves"), ins.get("shares"), ins.get("reach")),
        })

    baseline = db.get(Baseline, account.id) or Baseline(ig_account_id=account.id)
    baseline.computed_at = utcnow()
    baseline.sample_size = len(samples)
    baseline.median_reach = _med([s["reach"] for s in samples])
    baseline.median_saves = _med([s["saves"] for s in samples])
    baseline.median_shares = _med([s["shares"] for s in samples])
    baseline.median_likes = _med([s["likes"] for s in samples])
    baseline.median_comments = _med([s["comments"] for s in samples])
    baseline.median_comment_rate = _med([s["comment_rate"] for s in samples])
    baseline.samples = samples
    db.add(baseline)
    db.flush()
    return baseline
