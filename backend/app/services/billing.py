"""Razorpay Subscriptions.

Flow
----
1. POST /billing/subscriptions {plan, interval}  -> we create a Razorpay subscription
   and return its id + our key id.
2. The browser opens Razorpay Checkout with that subscription id. The creator pays.
3. Checkout hands the browser {payment_id, subscription_id, signature}; the browser
   POSTs it to /billing/verify. We check the HMAC and activate the plan immediately.
4. Razorpay webhooks (subscription.activated / charged / cancelled / halted / completed /
   expired, payment.failed) keep the plan and expiry in sync from then on.
5. The worker downgrades users whose plan_expires_at has passed (handle_expire_plans).

Docs: https://razorpay.com/docs/api/payments/subscriptions/
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BillingEvent, Subscription, User, utcnow

log = logging.getLogger(__name__)

API = "https://api.razorpay.com/v1"

PLANS = {
    "pro": {"name": "Pro", "monthly": 29900, "yearly": 299900},
    "pro_plus": {"name": "Pro+", "monthly": 99900, "yearly": 999900},
}
# Razorpay bills up to total_count cycles; 10 years is effectively "until cancelled".
TOTAL_COUNT = {"monthly": 120, "yearly": 10}
GRACE = timedelta(days=3)  # keep access a little past current_end while the next charge settles

ACTIVE_STATUSES = {"authenticated", "active"}
ENDED_STATUSES = {"cancelled", "completed", "expired"}


class BillingError(Exception):
    pass


def plan_id_for(plan: str, interval: str) -> str:
    s = get_settings()
    lookup = {
        ("pro", "monthly"): s.razorpay_plan_pro_monthly,
        ("pro", "yearly"): s.razorpay_plan_pro_yearly,
        ("pro_plus", "monthly"): s.razorpay_plan_pro_plus_monthly,
        ("pro_plus", "yearly"): s.razorpay_plan_pro_plus_yearly,
    }
    plan_id = lookup.get((plan, interval), "")
    if not plan_id:
        raise BillingError(f"No Razorpay plan configured for {plan}/{interval}")
    return plan_id


def plan_from_plan_id(plan_id: str) -> tuple[str, str] | None:
    s = get_settings()
    for key, value in (
        (("pro", "monthly"), s.razorpay_plan_pro_monthly),
        (("pro", "yearly"), s.razorpay_plan_pro_yearly),
        (("pro_plus", "monthly"), s.razorpay_plan_pro_plus_monthly),
        (("pro_plus", "yearly"), s.razorpay_plan_pro_plus_yearly),
    ):
        if value and value == plan_id:
            return key
    return None


def _client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(base_url=API, auth=(s.razorpay_key_id, s.razorpay_key_secret), timeout=20)


def _raise_for(resp: httpx.Response) -> dict:
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400:
        desc = (body.get("error") or {}).get("description") or resp.text[:200]
        raise BillingError(f"Razorpay: {desc}")
    return body


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


# ----------------------------------------------------------------- create


def create_subscription(db: Session, user: User, plan: str, interval: str) -> Subscription:
    if plan not in PLANS or interval not in TOTAL_COUNT:
        raise BillingError("Unknown plan")
    if not get_settings().billing_enabled:
        raise BillingError("Billing is not configured")
    if user.is_demo:
        raise BillingError("The demo account can't subscribe")

    current = active_subscription(db, user)
    if current and current.plan == plan and not current.cancel_at_cycle_end:
        raise BillingError("You already have this plan")

    plan_id = plan_id_for(plan, interval)
    with _client() as c:
        body = _raise_for(c.post("/subscriptions", json={
            "plan_id": plan_id,
            "total_count": TOTAL_COUNT[interval],
            "customer_notify": 1,
            "notes": {"user_id": str(user.id), "plan": plan, "interval": interval},
        }))
    sub = Subscription(
        user_id=user.id,
        provider_subscription_id=body["id"],
        provider_plan_id=plan_id,
        plan=plan,
        interval=interval,
        status=body.get("status", "created"),
        raw=body,
    )
    db.add(sub)
    db.flush()
    return sub


# ----------------------------------------------------------------- verify


def verify_checkout_signature(payment_id: str, subscription_id: str, signature: str) -> bool:
    secret = get_settings().razorpay_key_secret.encode()
    expected = hmac.new(secret, f"{payment_id}|{subscription_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    secret = get_settings().razorpay_webhook_secret.encode()
    if not secret:
        return False
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def confirm_checkout(db: Session, user: User, payment_id: str, subscription_id: str, signature: str) -> Subscription:
    sub = db.scalar(select(Subscription).where(Subscription.provider_subscription_id == subscription_id))
    if sub is None or sub.user_id != user.id:
        raise BillingError("Unknown subscription")
    if not verify_checkout_signature(payment_id, subscription_id, signature):
        raise BillingError("Payment signature did not match")
    # Fetch the live entity for the real period; fall back to a conservative estimate.
    try:
        with _client() as c:
            entity = _raise_for(c.get(f"/subscriptions/{subscription_id}"))
    except (BillingError, httpx.HTTPError) as e:
        log.warning("could not fetch subscription %s after checkout: %s", subscription_id, e)
        entity = {"status": "authenticated"}
    sub.last_payment_id = payment_id
    apply_subscription_entity(db, sub, entity, fallback_days=35 if sub.interval == "monthly" else 370)
    return sub


# --------------------------------------------------------------- webhooks


def record_webhook(db: Session, event_id: str, event_type: str, payload: dict) -> BillingEvent | None:
    """Stores the event; returns None if this event id was already received."""
    if db.scalar(select(BillingEvent).where(BillingEvent.event_id == event_id)):
        return None
    ev = BillingEvent(event_id=event_id, event_type=event_type, payload=payload)
    db.add(ev)
    db.flush()
    return ev


def process_webhook(db: Session, ev: BillingEvent) -> None:
    payload = ev.payload.get("payload", {})
    entity = (payload.get("subscription") or {}).get("entity")
    payment = (payload.get("payment") or {}).get("entity") or {}
    try:
        if entity:
            sub = db.scalar(select(Subscription).where(Subscription.provider_subscription_id == entity["id"]))
            if sub is None:
                # Created outside this app (e.g. from the dashboard): attach by notes.user_id if present.
                user_id = (entity.get("notes") or {}).get("user_id")
                mapped = plan_from_plan_id(entity.get("plan_id", ""))
                if user_id and mapped:
                    sub = Subscription(user_id=user_id, provider_subscription_id=entity["id"],
                                       provider_plan_id=entity["plan_id"], plan=mapped[0], interval=mapped[1])
                    db.add(sub)
                    db.flush()
            if sub is not None:
                if payment.get("id"):
                    sub.last_payment_id = payment["id"]
                apply_subscription_entity(db, sub, entity)
        elif ev.event_type == "payment.failed":
            log.info("payment failed: %s", payment.get("id"))
        ev.processed = True
    except Exception as e:  # noqa: BLE001
        ev.error = str(e)[:1000]
        raise


def apply_subscription_entity(db: Session, sub: Subscription, entity: dict, fallback_days: int | None = None) -> None:
    status = entity.get("status") or sub.status
    sub.status = status
    sub.current_start = _ts(entity.get("current_start")) or sub.current_start
    sub.current_end = _ts(entity.get("current_end")) or sub.current_end
    sub.cancel_at_cycle_end = bool(entity.get("has_scheduled_changes")) or sub.cancel_at_cycle_end
    if entity:
        sub.raw = entity
    if status == "cancelled":
        sub.cancel_at_cycle_end = False

    user = db.get(User, sub.user_id)
    if user is None:
        return
    if status in ACTIVE_STATUSES:
        end = sub.current_end or (utcnow() + timedelta(days=fallback_days or 35))
        user.plan = sub.plan
        user.plan_expires_at = end + GRACE
    elif status in ENDED_STATUSES or status == "halted":
        # Keep access until the paid period runs out; the worker downgrades after that.
        if user.plan == sub.plan and sub.current_end:
            user.plan_expires_at = min(user.plan_expires_at or sub.current_end + GRACE, sub.current_end + GRACE)
        elif user.plan == sub.plan and not sub.current_end:
            user.plan = "free"
            user.plan_expires_at = None
    db.flush()


# ----------------------------------------------------------------- cancel


def cancel_subscription(db: Session, user: User) -> Subscription:
    sub = active_subscription(db, user)
    if sub is None:
        raise BillingError("No active subscription")
    with _client() as c:
        entity = _raise_for(c.post(f"/subscriptions/{sub.provider_subscription_id}/cancel",
                                   json={"cancel_at_cycle_end": 1}))
    apply_subscription_entity(db, sub, entity)
    sub.cancel_at_cycle_end = entity.get("status") != "cancelled"
    db.flush()
    return sub


def active_subscription(db: Session, user: User) -> Subscription | None:
    subs = db.scalars(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.desc())
    ).all()
    for s in subs:
        if s.status in ACTIVE_STATUSES or (s.status == "cancelled" and s.current_end and s.current_end > utcnow()):
            return s
    return None


def expire_plans(db: Session) -> int:
    """Downgrade users whose paid period (plus grace) has ended. Called daily by the worker."""
    now = utcnow()
    users = db.scalars(select(User).where(User.plan.in_(("pro", "pro_plus")), User.plan_expires_at < now)).all()
    for u in users:
        u.plan = "free"
        u.plan_expires_at = None
    db.flush()
    return len(users)


def summary(db: Session, user: User) -> dict:
    s = get_settings()
    sub = active_subscription(db, user)
    return {
        "enabled": s.billing_enabled,
        "key_id": s.razorpay_key_id if s.billing_enabled else None,
        "plan": user.plan,
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "subscription": None if sub is None else {
            "id": sub.provider_subscription_id,
            "plan": sub.plan,
            "interval": sub.interval,
            "status": sub.status,
            "current_end": sub.current_end.isoformat() if sub.current_end else None,
            "cancel_at_cycle_end": sub.cancel_at_cycle_end,
        },
        "plans": {
            key: {"name": v["name"], "monthly": v["monthly"], "yearly": v["yearly"]} for key, v in PLANS.items()
        },
    }


def parse_webhook(raw: bytes) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise BillingError("Invalid JSON") from e
