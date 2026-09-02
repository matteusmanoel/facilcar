"""Load the authoritative Supabase URL for integration tests only.

Does not print credentials. Skips the module when the URL is not the
authorized project (``oulknepjqhyiyjbiuqtg``).
"""

from __future__ import annotations

import os
from pathlib import Path

AUTHORITATIVE_REF = "oulknepjqhyiyjbiuqtg"


def _parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            out[key] = value
    return out


def authoritative_database_url() -> str | None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    parsed = _parse_dotenv(env_path)
    url = parsed.get("DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if AUTHORITATIVE_REF in url:
        return url
    return None


_URL = authoritative_database_url()
if _URL:
    os.environ["DATABASE_URL"] = _URL
    from sdr.config import get_settings

    get_settings.cache_clear()
