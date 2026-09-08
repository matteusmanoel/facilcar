"""Phase 2 — commercial receipt vs internal document storage (no live I/O)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sdr.application.document_storage import (
    DocumentStorageService,
    StoreDocumentRequest,
)
from sdr.application.process_turn import process_turn
from sdr.domain.document_status import merge_document_status
from sdr.domain.document_storage import (
    STORAGE_PERMANENT_FAILURE,
    STORAGE_RETRYABLE_FAILURE,
    STORAGE_STORED,
    apply_commercial_document_receipt,
    build_document_storage_key,
    commercial_status_patch,
)
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus, make_text_inbound
from sdr.domain.inbound_batch import (
    InboundSegment,
    compose_inbound_turn,
    first_batch_partition,
)
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.understanding.response_composer import _document_received_bubbles


PRIVATE_BUCKET = "sdr-documents"
PUBLIC_BUCKET = "vehicle-images"


class FakeObjectStore:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.put_calls: list[str] = []
        self.head_calls: list[str] = []
        self.fail_buckets: set[str] = set()
        self.fail_next_puts: int = 0

    def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str | None = None) -> None:
        _ = content_type
        self.put_calls.append(bucket)
        if bucket in self.fail_buckets:
            raise RuntimeError(f"NoSuchBucket:{bucket}")
        if self.fail_next_puts > 0:
            self.fail_next_puts -= 1
            raise RuntimeError("ServiceUnavailable")
        self.objects[(bucket, key)] = body

    def head_object(self, *, bucket: str, key: str) -> dict | None:
        self.head_calls.append(f"{bucket}:{key}")
        data = self.objects.get((bucket, key))
        if data is None:
            return None
        return {"content_length": len(data)}


class InMemoryDocuments:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.fail_next_persist: int = 0
        self._seq = 0

    async def upsert_inbound(self, **fields) -> dict:
        if self.fail_next_persist > 0:
            self.fail_next_persist -= 1
            raise RuntimeError("unique_violation")
        conv = fields["conversation_id"]
        pid = fields["provider_message_id"]
        existing = next(
            (
                r
                for r in self.rows.values()
                if r.get("conversation_id") == conv and r.get("provider_message_id") == pid
            ),
            None,
        )
        if existing:
            existing.update(fields)
            return existing
        self._seq += 1
        doc_id = f"doc-{self._seq}"
        row = {"id": doc_id, **fields}
        self.rows[doc_id] = row
        return row

    async def get(self, document_id: str) -> dict | None:
        return self.rows.get(document_id)

    async def get_by_provider(self, conversation_id: str, provider_message_id: str) -> dict | None:
        return next(
            (
                r
                for r in self.rows.values()
                if r.get("conversation_id") == conversation_id
                and r.get("provider_message_id") == provider_message_id
            ),
            None,
        )


class InMemoryMessages:
    def __init__(self) -> None:
        self.keys: dict[str, str | None] = {}

    async def set_media_storage_key(self, message_id: str, key: str | None) -> None:
        self.keys[message_id] = key


def _settings(bucket: str = PRIVATE_BUCKET) -> SimpleNamespace:
    return SimpleNamespace(
        sdr_documents_bucket=bucket,
        sdr_document_storage_max_attempts=3,
    )


def _service(
    store: FakeObjectStore | None = None,
    docs: InMemoryDocuments | None = None,
    messages: InMemoryMessages | None = None,
    persist: InMemoryDocuments | None = None,
) -> tuple[DocumentStorageService, FakeObjectStore, InMemoryDocuments, InMemoryMessages]:
    store = store or FakeObjectStore()
    docs = persist or docs or InMemoryDocuments()
    messages = messages or InMemoryMessages()
    svc = DocumentStorageService(
        object_store=store,
        documents=docs,
        messages=messages,
        settings=_settings(),
    )
    return svc, store, docs, messages


def _request(**overrides) -> StoreDocumentRequest:
    data = overrides.pop("data", b"%PDF-synthetic-cnh%")
    fields = dict(
        data=data,
        mime_type="application/pdf",
        document_type="CNH",
        conversation_id="syn-conv-doc-1",
        message_id="syn-msg-doc-1",
        provider_message_id="syn-prov-doc-1",
        lead_id="syn-lead-1",
        extracted_json={"document_type": "CNH", "name": "Cliente Teste"},
        extraction_ok=True,
    )
    fields.update(overrides)
    return StoreDocumentRequest(**fields)


def test_storage_key_is_stable_and_has_no_pii() -> None:
    key = build_document_storage_key(
        conversation_id="syn-conv-doc-1",
        provider_message_id="syn-prov-doc-1",
        document_type="CNH",
        content_hash="abc123def456",
        extension="pdf",
    )
    again = build_document_storage_key(
        conversation_id="syn-conv-doc-1",
        provider_message_id="syn-prov-doc-1",
        document_type="CNH",
        content_hash="abc123def456",
        extension="pdf",
    )
    assert key == again
    assert "syn-conv-doc-1" in key
    assert "syn-prov-doc-1" in key
    assert key.endswith(".pdf")
    lowered = key.lower()
    assert "cpf" not in lowered
    assert "5511" not in key
    assert "cliente" not in lowered


def test_commercial_status_is_granular() -> None:
    assert commercial_status_patch("CNH") == {"cnh": "received"}
    assert commercial_status_patch("INCOME_PROOF") == {"proof_of_income": "received"}
    assert commercial_status_patch("RESIDENCE_PROOF") == {"proof_of_residence": "received"}
    assert commercial_status_patch("OTHER") == {}
    assert commercial_status_patch("CRLV") == {}
    assert commercial_status_patch(None) == {}
    merged = merge_document_status({"cnh": "received"}, commercial_status_patch("INCOME_PROOF"))
    assert merged["cnh"] == "received"
    assert merged["proof_of_income"] == "received"
    assert merged["proof_of_residence"] == "missing"


def test_cnh_ack_is_neutral_receipt_not_storage_claim() -> None:
    bubbles = _document_received_bubbles(
        {"document_kind": "CNH", "customer_name": "Mateus Ferreira"},
        "pt-BR",
    )
    joined = " ".join(bubbles)
    assert "Recebi sua CNH" in joined
    assert "Mateus" in joined
    lowered = joined.lower()
    assert "salva no sistema" not in lowered
    assert "salva na sua ficha" not in lowered
    assert "disponível para o vendedor" not in lowered
    assert "bucket" not in lowered
    assert "storage" not in lowered
    assert "reenvio" not in lowered


@pytest.mark.asyncio
async def test_1_successful_upload_stores_privately() -> None:
    svc, store, docs, messages = _service()
    out = await svc.store_inbound_document(_request())
    assert out.commercial_received is True
    assert out.customer_error_exposed is False
    assert out.storage_status == STORAGE_STORED
    assert out.storage_bucket == PRIVATE_BUCKET
    assert out.storage_key
    assert out.media_storage_key == out.storage_key
    assert messages.keys["syn-msg-doc-1"] == out.storage_key
    assert PUBLIC_BUCKET not in store.put_calls
    assert store.put_calls == [PRIVATE_BUCKET]
    assert len(docs.rows) == 1
    row = next(iter(docs.rows.values()))
    assert row["storage_status"] == STORAGE_STORED
    assert row["storage_bucket"] == PRIVATE_BUCKET


@pytest.mark.asyncio
async def test_2_upload_failure_does_not_change_customer_path() -> None:
    store = FakeObjectStore()
    store.fail_buckets.add(PRIVATE_BUCKET)
    svc, store, docs, messages = _service(store=store)
    out = await svc.store_inbound_document(_request())
    assert out.commercial_received is True
    assert out.customer_error_exposed is False
    assert out.storage_status == STORAGE_RETRYABLE_FAILURE
    assert out.media_storage_key is None
    assert "syn-msg-doc-1" not in messages.keys or messages.keys.get("syn-msg-doc-1") is None
    assert out.sanitized_error
    assert "ak" not in (out.sanitized_error or "")
    assert PUBLIC_BUCKET not in store.put_calls


@pytest.mark.asyncio
async def test_3_never_falls_back_to_vehicle_images() -> None:
    store = FakeObjectStore()
    store.fail_buckets.add(PRIVATE_BUCKET)
    svc, store, *_ = _service(store=store)
    out = await svc.store_inbound_document(_request())
    assert PUBLIC_BUCKET not in store.put_calls
    assert all(b == PRIVATE_BUCKET for b in store.put_calls)
    assert out.storage_bucket in {PRIVATE_BUCKET, None} or out.storage_bucket == PRIVATE_BUCKET
    assert not any(k[0] == PUBLIC_BUCKET for k in store.objects)


@pytest.mark.asyncio
async def test_4_retry_is_idempotent() -> None:
    store = FakeObjectStore()
    store.fail_next_puts = 1
    svc, store, docs, messages = _service(store=store)
    first = await svc.store_inbound_document(_request())
    assert first.storage_status == STORAGE_RETRYABLE_FAILURE
    assert first.media_storage_key is None
    second = await svc.store_inbound_document(_request())
    assert second.storage_status == STORAGE_STORED
    assert second.storage_key == second.media_storage_key
    assert len(docs.rows) == 1
    assert len(store.objects) == 1
    assert messages.keys["syn-msg-doc-1"] == second.storage_key
    # First failure + successful put. No extra object on the second call if head hits.
    assert list(store.objects)[0][0] == PRIVATE_BUCKET


@pytest.mark.asyncio
async def test_5_upload_ok_metadata_fail_reconciles_without_duplicate() -> None:
    docs = InMemoryDocuments()
    docs.fail_next_persist = 1
    svc, store, docs, messages = _service(persist=docs)
    first = await svc.store_inbound_document(_request())
    assert first.storage_status == STORAGE_RETRYABLE_FAILURE
    assert first.media_storage_key is None
    assert len(store.objects) == 1
    puts_after_first = len(store.put_calls)
    second = await svc.store_inbound_document(_request())
    assert second.storage_status == STORAGE_STORED
    assert second.media_storage_key
    assert len(store.objects) == 1
    assert len(store.put_calls) == puts_after_first
    assert len(docs.rows) == 1
    assert messages.keys["syn-msg-doc-1"] == second.storage_key


@pytest.mark.asyncio
async def test_6_extraction_and_storage_are_independent() -> None:
    svc, store, docs, _ = _service()
    extracted = await svc.store_inbound_document(
        _request(extraction_ok=True, extracted_json={"document_type": "CNH"})
    )
    assert extracted.commercial_received is True
    store.fail_buckets.add(PRIVATE_BUCKET)
    pending = await svc.store_inbound_document(
        _request(
            provider_message_id="syn-prov-doc-2",
            message_id="syn-msg-doc-2",
            extraction_ok=True,
            extracted_json={"document_type": "CNH", "cpf": "00000000000"},
        )
    )
    assert pending.commercial_received is True
    assert pending.storage_status == STORAGE_RETRYABLE_FAILURE
    stored_no_ocr = await svc.store_inbound_document(
        _request(
            provider_message_id="syn-prov-doc-3",
            message_id="syn-msg-doc-3",
            extraction_ok=False,
            extracted_json=None,
            document_type="OTHER",
        )
    )
    # Storage may succeed even without extraction.
    # The failing bucket is still set from the previous request on the same store.
    store.fail_buckets.clear()
    stored_no_ocr = await svc.store_inbound_document(
        _request(
            provider_message_id="syn-prov-doc-3",
            message_id="syn-msg-doc-3",
            extraction_ok=False,
            extracted_json=None,
            document_type="OTHER",
        )
    )
    assert stored_no_ocr.storage_status == STORAGE_STORED
    assert stored_no_ocr.commercial_received is True


def test_7_unknown_document_does_not_fill_known_categories() -> None:
    inbound = InboundTurn(
        thread_id="syn-conv",
        content_type=ContentType.DOCUMENT,
        text="arquivo",
        media_status=MediaStatus.OK,
        raw_message_ref={"document_extracted": {"document_type": "OTHER"}},
        segments=[
            InboundSegment(
                message_id="m1",
                content_type=ContentType.DOCUMENT,
                text="arquivo",
                document_extracted={"document_type": "OTHER"},
            )
        ],
    )
    state = ConversationCanonicalState(
        thread_id="syn-conv",
        customer=CustomerState(phone="5511900000001"),
    )
    apply_commercial_document_receipt(state, inbound)
    assert state.document_received is True
    status = state.facts.get("document_status") or {}
    assert status.get("cnh") != "received"
    assert status.get("proof_of_income") != "received"
    assert status.get("proof_of_residence") != "received"


def test_7_cnh_does_not_mark_income_or_residence() -> None:
    inbound = InboundTurn(
        thread_id="syn-conv",
        content_type=ContentType.DOCUMENT,
        media_status=MediaStatus.OK,
        raw_message_ref={"document_extracted": {"document_type": "CNH"}},
        segments=[
            InboundSegment(
                message_id="m1",
                content_type=ContentType.DOCUMENT,
                text="cnh",
                document_extracted={"document_type": "CNH"},
            )
        ],
    )
    state = ConversationCanonicalState(
        thread_id="syn-conv",
        customer=CustomerState(phone="5511900000001"),
    )
    apply_commercial_document_receipt(state, inbound)
    status = state.facts["document_status"]
    assert status["cnh"] == "received"
    assert status["proof_of_income"] == "missing"
    assert status["proof_of_residence"] == "missing"


@pytest.mark.asyncio
async def test_8_two_documents_in_one_turn_are_independent() -> None:
    svc, store, docs, messages = _service()
    store.fail_next_puts = 1
    first = await svc.store_inbound_document(
        _request(document_type="CNH", provider_message_id="p-cnh", message_id="m-cnh")
    )
    second = await svc.store_inbound_document(
        _request(
            document_type="INCOME_PROOF",
            provider_message_id="p-inc",
            message_id="m-inc",
            extracted_json={"document_type": "INCOME_PROOF"},
        )
    )
    assert first.commercial_received and second.commercial_received
    assert first.customer_error_exposed is False
    assert second.customer_error_exposed is False
    statuses = {first.storage_status, second.storage_status}
    assert STORAGE_STORED in statuses
    assert STORAGE_RETRYABLE_FAILURE in statuses
    segs = [
        InboundSegment(
            message_id="m-cnh",
            content_type=ContentType.DOCUMENT,
            text="cnh",
            document_extracted={"document_type": "CNH"},
            order=0,
        ),
        InboundSegment(
            message_id="m-inc",
            content_type=ContentType.DOCUMENT,
            text="renda",
            document_extracted={"document_type": "INCOME_PROOF"},
            order=1,
        ),
    ]
    turn = compose_inbound_turn(thread_id="syn-conv", segments=segs, batch_id="b-docs")
    state = ConversationCanonicalState(
        thread_id="syn-conv",
        customer=CustomerState(phone="5511900000001"),
    )
    apply_commercial_document_receipt(state, turn)
    assert state.facts["document_status"]["cnh"] == "received"
    assert state.facts["document_status"]["proof_of_income"] == "received"


def test_10_phase1_batch_and_deletar_still_hold() -> None:
    rows = [
        {"id": "a", "text": "oi", "transcription": None, "createdAt": 1},
        {"id": "b", "text": "/deletar", "transcription": None, "createdAt": 2},
    ]
    assert [r["id"] for r in first_batch_partition(rows)] == ["a"]
    segs = [
        InboundSegment(message_id="1", content_type=ContentType.TEXT, text="Oi", order=0),
        InboundSegment(
            message_id="2",
            content_type=ContentType.DOCUMENT,
            text="tipo: CNH",
            order=1,
        ),
    ]
    turn = compose_inbound_turn(thread_id="t", segments=segs, batch_id="one")
    assert turn.raw_message_ref["segment_count"] == 2
    assert turn.raw_message_ref["batch_id"] == "one"


@pytest.mark.asyncio
async def test_process_turn_acks_document_without_storage_key() -> None:
    inbound = InboundTurn(
        thread_id="syn-conv-k",
        content_type=ContentType.DOCUMENT,
        text="tipo: CNH",
        media_status=MediaStatus.OK,
        raw_message_ref={"document_extracted": {"document_type": "CNH"}},
    )
    state = ConversationCanonicalState(
        thread_id="syn-conv-k",
        customer=CustomerState(phone="5511900000001", name="Mateus Ferreira"),
        assistant_turn_count=1,
        intent=BusinessIntent.PURCHASE_FINANCING,
    )

    async def understand(text, _state):
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)

    from sdr.understanding import response_composer as rc

    original = rc.compose_response

    async def _template_only(s, p, tool_context=None, *, client=None):
        from sdr.understanding.response_composer import _template_compose, validate_bubbles

        return validate_bubbles(_template_compose(s, p, tool_context))

    rc.compose_response = _template_only
    try:
        result = await process_turn(state=state, inbound=inbound, understand=understand)
    finally:
        rc.compose_response = original

    joined = " ".join(result.outbound_texts)
    assert "Recebi sua CNH" in joined
    assert "salva no sistema" not in joined.lower()
    assert result.state.document_received is True
    assert result.state.facts.get("document_status", {}).get("cnh") == "received"
    assert "reenvio" not in joined.lower()
    assert "bucket" not in joined.lower()


def test_empty_bytes_are_permanent_internal_failure() -> None:
    from sdr.domain.document_storage import classify_empty_payload

    assert classify_empty_payload(b"") == STORAGE_PERMANENT_FAILURE
