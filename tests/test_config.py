"""Перевірка, що налаштування читаються й мають розумні значення за замовчуванням."""

from concertrip.config import settings


def test_defaults():
    assert settings.database_url.startswith("sqlite")
    assert "PL" in settings.countries
    assert settings.seed_csv.name.endswith(".csv")
