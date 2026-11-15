"""Реєстр джерел. Нове джерело — ще один запис, не нова гілка коду."""

from __future__ import annotations

from concertrip.sources.base import Source
from concertrip.sources.jsonld import JsonLdSource
from concertrip.sources.local_parser import SiteRulesSource
from concertrip.sources.seed import SeedSource
from concertrip.sources.ticketmaster import TicketmasterSource


def local_sources() -> list[Source]:
    return [SeedSource(), JsonLdSource(urls=[]), SiteRulesSource()]


def all_sources() -> list[Source]:
    return [SeedSource(), JsonLdSource(), SiteRulesSource(), TicketmasterSource()]
