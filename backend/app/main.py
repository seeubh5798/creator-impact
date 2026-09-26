import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, meta, posts, reports
from app.config import get_settings
from app.db import SessionLocal


def _check_production_config() -> None:
    s = get_settings()
    if not s.is_production:
        return
    problems = []
    if s.secret_key.startswith("dev-"):
        problems.append("SECRET_KEY")
    if not s.token_encryption_key:
        problems.append("TOKEN_ENCRYPTION_KEY")
    if s.comment_hash_salt.startswith("dev-"):
        problems.append("COMMENT_HASH_SALT")
    if problems:
        raise RuntimeError(f"Set these env vars for production: {', '.join(problems)}")


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    _check_production_config()
    s = get_settings()
    app = FastAPI(title="Creator Impact API", version="0.1.0")
    # The Next.js app proxies /api/* here, so CORS is only needed for local tools.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[s.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (auth.router, posts.router, reports.router, meta.router):
        app.include_router(router)

    @app.get("/health")
    def health():
        with SessionLocal() as db:
            db.execute(text("select 1"))
        return {"ok": True, "demo_mode": s.demo_mode, "llm": bool(s.anthropic_api_key)}

    return app


app = create_app()
