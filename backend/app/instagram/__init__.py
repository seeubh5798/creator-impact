from app.instagram.client import GraphInstagramClient, InstagramClient, InstagramError
from app.instagram.demo import DemoInstagramClient
from app.models import IgAccount
from app.security import decrypt_token

DEMO_PREFIX = "demo-"


def is_demo_account(account: IgAccount) -> bool:
    return account.ig_user_id.startswith(DEMO_PREFIX)


def client_for(account: IgAccount) -> InstagramClient:
    if is_demo_account(account):
        return DemoInstagramClient(account.ig_user_id)
    return GraphInstagramClient(decrypt_token(account.access_token_enc))


__all__ = ["InstagramClient", "InstagramError", "client_for", "is_demo_account", "DEMO_PREFIX"]
