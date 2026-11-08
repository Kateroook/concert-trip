from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.api.deps import get_current_user, get_db
from concertrip.api.schemas import EventActionRequest, RecommendationsResponse
from concertrip.api.services.recommendations import get_recommendations
from concertrip.models import Event, User, UserEventAction

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])
actions_router = APIRouter(prefix="/api/v1/events", tags=["event-actions"])


@router.get("", response_model=RecommendationsResponse)
def recommendations(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> RecommendationsResponse:
    from concertrip.config import settings

    return RecommendationsResponse(
        items=get_recommendations(session, current_user, limit),
        model=settings.recommendation_model,
    )


@actions_router.post("/{event_id}/actions", status_code=204)
def event_action(
    event_id: UUID,
    payload: EventActionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    if session.get(Event, event_id) is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Event not found")
    action = session.scalar(
        select(UserEventAction).where(
            UserEventAction.user_id == current_user.id,
            UserEventAction.event_id == event_id,
            UserEventAction.action == payload.action,
        )
    )
    if action is None:
        session.add(UserEventAction(user_id=current_user.id, event_id=event_id, action=payload.action))
        session.commit()
