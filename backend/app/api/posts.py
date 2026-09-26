import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_account, current_user
from app.db import get_db
from app.instagram import InstagramError, client_for
from app.models import IgAccount, Post, Report, User
from app.services import reports as reports_svc
from app.services.sync import sync_media

router = APIRouter(prefix="/posts", tags=["posts"])


class SponsorBody(BaseModel):
    brand_name: str | None = Field(default=None, max_length=80)


def _post_out(post: Post, report: Report | None) -> dict:
    return {
        "id": str(post.id),
        "media_type": post.media_product_type or post.media_type,
        "caption": (post.caption or "")[:200],
        "permalink": post.permalink,
        "thumbnail_url": post.thumbnail_url,
        "posted_at": post.posted_at.isoformat() if post.posted_at else None,
        "like_count": post.like_count,
        "comments_count": post.comments_count,
        "is_sponsored": post.is_sponsored,
        "brand_name": post.brand_name,
        "report": None if report is None else {"id": str(report.id), "status": report.status, "score": report.score},
    }


def _own_post(db: Session, account: IgAccount, post_id: uuid.UUID) -> Post:
    post = db.get(Post, post_id)
    if post is None or post.ig_account_id != account.id:
        raise HTTPException(404, "Post not found")
    return post


@router.get("")
def list_posts(account: IgAccount = Depends(current_account), db: Session = Depends(get_db)):
    posts = db.scalars(
        select(Post).where(Post.ig_account_id == account.id).order_by(Post.posted_at.desc()).limit(50)
    ).all()
    reports = {r.post_id: r for r in db.scalars(select(Report).where(Report.post_id.in_([p.id for p in posts])))}
    return {"posts": [_post_out(p, reports.get(p.id)) for p in posts]}


@router.post("/sync")
def sync(account: IgAccount = Depends(current_account), db: Session = Depends(get_db)):
    try:
        sync_media(db, account, client_for(account))
    except InstagramError as e:
        raise HTTPException(502 if not e.is_auth_error else 401, f"Instagram: {e}") from e
    db.commit()
    return list_posts(account, db)


@router.post("/{post_id}/sponsor")
def sponsor(post_id: uuid.UUID, body: SponsorBody, user: User = Depends(current_user),
            account: IgAccount = Depends(current_account), db: Session = Depends(get_db)):
    post = _own_post(db, account, post_id)
    try:
        report = reports_svc.tag_sponsored(db, user, post, body.brand_name)
    except reports_svc.QuotaExceeded as e:
        raise HTTPException(402, str(e)) from e
    db.commit()
    return {"report_id": str(report.id), "slug": report.slug, "status": report.status}


@router.delete("/{post_id}/sponsor")
def unsponsor(post_id: uuid.UUID, account: IgAccount = Depends(current_account), db: Session = Depends(get_db)):
    reports_svc.untag_sponsored(db, _own_post(db, account, post_id))
    db.commit()
    return {"ok": True}
