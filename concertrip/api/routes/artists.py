from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from concertrip.api.deps import get_current_user, get_db
from concertrip.api.schemas import ArtistResponse, FollowArtistRequest
from concertrip.models import Artist, User, UserArtistFollow

router = APIRouter(prefix="/api/v1/artists", tags=["artists"])


@router.get("", response_model=list[ArtistResponse])
def search_artists(
    q: str = Query(default="", max_length=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[ArtistResponse]:
    statement = select(Artist).order_by(Artist.name.asc()).limit(50)
    if q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Artist.name.ilike(pattern), Artist.normalized_name.ilike(pattern)))
    artists = session.scalars(statement).all()
    follows = {
        follow.artist_id: follow
        for follow in session.scalars(
            select(UserArtistFollow).where(UserArtistFollow.user_id == current_user.id)
        ).all()
    }
    return [
        ArtistResponse(
            id=artist.id,
            name=artist.name,
            followed=artist.id in follows and follows[artist.id].is_active,
            priority=float(follows[artist.id].priority) if artist.id in follows else 0.0,
        )
        for artist in artists
    ]


@router.post("/{artist_id}/follow", response_model=ArtistResponse)
def follow_artist(
    artist_id: UUID,
    payload: FollowArtistRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ArtistResponse:
    artist = session.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    follow = session.scalar(
        select(UserArtistFollow).where(
            UserArtistFollow.user_id == current_user.id,
            UserArtistFollow.artist_id == artist_id,
        )
    )
    if follow is None:
        follow = UserArtistFollow(user_id=current_user.id, artist_id=artist_id)
        session.add(follow)
    follow.priority = payload.priority
    follow.is_active = True
    session.commit()
    return ArtistResponse(id=artist.id, name=artist.name, followed=True, priority=payload.priority)


@router.delete("/{artist_id}/follow", response_model=ArtistResponse)
def unfollow_artist(
    artist_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ArtistResponse:
    artist = session.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    follow = session.scalar(
        select(UserArtistFollow).where(
            UserArtistFollow.user_id == current_user.id,
            UserArtistFollow.artist_id == artist_id,
        )
    )
    if follow:
        follow.is_active = False
        session.commit()
    return ArtistResponse(id=artist.id, name=artist.name, followed=False, priority=0.0)
