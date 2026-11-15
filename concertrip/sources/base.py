"""Протокол джерела: fetch повертає RawEvent і нічого не пише в базу."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from concertrip.domain import RawEvent


class Source(Protocol):
    source_id: str

    def fetch(self, since: date) -> list[RawEvent]: ...
