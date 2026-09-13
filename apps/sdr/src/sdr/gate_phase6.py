"""Phase 6 targeted live-LLM gate — naturalness cannot be proven by templates.

Usage (from apps/sdr, with OPENAI_API_KEY in .env):

    uv run python -m sdr.gate_phase6

Writes sanitized transcripts to stdout and ``.gate/phase6-transcripts.md``.
Does not version secrets, media, or real conversations.
"""

from __future__ import annotations

import asyncio
import os
import re
from decimal import Decimal
from pathlib import Path

from sdr.application.process_turn import process_turn
from sdr.config import get_settings
from sdr.domain.decision import inventory_search_key
from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus, QuotedContext
from sdr.domain.inventory_search import InventorySearchRequest, inventory_search_key_from_request
from sdr.domain.scheduling import suggest_visit_slots
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.domain.vehicle_reference import PresentedVehicleBinding
from sdr.tools.inventory import InventoryVehicle

STRADA_2021 = "veh-strada-2021"
STRADA_2017 = "veh-strada-2017"
STRADA_2018 = "veh-strada-2018"
CONV = "syn-gate-phase6"
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".gate"


def _restore_openai_key() -> bool:
    """Load OPENAI_API_KEY from apps/sdr/.env without printing it."""
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


def _sanitize(text: str) -> str:
    text = re.sub(r"\b\d{11,}\b", "[id]", text)
    text = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[cpf]", text)
    return text


def _state(**kwargs) -> ConversationCanonicalState:
    intent = kwargs.pop("intent", BusinessIntent.UNKNOWN)
    facts = kwargs.pop("facts", {})
    turn_count = kwargs.pop("assistant_turn_count", 0)
    customer = kwargs.pop("customer", CustomerState(phone="5511999990001", name="Mateus Ferreira"))
    state = ConversationCanonicalState(
        thread_id=kwargs.pop("thread_id", CONV),
        customer=customer,
        intent=intent,
        language="pt-BR",
        facts=facts,
    )
    state.assistant_turn_count = turn_count
    for key, value in kwargs.items():
        setattr(state, key, value)
    return state


def _strada_bindings() -> list[PresentedVehicleBinding]:
    offer = "offer-set-strada-gate"
    return [
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-img-2021",
            vehicle_id=STRADA_2021,
            presentation_type="IMAGE",
            position=0,
            offer_set_id=offer,
        ),
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-img-2017",
            vehicle_id=STRADA_2017,
            presentation_type="IMAGE",
            position=1,
            offer_set_id=offer,
        ),
        PresentedVehicleBinding(
            conversation_id=CONV,
            provider_message_id="prov-img-2018",
            vehicle_id=STRADA_2018,
            presentation_type="IMAGE",
            position=2,
            offer_set_id=offer,
        ),
    ]


def _shown_stradas(**overrides) -> ConversationCanonicalState:
    facts = {"desired_model": "Strada", "desired_vehicle_text": "Strada", **overrides.pop("facts", {})}
    shown = [STRADA_2021, STRADA_2017, STRADA_2018]
    req = InventorySearchRequest(original_model="Strada", original_vehicle_text="Strada")
    key = inventory_search_key_from_request(req, last_shown_vehicle_ids=shown)
    return _state(
        intent=BusinessIntent.PURCHASE,
        facts=facts,
        last_inventory_search_key=key,
        last_shown_vehicle_ids=shown,
        presented_vehicle_bindings=_strada_bindings(),
        assistant_turn_count=2,
        **overrides,
    )


def _financing_car() -> InventoryVehicle:
    return InventoryVehicle(
        id="v-strada-gate",
        slug="strada",
        title="FIAT STRADA FREEDOM 2018",
        brand_name="Fiat",
        model="Strada",
        type="CAR",
        price_cash=Decimal("68900"),
        mileage=45000,
        color="Branco",
        year_model=2018,
        year_manufacture=2018,
        version="Freedom",
        images=({"id": "c1", "url": "https://cdn.example.test/strada.jpg", "sortOrder": 0, "isCover": True},),
    )


