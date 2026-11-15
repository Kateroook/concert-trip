"""Запуск джерел і перший запис локальних подій."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from concertrip.db import init_db
from concertrip.ingest import ingest_events
from concertrip.models import SourceRun, utcnow
from concertrip.ranking.festival import recompute_festivals
from concertrip.sources.base import Source
from concertrip.sources.registry import all_sources, local_sources

log = logging.getLogger(__name__)


def collect(session: Session, sources: list[Source] | None = None) -> list[SourceRun]:
    runs: list[SourceRun] = []
    for source in sources or local_sources():
        run = SourceRun(source_id=source.source_id, started_at=utcnow(), events_found=0)
        try:
            raws = source.fetch(date.today())
            stats = ingest_events(session, raws)
            run.events_found = stats.upserted
            if stats.skipped:
                run.errors = f"пропущено {stats.skipped}"
        except Exception as exc:
            log.exception("джерело %s впало", source.source_id)
            run.errors = f"{type(exc).__name__}: {exc}"
        run.finished_at = utcnow()
        session.add(run)
        session.commit()
        runs.append(run)
    recompute_festivals(session)
    return runs


def bootstrap(session: Session) -> None:
    init_db()
    already = session.scalar(select(func.count()).select_from(SourceRun)) or 0
    if already:
        return
    collect(session, local_sources())


def collect_all(session: Session) -> list[SourceRun]:
    return collect(session, all_sources())
