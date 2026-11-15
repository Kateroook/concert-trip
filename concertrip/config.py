"""Налаштування застосунку: читаються з оточення або з файлу .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Проста заміна python-dotenv, щоб не тягнути залежність заради трьох рядків."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _csv_tuple(name: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in os.getenv(name, "").split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'concertrip.db'}")
    ticketmaster_api_key: str = os.getenv("TICKETMASTER_API_KEY", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
    spotify_client_id: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    spotify_client_secret: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    spotify_redirect_uri: str = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8501/")
    seed_csv: Path = Path(os.getenv("SEED_CSV", ROOT / "data" / "seed_events.csv"))
    countries: tuple[str, ...] = tuple(
        part.strip() for part in os.getenv("COUNTRIES", "GB,NL,DE,FR,PL").split(",") if part.strip()
    )
    jsonld_urls: tuple[str, ...] = _csv_tuple("JSONLD_URLS")
    http_user_agent: str = os.getenv(
        "HTTP_USER_AGENT",
        "ConcerTrip/0.1 (educational; fan ticket alerts)",
    )
    request_delay_seconds: float = _float_env("REQUEST_DELAY_SECONDS", 1.0)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def has_ticketmaster(self) -> bool:
        return bool(self.ticketmaster_api_key)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def has_spotify(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
