from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from concertrip.api.deps import get_current_user, get_db
from concertrip.api.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from concertrip.api.services.auth import (
    AuthError,
    authenticate_user,
    issue_tokens,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_email,
)
from concertrip.config import settings
from concertrip.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, isVerified=user.is_verified)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: Session = Depends(get_db)) -> RegisterResponse:
    try:
        user, verification_token = register_user(session, str(payload.email), payload.password)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return RegisterResponse(
        user=user_response(user),
        message="Registration successful. Verify your email before logging in.",
        verificationToken=verification_token if settings.auth_dev_mode else None,
    )


@router.post("/verify-email", response_model=UserResponse)
def verify(payload: VerifyEmailRequest, session: Session = Depends(get_db)) -> UserResponse:
    try:
        user = verify_email(session, payload.token)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return user_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = authenticate_user(session, str(payload.email), payload.password)
        access_token, refresh_token = issue_tokens(session, user, payload.device_name)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    return TokenResponse(accessToken=access_token, refreshToken=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, session: Session = Depends(get_db)) -> TokenResponse:
    try:
        _, access_token, refresh_token = rotate_refresh_token(session, payload.refresh_token)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    return TokenResponse(accessToken=access_token, refreshToken=refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, session: Session = Depends(get_db)) -> MessageResponse:
    revoke_refresh_token(session, payload.refresh_token)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return user_response(current_user)