async def _run(name: str, *, state, inbound_text: str = "", inbound=None, understand, pool=None) -> dict:
    result = await process_turn(
        state=state,
        inbound_text=inbound_text,
        inbound=inbound,
        understand=understand,
        pool=pool,
    )
    bubbles = [_sanitize(b) for b in result.outbound_texts]
    plan = result.response_directive.dialogue_plan if result.response_directive else {}
    return {
        "name": name,
        "inbound": _sanitize(inbound_text or (inbound.text if inbound is not None else "") or ""),
        "action": result.action_plan.action.value,
        "ask_field": result.action_plan.ask_field,
        "acts": plan.get("acts") or [],
        "bubbles": bubbles,
        "primary_vehicle_id": result.state.primary_vehicle_id,
        "tools": [r.get("tool") for r in result.tool_results],
    }


def _print_case(case: dict) -> str:
    lines = [
        f"### {case['name']}",
        f"- action: `{case['action']}` ask_field=`{case['ask_field']}`",
        f"- acts: {', '.join(case['acts']) or '—'}",
        f"- inbound: {case['inbound']}",
        "- outbound:",
    ]
    if not case["bubbles"]:
        lines.append("  _(silêncio)_")
    for i, bubble in enumerate(case["bubbles"], 1):
        lines.append(f"  {i}. {bubble}")
    lines.append("")
    return "\n".join(lines)


