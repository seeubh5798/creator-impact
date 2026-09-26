import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import Report, User
from app.services import reports as reports_svc

router = APIRouter(tags=["reports"])


class ReportUpdate(BaseModel):
    is_public: bool | None = None


def _own_report(db: Session, user: User, report_id: uuid.UUID) -> Report:
    report = db.get(Report, report_id)
    if report is None or report.user_id != user.id:
        raise HTTPException(404, "Report not found")
    return report


@router.get("/reports")
def list_reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Report).where(Report.user_id == user.id).order_by(Report.created_at.desc())).all()
    return {"reports": [
        {"id": str(r.id), "slug": r.slug, "status": r.status, "score": r.score, "verdict": r.verdict,
         "brand_name": r.post.brand_name, "posted_at": r.post.posted_at.isoformat() if r.post.posted_at else None,
         "thumbnail_url": r.post.thumbnail_url, "created_at": r.created_at.isoformat(), "view_count": r.view_count}
        for r in rows
    ]}


@router.get("/reports/{report_id}")
def get_report(report_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return reports_svc.serialize(_own_report(db, user, report_id), public=False)


@router.patch("/reports/{report_id}")
def patch_report(report_id: uuid.UUID, body: ReportUpdate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    report = _own_report(db, user, report_id)
    if body.is_public is not None:
        report.is_public = body.is_public
    db.commit()
    return reports_svc.serialize(report, public=False)


@router.post("/reports/{report_id}/refresh")
def refresh_report(report_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = _own_report(db, user, report_id)
    queued = reports_svc.request_refresh(db, report.post)
    db.commit()
    return {"queued": queued}


@router.get("/public/reports/{slug}")
def public_report(slug: str, db: Session = Depends(get_db)):
    report = db.scalar(select(Report).where(Report.slug == slug))
    if report is None or not report.is_public or report.status != "ready":
        raise HTTPException(404, "Report not found")
    db.execute(update(Report).where(Report.id == report.id).values(view_count=Report.view_count + 1))
    db.commit()
    return reports_svc.serialize(report, public=True)
