"""Phase 8 replay artifacts — identifiable run directories, never silent overwrite."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
GATE_ROOT = ROOT / ".gate" / "phase8"
TZ_BRT = ZoneInfo("America/Sao_Paulo")

HUMAN_RUBRIC_CRITERIA = [
    "Respondeu perguntas diretas",
    "Reconheceu fatos novos",
    "Próxima pergunta adequada",
    "Repetiu pergunta",
    "Número de ações por turno",
    "Rapport natural",
    "Soou como questionário",
    "Veículo correto",
    "Financiamento seguro",
    "Visita coerente",
    "Resumo útil",
    "CRM coerente",
]


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT.parent.parent,
            text=True,
        ).strip()
    except Exception:
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                text=True,
            ).strip()
        except Exception:
            return "unknown"


def new_run_id() -> str:
    now = datetime.now(TZ_BRT)
    return now.strftime("phase8-%Y%m%dT%H%M%S")


def restore_openai_key() -> bool:
    """Load OPENAI_API_KEY from apps/sdr/.env without printing it."""
    from sdr.config import get_settings

    get_settings.cache_clear()
    if (get_settings().openai_api_key or "").strip():
        return True
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return False
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        token = value.strip().strip("'").strip('"')
        if token:
            os.environ["OPENAI_API_KEY"] = token
            get_settings.cache_clear()
            return bool((get_settings().openai_api_key or "").strip())
    return False


def human_rubric_markdown(name: str) -> str:
    lines = [
        f"# Revisão humana — `{name}`",
        "",
        "Aprovação comercial: `PENDING_HUMAN_REVIEW`",
        "",
        "| Critério | Resultado |",
        "| --- | --- |",
    ]
    for criterion in HUMAN_RUBRIC_CRITERIA:
        lines.append(f"| {criterion} |  |")
    lines.append("| Aprovação comercial | PENDING_HUMAN_REVIEW |")
    lines.append("")
    return "\n".join(lines)


def write_meta(dest: Path, meta: dict[str, Any]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "run_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
