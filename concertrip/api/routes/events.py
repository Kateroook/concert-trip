from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from concertrip.api.deps import get_db
from concertrip.api.schemas import EventItem, EventsResponse
from concertrip.api.services.events import list_events

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("", response_model=EventsResponse)
def get_events(
    q: Optional[str] = Query(default=None, max_length=100),
    country: Optional[str] = Query(default=None, min_length=2, max_length=2),
    status: Optional[str] = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> EventsResponse:
    items, total = list_events(
        session,
        query=q,
        country=country,
        status=status,
        page=page,
        page_size=page_size,
    )
    return EventsResponse(items=items, total=total, page=page, pageSize=page_size)
