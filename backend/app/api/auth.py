import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import queue
from app.api.deps import current_user
from app.config import get_settings
from app.db import get_db
from app.instagram import DEMO_PREFIX, InstagramError
from app.instagram.client import GraphInstagramClient, authorize_url, exchange_code
from app.instagram.demo import DemoInstagramClient
from app.models import IgAccount, User
from app.security import SESSION_COOKIE, SESSION_DAYS, STATE_COOKIE, create_session_token, encrypt_token, new_state
from app.services import reports as reports_svc
from app.services.sync import update_profile

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id),
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        secure=s.is_production,
        samesite="lax",
        path="/",
    )


@router.get("/instagram/login")
def instagram_login():
    s = get_settings()
    if not s.instagram_app_id:
        raise HTTPException(503, "Instagram login is not configured. Set INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET.")
    state = new_state()
    response = RedirectResponse(authorize_url(state), status_code=302)
    response.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, secure=s.is_production, samesite="lax")
    return response


@router.get("/instagram/callback")
def instagram_callback(request: Request, code: str | None = None, state: str | None = None,
                       error: str | None = None, db: Session = Depends(get_db)):
    s = get_settings()
    front = s.frontend_url.rstrip("/")
    if error or not code:
        return RedirectResponse(f"{front}/login?error={error or 'missing_code'}", status_code=302)
    if not state or state != request.cookies.get(STATE_COOKIE):
        return RedirectResponse(f"{front}/login?error=state_mismatch", status_code=302)

    try:
        token = exchange_code(code)
        profile = GraphInstagramClient(token.access_token).get_profile()
    except InstagramError as e:
        log.warning("instagram oauth failed: %s", e)
        return RedirectResponse(f"{front}/login?error=instagram", status_code=302)

    ig_user_id = str(profile.get("user_id") or profile.get("id") or token.user_id)
    account = db.scalar(select(IgAccount).where(IgAccount.ig_user_id == ig_user_id))
    if account is None:
        user = User(display_name=profile.get("username"))
        db.add(user)
        db.flush()
        account = IgAccount(user_id=user.id, ig_user_id=ig_user_id, username=profile.get("username") or "",
                            access_token_enc="")
        db.add(account)
    else:
        user = account.user
    account.access_token_enc = encrypt_token(token.access_token)
    account.token_expires_at = token.expires_at
    update_profile(account, profile)
    db.flush()
    queue.enqueue(db, "sync_account", {"ig_account_id": str(account.id)}, dedupe_key=f"sync:{account.id}")
    db.commit()

    response = RedirectResponse(f"{front}/dashboard", status_code=302)
    response.delete_cookie(STATE_COOKIE)
    _set_session(response, user)
    return response


@router.post("/demo")
def demo_login(response: Response, db: Session = Depends(get_db)):
    """Creates (or reuses) the shared demo creator. Disabled unless DEMO_MODE=true."""
    if not get_settings().demo_mode:
        raise HTTPException(404, "Not found")
    ig_user_id = f"{DEMO_PREFIX}0001"
    account = db.scalar(select(IgAccount).where(IgAccount.ig_user_id == ig_user_id))
    if account is None:
        client = DemoInstagramClient(ig_user_id)
        user = User(display_name="Demo creator", plan="founding", is_demo=True)
        db.add(user)
        db.flush()
        account = IgAccount(user_id=user.id, ig_user_id=ig_user_id, username="", access_token_enc=encrypt_token("demo"))
        update_profile(account, client.get_profile())
        db.add(account)
        db.flush()
        queue.enqueue(db, "sync_account", {"ig_account_id": str(account.id)}, dedupe_key=f"sync:{account.id}")
    db.commit()
    _set_session(response, account.user)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    account = user.ig_account
    return {
        "user": {"id": str(user.id), "display_name": user.display_name, "is_demo": user.is_demo},
        "account": None if account is None else {
            "username": account.username,
            "profile_picture_url": account.profile_picture_url,
            "followers_count": account.followers_count,
            "last_synced_at": account.last_synced_at.isoformat() if account.last_synced_at else None,
        },
        "usage": reports_svc.usage(db, user),
    }


@router.delete("/me")
def delete_me(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Deletes the user and every row that belongs to them (cascades)."""
    db.delete(user)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
