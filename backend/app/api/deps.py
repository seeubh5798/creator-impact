from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import IgAccount, User
from app.security import SESSION_COOKIE, read_session_token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def current_account(user: User = Depends(current_user)) -> IgAccount:
    if user.ig_account is None:
        raise HTTPException(status_code=409, detail="No Instagram account connected")
    return user.ig_account
