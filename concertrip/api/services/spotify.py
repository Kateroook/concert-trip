import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlencode
from uuid import UUID

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from concertrip.config import settings
from concertrip.models import Artist, ExternalAccount, MusicPreference, SpotifyOAuthState, User

logger = logging.getLogger(__name__)
SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"


class SpotifyError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fernet() -> Fernet:
    if not settings.spotify_token_encryption_key:
        raise SpotifyError("SPOTIFY_TOKEN_ENCRYPTION_KEY is not configured")
    digest = hashlib.sha256(settings.spotify_token_encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise SpotifyError("Stored Spotify token cannot be decrypted") from error


def _hash_state(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _configured() -> None:
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        raise SpotifyError("Spotify client credentials are not configured")
    if not settings.spotify_token_encryption_key:
        raise SpotifyError("SPOTIFY_TOKEN_ENCRYPTION_KEY is not configured")


def create_authorize_url(session: Session, user: User) -> str:
    _configured()
    raw_state = secrets.token_urlsafe(32)
    session.add(
        SpotifyOAuthState(
            user_id=user.id,
            state_hash=_hash_state(raw_state),
            expires_at=_now() + timedelta(minutes=10),
        )
    )
    session.commit()
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": " ".join(settings.spotify_scopes),
        "state": raw_state,
        "show_dialog": "true",
    }
    return f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(params)}"


def _consume_state(session: Session, raw_state: str) -> User:
    state = session.scalar(
        select(SpotifyOAuthState).where(SpotifyOAuthState.state_hash == _hash_state(raw_state))
    )
    if state is None or state.used_at is not None or _as_utc(state.expires_at) <= _now():
        raise SpotifyError("Spotify OAuth state is invalid or expired")
    state.used_at = _now()
    session.commit()
    return session.get(User, state.user_id)


def _token_request(code: Optional[str] = None, refresh_token: Optional[str] = None) -> dict[str, Any]:
    _configured()
    data: dict[str, str] = {"grant_type": "authorization_code" if code else "refresh_token"}
    if code:
        data.update({"code": code, "redirect_uri": settings.spotify_redirect_uri})
    if refresh_token:
        data["refresh_token"] = refresh_token
    try:
        response = httpx.post(
            SPOTIFY_TOKEN_URL,
            data=data,
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
            timeout=20,
        )
    except httpx.RequestError as error:
        raise SpotifyError("Spotify token request failed") from error
    if response.status_code >= 400:
        raise SpotifyError(f"Spotify token request failed ({response.status_code})")
    return response.json()


def _save_account(
    session: Session,
    user: User,
    token_data: dict[str, Any],
    profile: dict[str, Any],
    existing: Optional[ExternalAccount] = None,
) -> ExternalAccount:
    account_id = profile.get("account_id") or profile.get("id")
    if not account_id:
        raise SpotifyError("Spotify profile has no account id")
    account = existing or session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user.id,
            ExternalAccount.provider == "spotify",
        )
    )
    if account is None:
        account = ExternalAccount(user_id=user.id, provider="spotify", provider_account_id=account_id)
        session.add(account)
    account.provider_account_id = account_id
    account.access_token_encrypted = _encrypt(token_data["access_token"])
    if token_data.get("refresh_token"):
        account.refresh_token_encrypted = _encrypt(token_data["refresh_token"])
    elif not account.refresh_token_encrypted:
        raise SpotifyError("Spotify did not return a refresh token")
    account.expires_at = _now() + timedelta(seconds=int(token_data.get("expires_in", 3600)))
    account.scopes = " ".join(settings.spotify_scopes)
    account.status = "connected"
    session.flush()
    return account


def complete_authorization(session: Session, code: str, raw_state: str) -> User:
    user = _consume_state(session, raw_state)
    if user is None:
        raise SpotifyError("OAuth state user no longer exists")
    token_data = _token_request(code=code)
    profile = _spotify_get(token_data["access_token"], "/me")
    _save_account(session, user, token_data, profile)
    session.commit()
    return user


def _refresh_account(session: Session, account: ExternalAccount) -> str:
    if _as_utc(account.expires_at) > _now() + timedelta(seconds=60):
        return _decrypt(account.access_token_encrypted)
    token_data = _token_request(refresh_token=_decrypt(account.refresh_token_encrypted))
    account.access_token_encrypted = _encrypt(token_data["access_token"])
    if token_data.get("refresh_token"):
        account.refresh_token_encrypted = _encrypt(token_data["refresh_token"])
    account.expires_at = _now() + timedelta(seconds=int(token_data.get("expires_in", 3600)))
    session.commit()
    return token_data["access_token"]


