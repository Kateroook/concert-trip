"""Налаштування єдиного локального користувача."""

from __future__ import annotations

from sqlalchemy.orm import Session

from concertrip.models import AppSetting


def get_pref(session: Session, key: str, default: str = "") -> str:
    row = session.get(AppSetting, key)
    if row is None or row.value is None:
        return default
    return row.value


def set_pref(session: Session, key: str, value: str) -> None:
    row = session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    session.commit()


def origin_city(session: Session) -> str:
    return get_pref(session, "origin_city", "Kyiv") or "Kyiv"


def unwanted_genres(session: Session) -> set[str]:
    raw = get_pref(session, "unwanted_genres", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def set_unwanted_genres(session: Session, genres: list[str]) -> None:
    clean = sorted({g.strip().lower() for g in genres if g.strip()})
    set_pref(session, "unwanted_genres", ",".join(clean))


def quiet_hours(session: Session) -> tuple[int, int]:
    start = _hour(get_pref(session, "quiet_start", "23"), 23)
    end = _hour(get_pref(session, "quiet_end", "8"), 8)
    return start, end


def is_muted(session: Session) -> bool:
    return get_pref(session, "muted", "0") == "1"


def _hour(raw: str, default: int) -> int:
    try:
        value = int(raw)
    except ValueError:
        return default
    if 0 <= value <= 23:
        return value
    return default


def jsonld_urls(session: Session) -> list[str]:
    """URL-и сторінок із JSON-LD розміткою, збережені в базі."""
    raw = get_pref(session, "jsonld_urls", "")
    return [u.strip() for u in raw.split("\n") if u.strip().startswith("http")]


def set_jsonld_urls(session: Session, urls: list[str]) -> None:
    clean = [u.strip() for u in urls if u.strip().startswith("http")]
    set_pref(session, "jsonld_urls", "\n".join(clean))
