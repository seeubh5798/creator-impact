"""Instagram API with Instagram Login (graph.instagram.com).

Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login
Scopes used: instagram_business_basic, instagram_business_manage_comments,
instagram_business_manage_insights.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlencode

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

SCOPES = [
    "instagram_business_basic",
    "instagram_business_manage_comments",
    "instagram_business_manage_insights",
]
INSIGHT_METRICS = ["reach", "views", "likes", "comments", "saved", "shares"]
METRIC_ALIASES = {"saved": "saves"}


class InstagramError(Exception):
    def __init__(self, message: str, status: int | None = None, code: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code

    @property
    def is_auth_error(self) -> bool:
        return self.code == 190 or self.status == 401


class InstagramClient(Protocol):
    def get_profile(self) -> dict: ...
    def list_media(self, limit: int = 50) -> list[dict]: ...
    def get_media_insights(self, media_id: str) -> dict: ...
    def list_comments(self, media_id: str, max_comments: int) -> list[dict]: ...


# ------------------------------------------------------------------ OAuth


def authorize_url(state: str) -> str:
    s = get_settings()
    params = {
        "client_id": s.instagram_app_id,
        "redirect_uri": s.oauth_redirect_uri,
        "response_type": "code",
        "scope": ",".join(SCOPES),
        "state": state,
        "enable_fb_login": "0",
        "force_authentication": "1",
    }
    return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"


@dataclass
class TokenResult:
    access_token: str
    user_id: str | None
    expires_at: datetime | None


def exchange_code(code: str) -> TokenResult:
    """Code -> short-lived token -> long-lived (60 day) token."""
    s = get_settings()
    resp = httpx.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": s.instagram_app_id,
            "client_secret": s.instagram_app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": s.oauth_redirect_uri,
            "code": code.removesuffix("#_"),
        },
        timeout=20,
    )
    body = _json_or_raise(resp)
    if "data" in body and body["data"]:  # newer response shape
        body = body["data"][0]
    short_token = body["access_token"]
    user_id = str(body.get("user_id")) if body.get("user_id") else None

    resp = httpx.get(
        "https://graph.instagram.com/access_token",
        params={"grant_type": "ig_exchange_token", "client_secret": s.instagram_app_secret, "access_token": short_token},
        timeout=20,
    )
    long = _json_or_raise(resp)
    return TokenResult(long["access_token"], user_id, _expiry(long.get("expires_in")))


def refresh_long_lived_token(token: str) -> TokenResult:
    resp = httpx.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=20,
    )
    body = _json_or_raise(resp)
    return TokenResult(body["access_token"], None, _expiry(body.get("expires_in")))


def _expiry(expires_in) -> datetime | None:
    if not expires_in:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))


def _json_or_raise(resp: httpx.Response) -> dict:
    try:
        body = resp.json()
    except ValueError:
        raise InstagramError(f"Non-JSON response ({resp.status_code})", resp.status_code) from None
    if resp.status_code >= 400 or "error" in body:
        err = body.get("error", {}) if isinstance(body.get("error"), dict) else {}
        msg = err.get("message") or body.get("error_message") or str(body)[:300]
        raise InstagramError(msg, resp.status_code, err.get("code"))
    return body


# ------------------------------------------------------------------ Graph


class GraphInstagramClient:
    def __init__(self, access_token: str, http: httpx.Client | None = None):
        s = get_settings()
        self.token = access_token
        self.base = f"https://graph.instagram.com/{s.graph_api_version}"
        self.http = http or httpx.Client(timeout=30)

    def _get(self, path_or_url: str, params: dict | None = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base}/{path_or_url.lstrip('/')}"
        params = dict(params or {})
        if "access_token=" not in url:
            params["access_token"] = self.token
        for attempt in range(4):
            # httpx replaces a URL's query string when params is passed, which would
            # drop the cursor from paging.next URLs, so only pass params when needed.
            resp = self.http.get(url, params=params or None)
            if resp.status_code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2**attempt)
                continue
            return _json_or_raise(resp)
        raise InstagramError("unreachable")

    def _paginate(self, path: str, params: dict, limit: int) -> list[dict]:
        items: list[dict] = []
        body = self._get(path, params)
        while True:
            items.extend(body.get("data", []))
            next_url = body.get("paging", {}).get("next")
            if len(items) >= limit or not next_url:
                return items[:limit]
            body = self._get(next_url)

    def get_profile(self) -> dict:
        return self._get(
            "me",
            {"fields": "user_id,username,account_type,profile_picture_url,followers_count,media_count"},
        )

    def list_media(self, limit: int = 50) -> list[dict]:
        fields = "id,caption,media_type,media_product_type,permalink,thumbnail_url,media_url,timestamp,like_count,comments_count"
        return self._paginate("me/media", {"fields": fields, "limit": 50}, limit)

    def get_media_insights(self, media_id: str) -> dict:
        """Returns {reach, views, likes, comments, saves, shares}; unsupported metrics are None.

        Metric support differs by media type, and one unsupported metric fails the
        whole request, so on error we fall back to fetching metrics one by one.
        """
        out: dict[str, int | None] = {METRIC_ALIASES.get(m, m): None for m in INSIGHT_METRICS}
        try:
            body = self._get(f"{media_id}/insights", {"metric": ",".join(INSIGHT_METRICS)})
            self._merge_insights(out, body)
        except InstagramError as e:
            if e.is_auth_error:
                raise
            for metric in INSIGHT_METRICS:
                try:
                    self._merge_insights(out, self._get(f"{media_id}/insights", {"metric": metric}))
                except InstagramError as inner:
                    if inner.is_auth_error:
                        raise
                    log.info("metric %s unavailable for %s: %s", metric, media_id, inner)
        return out

    @staticmethod
    def _merge_insights(out: dict, body: dict) -> None:
        for item in body.get("data", []):
            name = METRIC_ALIASES.get(item.get("name"), item.get("name"))
            values = item.get("values") or [{}]
            value = item.get("total_value", {}).get("value", values[0].get("value"))
            if name in out and isinstance(value, int):
                out[name] = value

    def list_comments(self, media_id: str, max_comments: int) -> list[dict]:
        fields = "id,text,timestamp,username,like_count,replies{id,text,timestamp,username,like_count}"
        top = self._paginate(f"{media_id}/comments", {"fields": fields, "limit": 50}, max_comments)
        flat: list[dict] = []
        for c in top:
            flat.append(c)
            flat.extend(c.get("replies", {}).get("data", []))
        return flat[:max_comments]
