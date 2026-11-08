from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.api.deps import get_current_user, get_db
from concertrip.api.schemas import (
    MessageResponse,
    MusicPreferenceResponse,
    SpotifyAuthorizeResponse,
    SpotifyStatusResponse,
    SpotifySyncResponse,
)
from concertrip.api.services.spotify import (
    SpotifyError,
    account_status,
    complete_authorization,
    create_authorize_url,
    disconnect,
    sync_preferences,
)
from concertrip.config import settings
from concertrip.models import MusicPreference, User

router = APIRouter(prefix="/api/v1/integrations/spotify", tags=["spotify"])
preferences_router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])


def _status_response(session: Session, user: User) -> SpotifyStatusResponse:
    return SpotifyStatusResponse(**account_status(session, user))


@router.get("/authorize", response_model=SpotifyAuthorizeResponse)
def authorize(
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db)
) -> SpotifyAuthorizeResponse:
    try:
        return SpotifyAuthorizeResponse(
            authorizeUrl=create_authorize_url(session, current_user)
        )
    except SpotifyError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


def _mobile_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(
        f"{settings.spotify_mobile_redirect_uri}?{urlencode(params)}", status_code=303
    )


@router.get("/callback")
def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return _mobile_redirect(connected="false", error="spotify_denied")
    if not code or not state:
        return _mobile_redirect(connected="false", error="missing_callback_params")
    try:
        complete_authorization(session, code, state)
    except SpotifyError:
        return _mobile_redirect(connected="false", error="spotify_authorization_failed")
    return _mobile_redirect(connected="true")


@router.get("/status", response_model=SpotifyStatusResponse)
def status_endpoint(
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db)
) -> SpotifyStatusResponse:
    return _status_response(session, current_user)


@router.post("/sync", response_model=SpotifySyncResponse)
def sync(
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db)
) -> SpotifySyncResponse:
    try:
        imported = sync_preferences(session, current_user)
    except SpotifyError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return SpotifySyncResponse(imported=imported, status=_status_response(session, current_user))


@router.delete("", response_model=MessageResponse)
def disconnect_endpoint(
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db)
) -> MessageResponse:
    disconnect(session, current_user)
    return MessageResponse(message="Spotify disconnected")


@preferences_router.get("/music", response_model=list[MusicPreferenceResponse])
def preferences_alias(
    current_user: User = Depends(get_current_user), session: Session = Depends(get_db)
) -> list[MusicPreferenceResponse]:
    preferences = session.scalars(
        select(MusicPreference)
        .where(MusicPreference.user_id == current_user.id)
        .order_by(MusicPreference.weight.desc())
    ).all()
    return [
        MusicPreferenceResponse(
            provider=preference.provider,
            providerArtistId=preference.provider_artist_id,
            artistName=preference.artist_name,
            source=preference.source,
            timeRange=preference.time_range,
            weight=float(preference.weight),
            genres=(preference.genres or {}).get("values", []),
        )
        for preference in preferences
    ]
