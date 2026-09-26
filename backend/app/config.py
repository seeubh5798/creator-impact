from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"  # development | production
    database_url: str = "postgresql+psycopg://postgres@127.0.0.1:54329/impact"

    # Where the Next.js app lives. The frontend proxies /api/* to this backend,
    # so cookies are first-party on the frontend domain.
    frontend_url: str = "http://localhost:3000"

    # Secrets
    secret_key: str = "dev-secret-change-me-this-is-not-a-real-key"
    token_encryption_key: str = ""  # Fernet key; generate with scripts/gen_keys.py
    comment_hash_salt: str = "dev-salt-change-me"

    # Instagram API with Instagram Login (Meta app)
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    graph_api_version: str = "v23.0"

    # Demo mode: fake Instagram data so the full flow works without Meta approval.
    demo_mode: bool = True

    # LLM. Without a key the rule-based classifier is used.
    anthropic_api_key: str = ""
    classify_model: str = "claude-haiku-4-5-20251001"
    summarize_model: str = "claude-sonnet-5"
    classify_batch_size: int = 100

    # Razorpay (Subscriptions). Create the plans in the Razorpay dashboard and paste their ids.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_plan_pro_monthly: str = ""
    razorpay_plan_pro_yearly: str = ""
    razorpay_plan_pro_plus_monthly: str = ""
    razorpay_plan_pro_plus_yearly: str = ""

    # Product rules
    free_reports_per_month: int = 3
    baseline_sample_size: int = 20
    raw_comment_retention_days: int = 30
    max_comments_per_post: int = 5000

    @property
    def billing_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{self.frontend_url.rstrip('/')}/api/auth/instagram/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
