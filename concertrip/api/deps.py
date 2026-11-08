from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from concertrip.api.services.auth import AuthError, decode_access_token
from concertrip.db import SessionLocal
from concertrip.models import User


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except AuthError as error:
        raise credentials_error from error

    user = session.get(User, user_id)
    if user is None or not user.is_active or not user.is_verified:
        raise credentials_error
    return user
