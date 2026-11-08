from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


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
