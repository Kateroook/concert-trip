"""Доставка черги в Telegram і команди бота."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from concertrip.config import settings
from concertrip.db import session_scope
from concertrip.models import Alert, Event, WatchItem
from concertrip.notify.messages import headline
from concertrip.prefs import get_pref, is_muted, quiet_hours, set_pref

MAX_ATTEMPTS = 3


def in_quiet_hours(now: datetime, start: int, end: int) -> bool:
    if start == end:
        return False
    hour = now.hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def deliver_queued(session: Session, sender, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if is_muted(session):
        return 0
    start, end = quiet_hours(session)
    if in_quiet_hours(now, start, end):
        return 0
    chat_id = get_pref(session, "telegram_chat_id", "")
    if not chat_id:
        return 0
    sent = 0
    queued = session.scalars(
        select(Alert).where(Alert.status == "queued", Alert.attempts < MAX_ATTEMPTS)
    ).all()
    for alert in queued:
        try:
            sender(chat_id, alert.body)
        except Exception as exc:
            alert.attempts += 1
            alert.last_error = str(exc)[:400]
            if alert.attempts >= MAX_ATTEMPTS:
                alert.status = "failed"
            continue
        alert.status = "sent"
        alert.sent_at = now
        sent += 1
    session.commit()
    return sent


def send_telegram(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("немає токена Telegram")

    async def _go() -> None:
        from telegram import Bot

        bot = Bot(settings.telegram_bot_token)
        try:
            await bot.send_message(chat_id=int(chat_id), text=text)
        finally:
            await bot.shutdown()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_go())
        return
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(_go())).result()


def send_test_message(chat_id: str) -> bool:
    """Надіслати тестове повідомлення. Повертає True якщо вдалося."""
    if not settings.telegram_bot_token or not chat_id:
        return False
    try:
        send_telegram(chat_id, "ConcerTrip на зв'язку \U0001f39f\ufe0f Сповіщення налаштовано правильно.")
        return True
    except Exception:
        return False


def _watch_text(session: Session) -> str:
    items = session.scalars(select(WatchItem)).all()
    if not items:
        return "Список порожній. Додай артиста в інтерфейсі."
    names = [item.artist.name for item in items if item.artist]
    marked = session.scalars(select(Event.id)).all()
    return "Стежиш за: " + ", ".join(names)


async def _start(update, context) -> None:
    chat_id = str(update.effective_chat.id)
    with session_scope() as session:
        set_pref(session, "telegram_chat_id", chat_id)
        set_pref(session, "muted", "0")
    await update.message.reply_text(
        "ConcerTrip на зв’язку. Напишу, коли з’являться квитки на позначену подію. /mute вимикає доставку, /watch показує список."
    )


async def _watch(update, context) -> None:
    with session_scope() as session:
        text = _watch_text(session)
    await update.message.reply_text(text)


async def _mute(update, context) -> None:
    with session_scope() as session:
        set_pref(session, "muted", "1")
    await update.message.reply_text("Сповіщення вимкнено. /unmute увімкне їх знову.")


async def _unmute(update, context) -> None:
    with session_scope() as session:
        set_pref(session, "muted", "0")
    await update.message.reply_text("Сповіщення знову ввімкнено.")


def main() -> None:
    if not settings.telegram_bot_token:
        print("Немає TELEGRAM_BOT_TOKEN. Інтерфейс працює без бота, доставка піде в чергу.")
        return
    from telegram.ext import Application, CommandHandler

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", _start))
    application.add_handler(CommandHandler("watch", _watch))
    application.add_handler(CommandHandler("mute", _mute))
    application.add_handler(CommandHandler("unmute", _unmute))
    application.run_polling(stop_signals=None)


if __name__ == "__main__":
    main()
