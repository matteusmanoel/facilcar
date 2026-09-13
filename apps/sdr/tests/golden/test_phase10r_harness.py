"""Phase 10R harness checks — skip baseline and gitignored gate output."""

from __future__ import annotations

import json
from pathlib import Path

_PHASE10R = Path(__file__).parent / "phase10r"
_SKIPS = json.loads((_PHASE10R / "skips.json").read_text(encoding="utf-8"))


def test_phase10r_skip_count_unchanged_environmental() -> None:
    """Baseline 64f1318: 8 skips. After Frente E: still 8 (none replaced)."""
    assert _SKIPS["count_before"] == 8
    assert _SKIPS["count_after"] == 8
    assert _SKIPS["replaced"] == []
    assert len(_SKIPS["skips"]) == 8
    allowed = {
        "JUSTIFIED_ENVIRONMENTAL",
        "REPLACEABLE_WITH_FAKE",
        "UNACCEPTABLE_COVERAGE_GAP",
        "PREEXISTING_UNRELATED",
    }
    classes = {row["classification"] for row in _SKIPS["skips"]}
    assert classes <= allowed
    assert "UNACCEPTABLE_COVERAGE_GAP" not in classes
    assert "REPLACEABLE_WITH_FAKE" not in classes


def test_gate_phase10r_output_dir_is_gitignored() -> None:
    from sdr.gate_phase10r import OUT_DIR, ROOT

    assert OUT_DIR == ROOT / ".gate" / "phase10r"
    gitignore = ROOT.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".gate/" in gitignore
