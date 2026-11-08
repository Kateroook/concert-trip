import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.config import settings
from concertrip.models import EmailVerificationToken, RefreshToken, User

logger = logging.getLogger(__name__)
password_hasher = PasswordHasher()


class AuthError(ValueError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_access_token(user_id: UUID) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access" or not payload.get("sub"):
            raise AuthError("Invalid access token")
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as error:
        raise AuthError("Invalid access token") from error


def _new_refresh_token(session: Session, user: User, device_name: Optional[str] = None) -> str:
    raw_token = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            user=user,
            token_hash=hash_token(raw_token),
            expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
            device_name=device_name,
        )
    )
    return raw_token


def _new_verification_token(session: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    session.add(
        EmailVerificationToken(
            user=user,
            token_hash=hash_token(raw_token),
            expires_at=_now() + timedelta(hours=settings.email_verification_expire_hours),
        )
    )
    return raw_token


def register_user(session: Session, email: str, password: str) -> tuple[User, str]:
    normalized_email = normalize_email(email)
    if session.scalar(select(User).where(User.email == normalized_email)) is not None:
        raise AuthError("Email is already registered")

    user = User(email=normalized_email, password_hash=hash_password(password))
    session.add(user)
    session.flush()
    verification_token = _new_verification_token(session, user)
    session.commit()
    session.refresh(user)
    if settings.auth_dev_mode:
        logger.info("Email verification token for %s: %s", user.email, verification_token)
    return user, verification_token


def verify_email(session: Session, raw_token: str) -> User:
    token = session.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(raw_token)
        )
    )
    if token is None or token.used_at is not None or _as_utc(token.expires_at) <= _now():
        raise AuthError("Verification token is invalid or expired")

    token.used_at = _now()
    token.user.is_verified = True
    session.commit()
    session.refresh(token.user)
    return token.user


def authenticate_user(session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("User is inactive")
    if not user.is_verified:
        raise AuthError("Email is not verified")
    return user


def issue_tokens(
    session: Session, user: User, device_name: Optional[str] = None
) -> tuple[str, str]:
    refresh_token = _new_refresh_token(session, user, device_name)
    access_token = create_access_token(user.id)
    session.commit()
    return access_token, refresh_token


def rotate_refresh_token(session: Session, raw_token: str) -> tuple[User, str, str]:
    stored = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    if stored is None or stored.revoked_at is not None or _as_utc(stored.expires_at) <= _now():
        raise AuthError("Refresh token is invalid or expired")
    if not stored.user.is_active or not stored.user.is_verified:
        raise AuthError("User cannot refresh this session")

    stored.revoked_at = _now()
    new_refresh_token = _new_refresh_token(session, stored.user, stored.device_name)
    access_token = create_access_token(stored.user.id)
    session.commit()
    return stored.user, access_token, new_refresh_token


def revoke_refresh_token(session: Session, raw_token: str) -> None:
    stored = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = _now()
        session.commit()
