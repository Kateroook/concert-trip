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


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'concertrip.db'}")
    ticketmaster_api_key: str = os.getenv("TICKETMASTER_API_KEY", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    seed_csv: Path = Path(os.getenv("SEED_CSV", ROOT / "data" / "seed_events.csv"))
    countries: tuple[str, ...] = tuple(os.getenv("COUNTRIES", "GB,NL,DE,FR,PL").split(","))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def has_ticketmaster(self) -> bool:
        return bool(self.ticketmaster_api_key)


settings = Settings()
