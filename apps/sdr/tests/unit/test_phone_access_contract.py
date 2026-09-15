"""Shared phone-access contract vectors — Python consumer."""

from __future__ import annotations

import json
from pathlib import Path

from sdr.domain.phone_access import evaluate_phone_access, parse_allowlist

VECTORS_PATH = Path(__file__).resolve().parents[1] / "contracts" / "phone_access_vectors.json"


def test_phone_access_contract_vectors() -> None:
    payload = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    vectors = payload["vectors"]
    assert len(vectors) >= 15
    for vector in vectors:
        allowlist = parse_allowlist(vector["allowlist_raw"])
        decision = evaluate_phone_access(
            vector["phone"],
            environment=vector["environment"],
            policy=vector["policy"],
            allowlist=allowlist,
        )
        assert decision.allowed is vector["allowed"], vector["id"]
        assert decision.reason == vector["reason"], vector["id"]
        phone = vector["phone"]
        if phone and any(ch.isdigit() for ch in phone):
            assert phone not in decision.reason
