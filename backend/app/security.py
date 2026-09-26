import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet

from app.config import get_settings

SESSION_COOKIE = "sid"
STATE_COOKIE = "oauth_state"
SESSION_DAYS = 30


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        # Dev fallback: derive a stable key from SECRET_KEY. Production must set
        # TOKEN_ENCRYPTION_KEY explicitly (checked at startup in main.py).
        digest = hashlib.sha256(get_settings().secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(token_enc: str) -> str:
    return _fernet().decrypt(token_enc.encode()).decode()


def create_session_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(days=SESSION_DAYS)}
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


def read_session_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_state() -> str:
    return secrets.token_urlsafe(24)


def new_slug() -> str:
    # 10 url-safe chars (~60 bits): unguessable share links.
    return secrets.token_urlsafe(8)[:10]


def hash_comment_id(comment_id: str) -> str:
    salt = get_settings().comment_hash_salt.encode()
    return hmac.new(salt, comment_id.encode(), hashlib.sha256).hexdigest()[:32]


def parse_meta_signed_request(signed_request: str) -> dict | None:
    """Verify a Meta signed_request (data deletion / deauthorize callbacks)."""
    try:
        encoded_sig, payload = signed_request.split(".", 1)
        sig = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    secret = get_settings().instagram_app_secret.encode()
    expected = hmac.new(secret, payload.encode(), hashlib.sha256).digest()
    if not secret or not hmac.compare_digest(sig, expected):
        return None
    return data
