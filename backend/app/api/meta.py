"""Callbacks Meta requires for app review: deauthorize and data deletion.

Configure in the Meta app dashboard (Instagram > API setup with Instagram login):
  Deauthorize callback URL:    {FRONTEND_URL}/api/meta/deauthorize
  Data deletion request URL:   {FRONTEND_URL}/api/meta/data-deletion
"""

import secrets

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import IgAccount
from app.security import parse_meta_signed_request

router = APIRouter(prefix="/meta", tags=["meta"])


def _delete_for(db: Session, signed_request: str) -> None:
    data = parse_meta_signed_request(signed_request)
    if data is None:
        raise HTTPException(400, "Invalid signed_request")
    ig_user_id = str(data.get("user_id", ""))
    account = db.scalar(select(IgAccount).where(IgAccount.ig_user_id == ig_user_id))
    if account is not None:
        db.delete(account.user)  # cascades to account, posts, labels, reports
        db.commit()


@router.post("/deauthorize")
def deauthorize(signed_request: str = Form(...), db: Session = Depends(get_db)):
    _delete_for(db, signed_request)
    return {"ok": True}


@router.post("/data-deletion")
def data_deletion(signed_request: str = Form(...), db: Session = Depends(get_db)):
    _delete_for(db, signed_request)
    code = secrets.token_hex(8)
    return {"url": f"{get_settings().frontend_url.rstrip('/')}/privacy#deletion", "confirmation_code": code}
