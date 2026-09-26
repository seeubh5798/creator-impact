import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import User
from app.services import billing

log = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


class SubscribeBody(BaseModel):
    plan: Literal["pro", "pro_plus"]
    interval: Literal["monthly", "yearly"] = "monthly"


class VerifyBody(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


@router.get("")
def get_billing(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return billing.summary(db, user)


@router.post("/subscriptions")
def subscribe(body: SubscribeBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        sub = billing.create_subscription(db, user, body.plan, body.interval)
    except billing.BillingError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return {"subscription_id": sub.provider_subscription_id, "key_id": billing.get_settings().razorpay_key_id,
            "plan": sub.plan, "interval": sub.interval}


@router.post("/verify")
def verify(body: VerifyBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        sub = billing.confirm_checkout(db, user, body.razorpay_payment_id, body.razorpay_subscription_id,
                                       body.razorpay_signature)
    except billing.BillingError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return {"ok": True, "plan": user.plan, "status": sub.status, "summary": billing.summary(db, user)}


@router.post("/cancel")
def cancel(user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        billing.cancel_subscription(db, user)
    except billing.BillingError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return billing.summary(db, user)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay -> us. Configure in Dashboard -> Settings -> Webhooks with the secret
    from RAZORPAY_WEBHOOK_SECRET and the subscription.* + payment.failed events."""
    raw = await request.body()
    if not billing.verify_webhook_signature(raw, request.headers.get("X-Razorpay-Signature", "")):
        raise HTTPException(400, "Bad signature")
    try:
        payload = billing.parse_webhook(raw)
    except billing.BillingError as e:
        raise HTTPException(400, str(e)) from e
    event_id = request.headers.get("X-Razorpay-Event-Id") or f"noid:{hash(raw)}"
    ev = billing.record_webhook(db, event_id, payload.get("event", "unknown"), payload)
    if ev is None:
        return {"ok": True, "duplicate": True}
    try:
        billing.process_webhook(db, ev)
        db.commit()
    except Exception as e:  # noqa: BLE001
        # The rollback also drops the event row, so store it again with the error.
        # We still answer 200: Razorpay would otherwise retry a permanently broken
        # event for days, and the failure is visible in billing_events.
        db.rollback()
        log.exception("webhook %s failed", event_id)
        failed = billing.record_webhook(db, event_id, payload.get("event", "unknown"), payload)
        if failed:
            failed.error = str(e)[:1000]
        db.commit()
    return {"ok": True}
