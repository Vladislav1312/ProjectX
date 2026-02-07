from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    token: str
    db_path: str
    timezone: str


def load_settings() -> Settings:
    token = os.getenv("MARKOV_TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("MARKOV_TELEGRAM_TOKEN is required")
    db_path = os.getenv("MARKOV_DB_PATH", "markov.db")
    timezone = os.getenv("MARKOV_TIMEZONE", "Europe/Moscow")
    return Settings(token=token, db_path=db_path, timezone=timezone)
