from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class HealthResponse(BaseModel):
    status: str


class EventItem(BaseModel):
    id: UUID
    artist: str
    venue: str
    city: str
    country: str
    eventDate: date
    onSaleDate: Optional[date] = None
    ticketType: str
    status: str
    url: str


class EventsResponse(BaseModel):
    items: list[EventItem]
    total: int
    page: int
    pageSize: int


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device_name: Optional[str] = Field(default=None, max_length=120)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class UserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    email: EmailStr
    is_verified: bool = Field(alias="isVerified")


class RegisterResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user: UserResponse
    message: str
    verification_token: Optional[str] = Field(default=None, alias="verificationToken")


class TokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(default="bearer", alias="tokenType")


class MessageResponse(BaseModel):
    message: str
