import base64
import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet

from gatelock.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int, role: str) -> str:
    s = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, s.jwt_secret, "HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def _fernet() -> Fernet:
    s = get_settings()
    key = s.pii_key or base64.urlsafe_b64encode(hashlib.sha256(s.jwt_secret.encode()).digest())
    return Fernet(key)


def encrypt_pii(value: str) -> bytes:
    return _fernet().encrypt(value.encode())


def decrypt_pii(token: bytes) -> str:
    return _fernet().decrypt(token).decode()


def mask_id(national_id: str) -> str:
    return "*" * max(len(national_id) - 3, 0) + national_id[-3:]
