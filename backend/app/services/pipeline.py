"""The analysis pipeline: fetch -> preprocess -> classify -> aggregate -> score -> report."""

import logging
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.classifier import Classifier, get_classifier
from app.analysis.preprocess import Comment, preprocess, strip_mentions
from app.analysis.scoring import ScoreInput, impact_score, percentile, verdict
from app.analysis.summarize import summarize_topics
from app.config import get_settings
from app.instagram import InstagramClient, client_for
from app.models import AnalysisRun, CommentLabel, IgAccount, Post, PostMetric, Report, utcnow
from app.security import hash_comment_id
from app.services import baseline as baseline_svc
from app.services.sync import parse_ig_time

log = logging.getLogger(__name__)

REAL_CATEGORIES = ("buying_intent", "question", "objection", "praise", "other")


def analyze_post(
    db: Session,
    post_id: uuid.UUID,
    run_kind: str = "manual",
    client: InstagramClient | None = None,
    classifier: Classifier | None = None,
) -> Report:
    settings = get_settings()
    post = db.get(Post, post_id)
    if post is None:
        raise LookupError(f"post {post_id} not found")
    account: IgAccount = post.account
    client = client or client_for(account)
    classifier = classifier or get_classifier()
    report = db.scalar(select(Report).where(Report.post_id == post.id))
    if report is None:
        raise LookupError(f"no report for post {post_id}")

    run = AnalysisRun(post_id=post.id, run_kind=run_kind, status="running", started_at=utcnow())
    db.add(run)
    db.flush()

    try:
        # 1. Metrics
        insights = client.get_media_insights(post.ig_media_id)
        db.add(PostMetric(post_id=post.id, **insights))

        # 2. New comments only (labels are cached per comment)
        raw = client.list_comments(post.ig_media_id, settings.max_comments_per_post)
        known = set(db.scalars(select(CommentLabel.comment_hash).where(CommentLabel.post_id == post.id)))
        fresh = []
        for c in raw:
            h = hash_comment_id(str(c["id"]))
            if h in known:
                continue
            known.add(h)
            fresh.append(Comment(
                comment_id=h,
                text=c.get("text") or "",
                username=c.get("username"),
                like_count=int(c.get("like_count") or 0),
                timestamp=parse_ig_time(c.get("timestamp")),
            ))

        # 3. Preprocess + classify
        prepared, _ = preprocess(fresh, account.username)
        to_classify = [c for c in prepared if c.category is None]
        classifier.classify(to_classify)
        run.llm_used = getattr(classifier, "name", "") == "llm"

        for c in prepared:
            db.add(CommentLabel(
                post_id=post.id,
                comment_hash=c.comment_id,
                category=c.category or "other",
                language=c.language,
                confidence=c.confidence,
                topic=c.topic,
                like_count=c.like_count,
                text_excerpt=strip_mentions(c.clean)[:280] or None,
                commented_at=c.timestamp,
            ))
        db.flush()

        # 4. Aggregate over every label for this post
        labels = db.scalars(select(CommentLabel).where(CommentLabel.post_id == post.id)).all()
        base = baseline_svc.get_or_refresh(db, account, client)
        data = build_report_data(post, account, insights, labels, base, run_kind)

        report.status = "ready"
        report.score = data["score"]
        report.verdict = data["verdict"]
        report.data = data
        run.status = "done"
        run.total_comments = len(labels)
        run.spam_removed = data["comments"]["spam_removed"]
        run.finished_at = utcnow()
        db.flush()
        return report
    except Exception as e:
        run.status = "failed"
        run.error = str(e)[:2000]
        run.finished_at = utcnow()
        if report.status == "processing":
            report.status = "failed"
        db.flush()
        raise


def build_report_data(post: Post, account: IgAccount, insights: dict, labels, base, run_kind: str) -> dict:
    counts = Counter(l.category for l in labels)
    languages = Counter(l.language for l in labels if l.category in REAL_CATEGORIES)
    spam = counts.get("spam", 0)
    real = sum(counts.get(c, 0) for c in REAL_CATEGORIES)
    intent = counts.get("buying_intent", 0)
    intent_rate = (intent / real) if real else None

    reach = insights.get("reach")
    comments_n = insights.get("comments") if insights.get("comments") is not None else post.comments_count
    comment_rate = (comments_n / reach) if comments_n is not None and reach else None

    score, parts = impact_score(ScoreInput(
        intent_rate=intent_rate,
        saves=insights.get("saves"), shares=insights.get("shares"), reach=reach, comment_rate=comment_rate,
        base_saves=base.median_saves, base_shares=base.median_shares,
        base_reach=base.median_reach, base_comment_rate=base.median_comment_rate,
    ))
    eng = baseline_svc.engagement_rate(insights.get("saves"), insights.get("shares"), reach)
    pct = percentile(eng, [s.get("engagement_rate") for s in (base.samples or [])])

    def metric(value, base_value):
        r = (value / base_value) if value is not None and base_value else None
        return {"value": value, "baseline": base_value, "ratio": round(r, 2) if r is not None else None}

    questions = summarize_topics(
        [(l.topic, l.text_excerpt) for l in labels if l.category in ("question", "buying_intent") and l.topic]
    )
    objections = summarize_topics([(l.topic, l.text_excerpt) for l in labels if l.category == "objection" and l.topic])
    quotes = [
        {"text": l.text_excerpt[:140]}
        for l in sorted(
            (l for l in labels if l.category == "buying_intent" and l.text_excerpt and len(l.text_excerpt) >= 8),
            key=lambda l: l.like_count,
            reverse=True,
        )[:2]
    ]

    now = datetime.now(timezone.utc)
    hours_since = round((now - post.posted_at).total_seconds() / 3600) if post.posted_at else None
    return {
        "version": 1,
        "creator": {
            "username": account.username,
            "profile_picture_url": account.profile_picture_url,
            "followers_count": account.followers_count,
        },
        "post": {
            "permalink": post.permalink,
            "media_type": post.media_product_type or post.media_type,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "thumbnail_url": post.thumbnail_url,
            "caption_excerpt": (post.caption or "")[:140],
        },
        "brand_name": post.brand_name,
        "score": score,
        "score_parts": parts,
        "verdict": verdict(score, intent_rate),
        "percentile": pct,
        "metrics": {
            "reach": metric(reach, base.median_reach),
            "saves": metric(insights.get("saves"), base.median_saves),
            "shares": metric(insights.get("shares"), base.median_shares),
            "likes": metric(insights.get("likes"), base.median_likes),
            "comments": metric(comments_n, base.median_comments),
            "views": {"value": insights.get("views"), "baseline": None, "ratio": None},
        },
        "baseline": {"sample_size": base.sample_size, "computed_at": base.computed_at.isoformat()},
        "comments": {
            "total": len(labels),
            "analyzed": real,
            "spam_removed": spam,
            "breakdown": {c: counts.get(c, 0) for c in REAL_CATEGORIES},
            "languages": dict(languages),
        },
        "buying_intent": {"count": intent, "rate": round(intent_rate, 4) if intent_rate is not None else None},
        "top_questions": [{"label": t.label, "count": t.count} for t in questions],
        "objections": [{"label": t.label, "count": t.count} for t in objections],
        "quotes": quotes,
        "run_kind": run_kind,
        "hours_since_post": hours_since,
        "updated_at": now.isoformat(),
    }