async def run_gate() -> list[dict]:
    if not _restore_openai_key():
        raise SystemExit("OPENAI_API_KEY ausente — gate LLM bloqueado.")

    from unittest.mock import patch

    car = _financing_car()

    async def fake_search(_pool, _req):
        return [car]

    cases: list[dict] = []

    async def smalltalk(_t, _s):
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    async def purchase_strada(_t, _s):
        return TurnFacts(intent=BusinessIntent.PURCHASE, language="pt-BR", facts={"desired_model": "Strada"})

    async def financing_burst(_t, _s):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"payment_method": "financing", "down_payment": 0, "desired_model": "Civic"},
        )

    async def purchase_only(_t, _s):
        return TurnFacts(intent=BusinessIntent.PURCHASE, language="pt-BR")

    async def installment(_t, _s):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            language="pt-BR",
            facts={"desired_installment": 1800},
        )

    async def financing_keep(_t, _s):
        return TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, language="pt-BR")

    async def cash_correction(_t, _s):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={"payment_method": "cash"},
            explicit_corrections=["payment_method"],
        )

    repeats = {
        "1_cumprimento_puro": 2,
        "3_financiamento_burst": 2,
        "4_reply_strada_2018": 2,
    }

    async def once_greeting(label: str) -> dict:
        return await _run(label, state=_state(assistant_turn_count=0), inbound_text="Olá! Tudo bem?", understand=smalltalk)

    async def once_vehicle(label: str) -> dict:
        with patch("sdr.tools.inventory.search_with_request", fake_search):
            return await _run(
                label,
                state=_state(assistant_turn_count=0),
                inbound_text="Olá! E essa Strada, ainda tem?",
                understand=purchase_strada,
                pool=object(),
            )

    async def once_financing(label: str) -> dict:
        facts = {"desired_model": "Civic", "deal_type": "purchase"}
        key = inventory_search_key({**facts, "payment_method": "financing", "down_payment": 0})
        return await _run(
            label,
            state=_state(
                intent=BusinessIntent.PURCHASE,
                facts=facts,
                last_inventory_search_key=key,
                last_shown_vehicle_ids=["civic-1"],
                assistant_turn_count=1,
            ),
            inbound_text="Compra financiada.\nFinancia 100%?",
            understand=financing_burst,
        )

    async def once_reply(label: str) -> dict:
        inbound = InboundTurn(
            thread_id=CONV,
            content_type=ContentType.TEXT,
            text="Gostei dessa opção",
            media_status=MediaStatus.OK,
            quoted=[QuotedContext(stanza_id="prov-img-2018", quoted_text="Fiat Strada 2018")],
        )
        with patch("sdr.tools.inventory.search_with_request", fake_search):
            return await _run(
                label,
                state=_shown_stradas(),
                inbound=inbound,
                understand=purchase_only,
                pool=object(),
            )

    # 1 (x2)
    for i in range(repeats["1_cumprimento_puro"]):
        cases.append(await once_greeting(f"1_cumprimento_puro#{i+1}"))
    # 2
    cases.append(await once_vehicle("2_cumprimento_com_veiculo"))
    # 3 (x2)
    for i in range(repeats["3_financiamento_burst"]):
        cases.append(await once_financing(f"3_financiamento_burst#{i+1}"))
    # 4 (x2)
    for i in range(repeats["4_reply_strada_2018"]):
        cases.append(await once_reply(f"4_reply_strada_2018#{i+1}"))

    # 5 parcela
    facts5 = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
    }
    cases.append(
        await _run(
            "5_parcela_informada",
            state=_state(
                intent=BusinessIntent.PURCHASE_FINANCING,
                facts=facts5,
                last_inventory_search_key=inventory_search_key(facts5),
                last_shown_vehicle_ids=["civic-1"],
                pending_question="desired_installment",
                installment_asked=True,
                assistant_turn_count=3,
            ),
            inbound_text="Consigo pagar uns 1800 de parcela",
            understand=installment,
        )
    )

    # 6 CNH
    facts6 = {
        "desired_model": "Civic",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1800,
    }
    inbound_cnh = InboundTurn(
        thread_id=CONV,
        content_type=ContentType.DOCUMENT,
        text="nome: Mateus Ferreira\ntipo: CNH",
        media_status=MediaStatus.OK,
    )
    cases.append(
        await _run(
            "6_cnh_enviada",
            state=_state(
                intent=BusinessIntent.PURCHASE_FINANCING,
                facts=facts6,
                last_inventory_search_key=inventory_search_key(facts6),
                last_shown_vehicle_ids=["civic-1"],
                documents_asked=True,
                pending_question="documents",
                assistant_turn_count=4,
            ),
            inbound=inbound_cnh,
            understand=financing_keep,
        )
    )

    # 7 visita
    slots = suggest_visit_slots()
    facts7 = {
        "desired_model": "Civic",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 2000,
        "name": "Mateus Ferreira",
    }
    cases.append(
        await _run(
            "7_aceite_visita",
            state=_state(
                intent=BusinessIntent.PURCHASE_FINANCING,
                facts=facts7,
                last_inventory_search_key=inventory_search_key(facts7),
                last_shown_vehicle_ids=["civic-1"],
                visit_invited=True,
                offered_visit_slots=list(slots),
                documents_asked=True,
                assistant_turn_count=6,
            ),
            inbound_text="Pode ser o primeiro horário",
            understand=financing_keep,
        )
    )

    # 8 fora do conhecimento
    cases.append(
        await _run(
            "8_pergunta_fora_do_conhecimento",
            state=_shown_stradas(facts={"desired_model": "Strada", "deal_type": "purchase"}),
            inbound_text="Esse carro tem teto solar panorâmico de série?",
            understand=purchase_only,
        )
    )

    # 9 mudança de intenção
    facts9 = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
    }
    cases.append(
        await _run(
            "9_mudanca_intencao",
            state=_state(
                intent=BusinessIntent.PURCHASE_FINANCING,
                facts=facts9,
                last_inventory_search_key=inventory_search_key(facts9),
                last_shown_vehicle_ids=["civic-1"],
                pending_question="desired_installment",
                assistant_turn_count=4,
            ),
            inbound_text="Na verdade vai ser à vista",
            understand=cash_correction,
        )
    )

    # 10 cortesia
    facts10 = {
        "desired_model": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
    }

    async def thanks(_t, _s):
        return TurnFacts(intent=BusinessIntent.SMALLTALK, language="pt-BR")

    cases.append(
        await _run(
            "10_cortesia",
            state=_state(
                intent=BusinessIntent.PURCHASE_FINANCING,
                facts=facts10,
                last_inventory_search_key=inventory_search_key(facts10),
                last_shown_vehicle_ids=["civic-1"],
                pending_question="desired_installment",
                assistant_turn_count=3,
            ),
            inbound_text="Obrigado",
            understand=thanks,
        )
    )
    return cases


def main() -> None:
    cases = asyncio.run(run_gate())
    body = ["# Phase 6 LLM gate transcripts (sanitized)", ""]
    for case in cases:
        chunk = _print_case(case)
        body.append(chunk)
        print(chunk)
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "phase6-transcripts.md").write_text("\n".join(body), encoding="utf-8")
    print(f"wrote {OUT_DIR / 'phase6-transcripts.md'}")


if __name__ == "__main__":
    main()
