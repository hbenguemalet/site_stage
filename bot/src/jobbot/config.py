"""Chargement de la configuration : secrets (.env) + règles métier (config.yaml)."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def load(config_path: Path | None = None, env_path: Path | None = None) -> tuple[dict, dict]:
    load_dotenv(env_path or ROOT / ".env")
    with open(config_path or ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    keys = [
        "ADZUNA_APP_ID", "ADZUNA_APP_KEY",
        "IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD", "IMAP_FOLDER",
        "DISCORD_WEBHOOK_URL", "DISCORD_LOGS_WEBHOOK_URL",
        "NTFY_URL", "NTFY_TOPIC", "NTFY_TOKEN", "LBA_API_KEY",
    ]
    # + les webhooks / topics par profil (DISCORD_WEBHOOK_DEV, NTFY_TOPIC_…), nommés dans profiles.yaml
    keys += [k for k in os.environ if k.startswith(("DISCORD_", "NTFY_")) and k not in keys]
    env = {k: os.environ.get(k, "").strip() for k in keys}
    return cfg, env


def require(env: dict, *keys: str) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise SystemExit(f"Variables manquantes dans .env : {', '.join(missing)}")
