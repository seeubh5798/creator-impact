"""Keep ig_accounts and posts in sync with Instagram."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.instagram import InstagramClient
from app.models import IgAccount, Post, utcnow


def parse_ig_time(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(value, fmt).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def update_profile(account: IgAccount, profile: dict) -> None:
    account.username = profile.get("username") or account.username
    account.account_type = profile.get("account_type")
    account.profile_picture_url = profile.get("profile_picture_url")
    account.followers_count = profile.get("followers_count")
    account.media_count = profile.get("media_count")


def sync_media(db: Session, account: IgAccount, client: InstagramClient, limit: int = 50) -> list[Post]:
    items = client.list_media(limit=limit)
    ids = [m["id"] for m in items]
    existing = {p.ig_media_id: p for p in db.scalars(select(Post).where(Post.ig_media_id.in_(ids)))}
    posts = []
    for m in items:
        post = existing.get(m["id"])
        if post is None:
            post = Post(ig_account_id=account.id, ig_media_id=m["id"])
            db.add(post)
        post.media_type = m.get("media_type")
        post.media_product_type = m.get("media_product_type")
        post.caption = (m.get("caption") or "")[:2200]
        post.permalink = m.get("permalink")
        post.thumbnail_url = m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") == "IMAGE" else None)
        post.posted_at = parse_ig_time(m.get("timestamp"))
        post.like_count = m.get("like_count")
        post.comments_count = m.get("comments_count")
        posts.append(post)
    account.last_synced_at = utcnow()
    db.flush()
    return posts
