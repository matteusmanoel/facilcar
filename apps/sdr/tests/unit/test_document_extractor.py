"""Unit tests for document extractor + retention helpers (mocked OpenAI)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sdr.config import get_settings
from sdr.infrastructure.document_repository import (
    RETENTION_DAYS_180,
    RETENTION_PERMANENT,
    expires_at_for_policy,
    retention_policy_for_lead_status,
)
from sdr.media.document_extractor import (
    ExtractedDocument,
    check_extraction_conflicts,
    extract_document,
)
from sdr.media.processor import process_media


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _vision_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = MagicMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
                )
            ]
        )
    )
    return client


@pytest.mark.asyncio
async def test_cnh_extraction_fields() -> None:
    client = _vision_client(
        {
            "name": "João Souza",
            "cpf": "529.982.247-25",
            "birth_date": "1988-05-20",
            "birth_city": "CASCAVEL",
            "birth_state": "PR",
            "plate": None,
            "document_type": "CNH",
        }
    )
    extracted, conflict = await extract_document(
        b"fake-cnh-bytes",
        mime_type="image/jpeg",
        client=client,
    )
    assert extracted.name == "João Souza"
    assert extracted.cpf == "52998224725"
    assert extracted.birth_date == "20/05/1988"
    assert extracted.birth_city == "CASCAVEL"
    assert extracted.birth_state == "PR"
    assert extracted.document_type == "CNH"
    assert conflict.needs_confirmation is False
    assert conflict.action == "apply"


@pytest.mark.asyncio
async def test_conflict_asks_confirmation() -> None:
    """When text/state CPF ≠ document CPF → ask_confirmation, do not overwrite."""
    client = _vision_client(
        {
            "name": "Ana",
            "cpf": "22222222222",
            "birth_date": None,
            "plate": None,
            "document_type": "CNH",
        }
    )
    state_facts = {"cpf": "11111111111", "name": "Ana"}
    extracted, conflict = await extract_document(
        b"fake",
        state_facts=state_facts,
        client=client,
    )
    assert extracted.cpf == "22222222222"
    assert conflict.needs_confirmation is True
    assert conflict.action == "ask_confirmation"
    assert "cpf" in conflict.conflicting_fields
    # Must not overwrite state CPF
    assert conflict.merged_facts["cpf"] == "11111111111"


def test_conflict_helper_same_cpf_no_confirmation() -> None:
    state = {"cpf": "111.111.111-11"}
    extracted = ExtractedDocument(cpf="11111111111", document_type="CNH")
    result = check_extraction_conflicts(state, extracted)
    assert result.needs_confirmation is False
    assert result.action == "apply"
    assert result.merged_facts["cpf"] == "11111111111"


def test_conflict_helper_empty_state_applies() -> None:
    extracted = ExtractedDocument(cpf="12345678901", name="Bia", document_type="CNH")
    result = check_extraction_conflicts({}, extracted)
    assert result.needs_confirmation is False
    assert result.merged_facts["cpf"] == "12345678901"
    assert result.merged_facts["name"] == "Bia"


def test_retention_policy_days_180_default() -> None:
    assert retention_policy_for_lead_status(None) == RETENTION_DAYS_180
    assert retention_policy_for_lead_status("NEW") == RETENTION_DAYS_180
    assert retention_policy_for_lead_status("QUALIFIED") == RETENTION_DAYS_180
    assert retention_policy_for_lead_status("LOST") == RETENTION_DAYS_180


def test_retention_policy_permanent_when_won() -> None:
    assert retention_policy_for_lead_status("WON") == RETENTION_PERMANENT
    assert retention_policy_for_lead_status("won") == RETENTION_PERMANENT


def test_expires_at_helper_days_180_vs_permanent() -> None:
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    exp = expires_at_for_policy(RETENTION_DAYS_180, created_at=created)
    assert exp is not None
    assert (exp - created).days == 180
    assert expires_at_for_policy(RETENTION_PERMANENT, created_at=created) is None


@pytest.mark.asyncio
async def test_processor_propagates_conflict() -> None:
    client = _vision_client(
        {
            "name": None,
            "cpf": "99999999999",
            "birth_date": None,
            "plate": None,
            "document_type": "OTHER",
        }
    )
    result = await process_media(
        b"x",
        content_type="DOCUMENT",
        mime_type="image/png",
        state_facts={"cpf": "11111111111"},
        client=client,
    )
    assert result.conflict is not None
    assert result.conflict.needs_confirmation is True
    assert result.conflict.action == "ask_confirmation"


@pytest.mark.asyncio
async def test_pdf_is_rasterized_before_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vision only accepts image MIME types — PDFs must be rasterized first."""
    jpeg = b"\xff\xd8\xfffakejpeg"
    monkeypatch.setattr(
        "sdr.media.document_extractor.rasterize_pdf_first_page",
        lambda data, **kwargs: jpeg,
    )
    client = _vision_client(
        {
            "name": "Maria Silva",
            "cpf": "52998224725",
            "birth_date": "1990-01-01",
            "plate": None,
            "document_type": "CNH",
        }
    )
    extracted, _conflict = await extract_document(
        b"%PDF-fake",
        mime_type="application/pdf",
        client=client,
    )
    assert extracted.name == "Maria Silva"
    kwargs = client.chat.completions.create.call_args.kwargs
    content = kwargs["messages"][1]["content"]
    image_url = content[1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")
    assert "application/pdf" not in image_url
