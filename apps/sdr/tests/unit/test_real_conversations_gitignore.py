"""Phase 13A — shared ignore for local conversation dumps. Does not read contents."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".gitignore").is_file() and (parent / "apps" / "sdr").is_dir():
            return parent
    raise AssertionError("repository root with .gitignore not found")


def test_real_conversations_is_listed_in_versioned_gitignore() -> None:
    gitignore = (_repo_root() / ".gitignore").read_text(encoding="utf-8")
    assert "apps/sdr/real_conversations/" in gitignore


def test_git_check_ignore_covers_nested_dump_paths() -> None:
    root = _repo_root()
    samples = [
        "apps/sdr/real_conversations/secret.bin",
        "apps/sdr/real_conversations/Artifacts/trace.json",
        "apps/sdr/real_conversations/export.opus",
        "apps/sdr/real_conversations/cnh.pdf",
    ]
    for rel in samples:
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"expected ignore for {rel}"


def test_real_conversations_is_not_tracked() -> None:
    root = _repo_root()
    listed = subprocess.run(
        ["git", "ls-files", "apps/sdr/real_conversations"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert listed.stdout.strip() == ""
