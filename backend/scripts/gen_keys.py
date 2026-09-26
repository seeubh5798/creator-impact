"""Print fresh secrets for .env. Usage: python scripts/gen_keys.py"""

import secrets

from cryptography.fernet import Fernet

print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
print(f"TOKEN_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
print(f"COMMENT_HASH_SALT={secrets.token_urlsafe(24)}")
