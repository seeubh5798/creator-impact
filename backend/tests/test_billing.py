"""Razorpay subscriptions: create -> checkout verify -> webhooks -> cancel -> expiry."""

import hashlib
import hmac
import json
import time

import httpx
import pytest
import respx
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import BillingEvent, Subscription, User
from app.services import billing

API = "https://api.razorpay.com/v1"


@pytest.fixture(autouse=True)
def razorpay_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "razorpay_key_id", "rzp_test_key")
    monkeypatch.setattr(s, "razorpay_key_secret", "rzp_test_secret")
    monkeypatch.setattr(s, "razorpay_webhook_secret", "whsec")
    monkeypatch.setattr(s, "razorpay_plan_pro_monthly", "plan_pro_m")
    monkeypatch.setattr(s, "razorpay_plan_pro_plus_monthly", "plan_proplus_m")


@pytest.fixture
def paid_client(demo_client):
    """Demo user flipped to a normal free user so they can subscribe."""
    with SessionLocal() as db:
        user = db.scalars(select(User)).one()
        user.is_demo = False
        user.plan = "free"
        db.commit()
    return demo_client


def _sig(payment_id, sub_id, secret="rzp_test_secret"):
    return hmac.new(secret.encode(), f"{payment_id}|{sub_id}".encode(), hashlib.sha256).hexdigest()


def _webhook(client, event, entity, event_id, payment=None, secret="whsec"):
    body = json.dumps({"event": event, "payload": {"subscription": {"entity": entity},
                                                   **({"payment": {"entity": payment}} if payment else {})}}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/billing/webhook", content=body,
                       headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id,
                                "Content-Type": "application/json"})


def _entity(sub_id, status, plan_id="plan_pro_m", days=30, scheduled=False):
    now = int(time.time())
    return {"id": sub_id, "plan_id": plan_id, "status": status, "current_start": now,
            "current_end": now + days * 86400, "has_scheduled_changes": scheduled,
            "notes": {}}


@respx.mock
def test_subscribe_verify_webhooks_cancel_expire(paid_client):
    c = paid_client
    assert c.get("/billing").json()["plan"] == "free"

    # 1. Create subscription
    respx.post(f"{API}/subscriptions").mock(return_value=httpx.Response(200, json={
        "id": "sub_123", "plan_id": "plan_pro_m", "status": "created"}))
    r = c.post("/billing/subscriptions", json={"plan": "pro"})
    assert r.status_code == 200, r.text
    assert r.json() == {"subscription_id": "sub_123", "key_id": "rzp_test_key", "plan": "pro", "interval": "monthly"}
    sent = json.loads(respx.calls.last.request.content)
    assert sent["plan_id"] == "plan_pro_m" and sent["total_count"] == 120

    # 2. Checkout returns; bad signature is rejected, good one activates immediately
    bad = c.post("/billing/verify", json={"razorpay_payment_id": "pay_1", "razorpay_subscription_id": "sub_123",
                                          "razorpay_signature": "nope"})
    assert bad.status_code == 400
    respx.get(f"{API}/subscriptions/sub_123").mock(return_value=httpx.Response(200, json=_entity("sub_123", "active")))
    ok = c.post("/billing/verify", json={"razorpay_payment_id": "pay_1", "razorpay_subscription_id": "sub_123",
                                         "razorpay_signature": _sig("pay_1", "sub_123")})
    assert ok.status_code == 200 and ok.json()["plan"] == "pro"
    me = c.get("/auth/me").json()
    assert me["usage"]["plan"] == "pro" and me["usage"]["monthly_limit"] is None

    # 3. Webhooks: bad signature, duplicate event id, charged event
    body = json.dumps({"event": "subscription.charged"}).encode()
    assert c.post("/billing/webhook", content=body, headers={"X-Razorpay-Signature": "x"}).status_code == 400
    assert _webhook(c, "subscription.charged", _entity("sub_123", "active", days=60), "evt_1",
                    payment={"id": "pay_2"}).json() == {"ok": True}
    assert _webhook(c, "subscription.charged", _entity("sub_123", "active", days=60), "evt_1").json()["duplicate"] is True
    with SessionLocal() as db:
        sub = db.scalars(select(Subscription)).one()
        assert sub.last_payment_id == "pay_2" and sub.status == "active"
        assert len(db.scalars(select(BillingEvent)).all()) == 1

    # 4. Cancel at cycle end: plan stays until current_end
    respx.post(f"{API}/subscriptions/sub_123/cancel").mock(
        return_value=httpx.Response(200, json=_entity("sub_123", "active", days=20, scheduled=True)))
    r = c.post("/billing/cancel")
    assert r.status_code == 200 and r.json()["subscription"]["cancel_at_cycle_end"] is True
    assert c.get("/auth/me").json()["usage"]["plan"] == "pro"

    # Razorpay later confirms the cancellation
    _webhook(c, "subscription.cancelled", _entity("sub_123", "cancelled", days=20), "evt_2")
    assert c.get("/billing").json()["subscription"]["status"] == "cancelled"
    assert c.get("/auth/me").json()["usage"]["plan"] == "pro"  # still inside paid period

    # 5. Period ends -> effective plan is free even before the worker runs; worker downgrades
    with SessionLocal() as db:
        user = db.scalars(select(User)).one()
        user.plan_expires_at = billing.utcnow() - billing.timedelta(days=1)
        db.scalars(select(Subscription)).one().current_end = billing.utcnow() - billing.timedelta(days=4)
        db.commit()
    assert c.get("/auth/me").json()["usage"]["plan"] == "free"
    with SessionLocal() as db:
        assert billing.expire_plans(db) == 1
        db.commit()
        assert db.scalars(select(User)).one().plan == "free"
    assert c.get("/billing").json()["subscription"] is None


@respx.mock
def test_subscription_guards(paid_client, demo_client):
    c = paid_client
    assert c.post("/billing/subscriptions", json={"plan": "enterprise"}).status_code == 422
    get_settings().razorpay_plan_pro_plus_monthly = ""
    r = c.post("/billing/subscriptions", json={"plan": "pro_plus"})
    assert r.status_code == 400 and "No Razorpay plan" in r.json()["detail"]
    respx.post(f"{API}/subscriptions").mock(return_value=httpx.Response(400, json={
        "error": {"description": "The plan id provided does not exist"}}))
    r = c.post("/billing/subscriptions", json={"plan": "pro"})
    assert r.status_code == 400 and "does not exist" in r.json()["detail"]


def test_webhook_for_unknown_subscription_uses_notes(paid_client):
    with SessionLocal() as db:
        user_id = str(db.scalars(select(User)).one().id)
    entity = _entity("sub_ext", "active") | {"notes": {"user_id": user_id}}
    assert _webhook(paid_client, "subscription.activated", entity, "evt_x").status_code == 200
    assert paid_client.get("/billing").json()["subscription"]["id"] == "sub_ext"
    assert paid_client.get("/auth/me").json()["usage"]["plan"] == "pro"


def test_billing_disabled_without_keys(demo_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "razorpay_key_id", "")
    assert demo_client.get("/billing").json()["enabled"] is False
    assert demo_client.post("/billing/subscriptions", json={"plan": "pro"}).status_code == 400