def _spotify_get(access_token: str, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    try:
        response = httpx.get(
            f"{SPOTIFY_API_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except httpx.RequestError as error:
        raise SpotifyError("Spotify API request failed") from error
    if response.status_code == 429:
        raise SpotifyError("Spotify rate limit exceeded")
    if response.status_code >= 400:
        raise SpotifyError(f"Spotify API request failed ({response.status_code})")
    return response.json()


def _get_or_create_artist(session: Session, name: str) -> Artist:
    normalized = " ".join(name.casefold().split())
    artist = session.scalar(select(Artist).where(Artist.normalized_name == normalized))
    if artist is None:
        artist = Artist(name=name, normalized_name=normalized)
        session.add(artist)
        session.flush()
    return artist


def _upsert_preference(
    session: Session,
    user: User,
    *,
    artist_data: dict[str, Any],
    source: str,
    time_range: str,
    weight: Decimal,
) -> None:
    provider_artist_id = str(artist_data.get("id") or "")
    name = str(artist_data.get("name") or "Unknown artist")
    if not provider_artist_id:
        return
    artist = _get_or_create_artist(session, name)
    preference = session.scalar(
        select(MusicPreference).where(
            MusicPreference.user_id == user.id,
            MusicPreference.provider == "spotify",
            MusicPreference.provider_artist_id == provider_artist_id,
            MusicPreference.source == source,
            MusicPreference.time_range == time_range,
        )
    )
    if preference is None:
        preference = MusicPreference(
            user_id=user.id,
            provider="spotify",
            provider_artist_id=provider_artist_id,
            artist_name=name,
            source=source,
            time_range=time_range,
            weight=weight,
        )
    preference.artist_id = artist.id
    preference.artist_name = name
    preference.weight = weight
    preference.genres = {"values": artist_data.get("genres", [])}
    session.add(preference)


def sync_preferences(session: Session, user: User) -> int:
    account = session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user.id,
            ExternalAccount.provider == "spotify",
        )
    )
    if account is None:
        raise SpotifyError("Spotify is not connected")
    access_token = _refresh_account(session, account)
    count = 0
    for time_range, multiplier in (("short_term", Decimal("0.8")), ("medium_term", Decimal("1.0")), ("long_term", Decimal("1.2"))):
        response = _spotify_get(
            access_token,
            "/me/top/artists",
            {"time_range": time_range, "limit": 50},
        )
        artists = response.get("items") or []
        for index, artist_data in enumerate(artists):
            weight = multiplier * Decimal(str(max(0.1, 1 - index / max(1, len(artists)))))
            _upsert_preference(
                session,
                user,
                artist_data=artist_data,
                source="top_artists",
                time_range=time_range,
                weight=weight,
            )
            count += 1

    recent = _spotify_get(access_token, "/me/player/recently-played", {"limit": 50})
    recent_artists: dict[str, dict[str, Any]] = {}
    for item in recent.get("items") or []:
        for artist_data in (item.get("track") or {}).get("artists") or []:
            if artist_data.get("id"):
                recent_artists[artist_data["id"]] = artist_data
    for artist_data in recent_artists.values():
        _upsert_preference(
            session,
            user,
            artist_data=artist_data,
            source="recently_played",
            time_range="recent",
            weight=Decimal("0.7"),
        )
        count += 1

    account.last_synced_at = _now()
    session.commit()
    return count


def account_status(session: Session, user: User) -> dict[str, Any]:
    account = session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user.id,
            ExternalAccount.provider == "spotify",
        )
    )
    preference_count = session.scalar(
        select(func.count(MusicPreference.id)).where(MusicPreference.user_id == user.id)
    ) or 0
    return {
        "connected": account is not None and account.status == "connected",
        "providerAccountId": account.provider_account_id if account else None,
        "lastSyncedAt": account.last_synced_at if account else None,
        "preferenceCount": preference_count,
    }


def disconnect(session: Session, user: User) -> None:
    account = session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user.id,
            ExternalAccount.provider == "spotify",
        )
    )
    if account:
        session.delete(account)
        session.commit()
