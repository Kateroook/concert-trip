"""Планувальник: локальний збір, щогодинна перевірка, черга раз на дві хвилини."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from concertrip.availability import check_availability
from concertrip.collect import collect
from concertrip.config import settings
from concertrip.db import init_db, session_scope
from concertrip.notify.telegram_bot import deliver_queued, send_telegram

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def job_collect() -> None:
    try:
        init_db()
        with session_scope() as session:
            collect(session)
    except Exception:
        log.exception("збір не вдався")


def job_availability() -> None:
    try:
        init_db()
        with session_scope() as session:
            check_availability(session)
    except Exception:
        log.exception("перевірка статусу не вдалась")


def job_deliver() -> None:
    if not settings.has_telegram:
        return
    try:
        init_db()
        with session_scope() as session:
            deliver_queued(session, send_telegram)
    except Exception:
        log.exception("доставка не вдалась")


def ensure_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(job_collect, "interval", hours=6, id="collect", replace_existing=True)
    scheduler.add_job(job_availability, "interval", hours=1, id="availability", replace_existing=True)
    scheduler.add_job(job_deliver, "interval", minutes=2, id="deliver", replace_existing=True)
    scheduler.start()
    _scheduler = scheduler
    return scheduler
