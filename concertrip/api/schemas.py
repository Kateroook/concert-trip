from datetime import date, datetime
from typing import Literal, Optional
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
    eventDate: Optional[date] = None
    onSaleDate: Optional[date] = None
    dateStatus: str = "confirmed"
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


class SpotifyAuthorizeResponse(BaseModel):
    authorize_url: str = Field(alias="authorizeUrl")
    model_config = ConfigDict(populate_by_name=True)


class SpotifyStatusResponse(BaseModel):
    connected: bool
    provider_account_id: Optional[str] = Field(default=None, alias="providerAccountId")
    last_synced_at: Optional[datetime] = Field(default=None, alias="lastSyncedAt")
    preference_count: int = Field(alias="preferenceCount")
    model_config = ConfigDict(populate_by_name=True)


class SpotifySyncResponse(BaseModel):
    imported: int
    status: SpotifyStatusResponse


class MusicPreferenceResponse(BaseModel):
    provider: str
    provider_artist_id: str = Field(alias="providerArtistId")
    artist_name: str = Field(alias="artistName")
    source: str
    time_range: str = Field(alias="timeRange")
    weight: float
    genres: list[str]
    model_config = ConfigDict(populate_by_name=True)


class RecommendationItem(BaseModel):
    event: EventItem
    score: float
    reasons: list[str]


class RecommendationsResponse(BaseModel):
    items: list[RecommendationItem]
    model: str


class ArtistResponse(BaseModel):
    id: UUID
    name: str
    followed: bool
    priority: float


class FollowArtistRequest(BaseModel):
    priority: float = Field(default=3.0, ge=0.0, le=10.0)


class EventActionRequest(BaseModel):
    action: Literal["viewed", "saved", "dismissed", "clicked_ticket"]
