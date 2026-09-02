"""Inbound document helpers — media ref + extracted text for Understanding."""

from __future__ import annotations

from sdr.application.inbound_document import document_inbound_text, media_ref_from_row
from sdr.media.document_extractor import ExtractedDocument


def test_media_ref_from_dict_and_json() -> None:
    ref = {"url": "https://example/media"}
    assert media_ref_from_row({"turnFactsJson": {"_sdr_media": ref}}) == ref
    assert media_ref_from_row({"turnFactsJson": '{"_sdr_media": {"id": "1"}}'}) == {"id": "1"}
    assert media_ref_from_row({"turnFactsJson": "{not-json"}) is None
    assert media_ref_from_row({}) is None


def test_document_inbound_text_from_extraction_and_caption() -> None:
    extracted = ExtractedDocument(
        name="Maria Silva",
        cpf="12345678901",
        document_type="CNH",
    )
    text = document_inbound_text(extracted, "segue minha cnh")
    assert "segue minha cnh" in text
    assert "Maria Silva" in text
    assert "12345678901" in text
    assert "CNH" in text


def test_document_inbound_text_empty_without_extraction_or_caption() -> None:
    assert document_inbound_text(None, "") == ""
    assert document_inbound_text(None, "   ") == ""
