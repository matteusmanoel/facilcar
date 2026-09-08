"""Semantic response plan — what the turn must fulfill, not how to word it.

The Composer (LLM or fallback) phrases naturally. Code owns:
  allowed facts, required acts, canonical question, commercial risks.

Question-kind detection is PROTOCOL / SAFE_FAST_PATH (commercial question
types), not brand/model/slang lists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from sdr.domain.display_name import display_first_name
from sdr.domain.types import Action, BusinessIntent, ConversationCanonicalState, TurnFacts


class DialogueAct(str, Enum):
    ANSWER_DIRECT_QUESTION = "answer_direct_question"
    ACKNOWLEDGE_FACT = "acknowledge_fact"
    RAPPORT = "rapport"
    CLARIFY = "clarify"
    PRESENT_VEHICLE = "present_vehicle"
    ASK_NEXT_FIELD = "ask_next_field"
    INVITE_VISIT = "invite_visit"
    CONFIRM_VISIT = "confirm_visit"
    HANDOFF_MESSAGE = "handoff_message"
    SAFETY_DISCLAIMER = "safety_disclaimer"


class DirectQuestionKind(str, Enum):
    FINANCING_100 = "financing_100"
    ACCEPT_TRADE = "accept_trade"
    AVAILABILITY = "availability"
    PRICE = "price"
    WARRANTY = "warranty"
    DOCUMENTS_LATER = "documents_later"
    BUY_MY_CAR = "buy_my_car"
    SATURDAY_HOURS = "saturday_hours"
    STORE_LOCATION = "store_location"
    WELLBEING = "wellbeing"
    UNKNOWN = "unknown"


_COURTESY = re.compile(
    r"\b(?:obrigad[oa]|valeu|agrade[cç]o|thanks)\b",
    re.I,
)
_GREETING = re.compile(
    r"^\s*(?:oi+|ol[áa]|oie|hola|bom\s+dia|boa\s+tarde|boa\s+noite)\b",
    re.I,
)
_WELLBEING = re.compile(
    r"tudo\s+bem\??|como\s+(?:vai|est[aá]|voc[eê]\s+est[aá])\??|tudo\s+certo\??|beleza\??",
    re.I,
)
_INTENT_MENU_TERMS = ("comprar", "trocar", "vender", "consignar", "refinanciar")

# Commercial question stems — protocol categories, not product vocabulary.
_QUESTION_STEMS: tuple[tuple[DirectQuestionKind, re.Pattern[str]], ...] = (
    (
        DirectQuestionKind.FINANCING_100,
        re.compile(
            r"financia(?:r)?\s*(?:o\s+)?(?:valor\s+)?(?:todo|100)|"
            r"100\s*%|sem\s+entrada|financia\s+tudo",
            re.I,
        ),
    ),
    (
        DirectQuestionKind.ACCEPT_TRADE,
        re.compile(
            r"aceit\w+\s+(?:meu\s+)?(?:carro|ve[ií]culo).{0,24}troca|"
            r"aceit\w+\s+(?:na\s+)?troca|faz(?:em)?\s+troca",
            re.I,
        ),
    ),
    (
        DirectQuestionKind.AVAILABILITY,
        re.compile(r"ainda\s+est[aá]\s+dispon[ií]vel|ainda\s+tem|est[aá]\s+dispon[ií]vel", re.I),
    ),
    (
        DirectQuestionKind.PRICE,
        re.compile(r"qual\s+(?:[eé]\s+)?o\s+valor|quanto\s+custa|qual\s+o\s+pre[cç]o", re.I),
    ),
    (
        DirectQuestionKind.WARRANTY,
        re.compile(r"\bgarantia\b", re.I),
    ),
    (
        DirectQuestionKind.DOCUMENTS_LATER,
        re.compile(
            r"documentos?\s+depois|mandar\s+depois|enviar\s+depois|depois\s+(?:eu\s+)?(?:mando|envio)",
            re.I,
        ),
    ),
    (
        DirectQuestionKind.BUY_MY_CAR,
        re.compile(r"compram?\s+(?:o\s+)?meu\s+carro|voc[eê]s\s+compram", re.I),
    ),
    (
        DirectQuestionKind.SATURDAY_HOURS,
        re.compile(r"abre\s+no\s+s[aá]bado|funcion\w+.{0,12}s[aá]bado|abre\s+s[aá]bado", re.I),
    ),
    (
        DirectQuestionKind.STORE_LOCATION,
        re.compile(r"onde\s+fica|endere[cç]o(?:\s+da\s+loja)?|localiza[cç][aã]o\s+da\s+loja", re.I),
    ),
)

_INTERNAL_LEAK = re.compile(
    r"\b(?:handoff|triagem|decision\s+engine|crm|intelig[eê]ncia\s+artificial|"
    r"sou\s+(?:uma?\s+)?(?:ia|rob[oô]|pr[eé]-?atendente))\b",
    re.I,
)
_VENDOR_CONFIRM = re.compile(
    r"confirma[cç][aã]o\s+do\s+vendedor|depende\s+do\s+vendedor|"
    r"vou\s+confirmar\s+com\s+o\s+vendedor",
    re.I,
)
_APPROVAL_CLAIM = re.compile(
    r"financiamento\s+(?:est[aá]\s+)?aprovado|j[aá]\s+est[aá]\s+aprovad|"
    r"vamos\s+financiar\s+(?:o\s+valor\s+)?(?:todo|tudo)|"
    r"financiaremos\s+el\s+valor\s+total|"
    r"100\s*%\s*garantid|taxa\s+garantida|aprova(?:[cç][aã]o|do)\s+garantid|"
    r"financiar\s+o\s+valor\s+todo",
    re.I,
)


@dataclass(slots=True)
class DirectQuestion:
    kind: DirectQuestionKind
    answerable: bool
    allowed_answer: str
    inbound_span: str = ""


@dataclass(slots=True)
class DialoguePlan:
    """Turn-level semantic obligations for the Composer."""

    acts: list[str] = field(default_factory=list)
    direct_questions: list[dict[str, Any]] = field(default_factory=list)
    facts_to_acknowledge: list[str] = field(default_factory=list)
    canonical_question: str | None = None
    use_name: bool = False
    skip_generic_intent_menu: bool = False
    skip_reintroduce: bool = False
    courtesy_only: bool = False
    wellbeing_reciprocity: bool = False
    forbid_reask_fields: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    proven_vehicle_label: str | None = None
    vehicle_label_source: str | None = None
    primary_action: str | None = None
    supporting_acts: list[str] = field(default_factory=list)
    forbidden_concurrent_actions: list[str] = field(default_factory=list)
    remaining_documents: list[str] = field(default_factory=list)
    max_text_bubbles: int = 3
    max_questions: int = 1
    availability_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "acts": list(self.acts),
            "direct_questions": list(self.direct_questions),
            "facts_to_acknowledge": list(self.facts_to_acknowledge),
            "canonical_question": self.canonical_question,
            "use_name": self.use_name,
            "skip_generic_intent_menu": self.skip_generic_intent_menu,
            "skip_reintroduce": self.skip_reintroduce,
            "courtesy_only": self.courtesy_only,
            "wellbeing_reciprocity": self.wellbeing_reciprocity,
            "forbid_reask_fields": list(self.forbid_reask_fields),
            "proven_vehicle_label": self.proven_vehicle_label,
            "vehicle_label_source": self.vehicle_label_source,
            "primary_action": self.primary_action,
            "supporting_acts": list(self.supporting_acts),
            "forbidden_concurrent_actions": list(self.forbidden_concurrent_actions),
            "remaining_documents": list(self.remaining_documents),
            "max_text_bubbles": self.max_text_bubbles,
            "max_questions": self.max_questions,
            "availability_status": self.availability_status,
            "restrictions": list(self.restrictions),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "DialoguePlan":
        if not isinstance(raw, Mapping):
            return cls()
        return cls(
            acts=[str(a) for a in (raw.get("acts") or [])],
            direct_questions=[dict(q) for q in (raw.get("direct_questions") or []) if isinstance(q, Mapping)],
            facts_to_acknowledge=[str(f) for f in (raw.get("facts_to_acknowledge") or [])],
            canonical_question=(str(raw["canonical_question"]) if raw.get("canonical_question") else None),
            use_name=bool(raw.get("use_name")),
            skip_generic_intent_menu=bool(raw.get("skip_generic_intent_menu")),
            skip_reintroduce=bool(raw.get("skip_reintroduce")),
            courtesy_only=bool(raw.get("courtesy_only")),
            wellbeing_reciprocity=bool(raw.get("wellbeing_reciprocity")),
            forbid_reask_fields=[str(f) for f in (raw.get("forbid_reask_fields") or [])],
            restrictions=[str(r) for r in (raw.get("restrictions") or [])],
            proven_vehicle_label=(
                str(raw["proven_vehicle_label"]) if raw.get("proven_vehicle_label") else None
            ),
            vehicle_label_source=(
                str(raw["vehicle_label_source"]) if raw.get("vehicle_label_source") else None
            ),
            primary_action=(str(raw["primary_action"]) if raw.get("primary_action") else None),
            supporting_acts=[str(a) for a in (raw.get("supporting_acts") or [])],
            forbidden_concurrent_actions=[
                str(a) for a in (raw.get("forbidden_concurrent_actions") or [])
            ],
            remaining_documents=[str(a) for a in (raw.get("remaining_documents") or [])],
            max_text_bubbles=int(raw.get("max_text_bubbles") or 3),
            max_questions=int(raw.get("max_questions") or 1),
            availability_status=(
                str(raw["availability_status"]) if raw.get("availability_status") else None
            ),
        )


def has_wellbeing_question(text: str) -> bool:
    return bool(_WELLBEING.search(text or ""))


def has_greeting_opener(text: str) -> bool:
    return bool(_GREETING.match(text or ""))


def is_courtesy_only(text: str, facts: TurnFacts | None = None) -> bool:
    """True when the inbound is only thanks — no question and no new commercial facts."""
    collected = (facts.facts if facts is not None else None) or {}
    if collected:
        return False
    if facts is not None:
        sig = facts.signals
        if any(
            getattr(sig, name, None) is True
            for name in ("explicit_handoff", "explicit_offer", "visit_intent", "high_purchase_intent")
        ):
            return False
    raw = (text or "").strip()
    if not raw or "?" in raw:
        return False
    if not _COURTESY.search(raw):
        return False
    remainder = _COURTESY.sub(" ", raw)
    remainder = re.sub(r"[^\wáéíóúãõç]+", " ", remainder, flags=re.I).strip()
    return len(remainder.split()) <= 2


def looks_like_intent_menu(text: str) -> bool:
    low = (text or "").lower()
    hits = sum(1 for term in _INTENT_MENU_TERMS if term in low)
    return hits >= 3


def classify_direct_questions(inbound_text: str) -> list[DirectQuestion]:
    text = inbound_text or ""
    found: list[DirectQuestion] = []
    if has_wellbeing_question(text):
        found.append(
            DirectQuestion(
                kind=DirectQuestionKind.WELLBEING,
                answerable=True,
                allowed_answer="Responda com reciprocidade breve (está bem) e convide a continuar.",
                inbound_span="wellbeing",
            )
        )
    for kind, pattern in _QUESTION_STEMS:
        if pattern.search(text):
            found.append(_question_for_kind(kind, text))
    if "?" in text and not any(q.kind != DirectQuestionKind.WELLBEING for q in found):
        found.append(
            DirectQuestion(
                kind=DirectQuestionKind.UNKNOWN,
                answerable=False,
                allowed_answer=(
                    "A informação pedida não está disponível com segurança. "
                    "Seja transparente, não invente, e ofereça o próximo passo útil."
                ),
                inbound_span=text[:160],
            )
        )
    return found


def _question_for_kind(kind: DirectQuestionKind, text: str) -> DirectQuestion:
    answers = {
        DirectQuestionKind.FINANCING_100: (
            True,
            "Pode simular sem entrada. Aprovação, taxa, prazo e condições "
            "dependem da análise da financeira. Não afirme aprovação nem 100% garantido.",
        ),
        DirectQuestionKind.ACCEPT_TRADE: (
            True,
            "Sim, a FacilCar trabalha com troca. Depois avance para o veículo do cliente.",
        ),
        DirectQuestionKind.AVAILABILITY: (
            True,
            "Responda a disponibilidade de forma explícita (está disponível / foi vendido / "
            "está reservado / não conseguiu confirmar / há mais de uma possibilidade). "
            "Não invente estoque. Não deixe a disponibilidade só implícita.",
        ),
        DirectQuestionKind.PRICE: (
            True,
            "Informe o preço publicado do veículo primário se existir no contexto. Não invente valor.",
        ),
        DirectQuestionKind.WARRANTY: (
            False,
            "Não invente garantia. Diga que o time confirma as condições e siga o próximo passo útil.",
        ),
        DirectQuestionKind.DOCUMENTS_LATER: (
            True,
            "Pode enviar os documentos depois. Não bloqueie o atendimento por isso.",
        ),
        DirectQuestionKind.BUY_MY_CAR: (
            True,
            "Sim, a loja avalia compra do veículo do cliente. Peça os dados do usado sem menu de intenções.",
        ),
        DirectQuestionKind.SATURDAY_HOURS: (
            True,
            "A loja atende aos sábados. Ofereça horário concreto se couber, sem inventar expediente detalhado.",
        ),
        DirectQuestionKind.STORE_LOCATION: (
            True,
            "A localização vai no pin quando planejado. Não invente endereço. Convide a visita se útil.",
        ),
    }
    answerable, allowed = answers[kind]
    return DirectQuestion(kind=kind, answerable=answerable, allowed_answer=allowed, inbound_span=text[:160])


def _has_vehicle_context(
    state: ConversationCanonicalState | None,
    facts_context: Mapping[str, Any] | None,
) -> bool:
    facts = dict(facts_context or {})
    if state is not None:
        facts = {**dict(state.facts or {}), **facts}
        if state.last_shown_vehicle_ids or state.primary_vehicle_id or state.listing_reference:
            return True
    model = facts.get("desired_model") or facts.get("desired_vehicle_text")
    return bool(isinstance(model, str) and model.strip())


def _intent_known(intent: BusinessIntent | str | None) -> bool:
    value = intent.value if isinstance(intent, BusinessIntent) else str(intent or "")
    return value not in ("", "unknown", "smalltalk", BusinessIntent.UNKNOWN.value, BusinessIntent.SMALLTALK.value)


def _filled_fields(facts: Mapping[str, Any]) -> list[str]:
    filled: list[str] = []
    for key, value in facts.items():
        if value is None or value == "":
            continue
        if isinstance(value, str) and not value.strip():
            continue
        filled.append(str(key))
    return filled


def _proven_vehicle_label(
    state: ConversationCanonicalState | None,
    facts_context: Mapping[str, Any] | None,
) -> tuple[str | None, str]:
    facts = dict(facts_context or {})
    if state is not None:
        facts = {**dict(state.facts or {}), **facts}
        from sdr.domain.vehicle_catalog import conversational_label_for_id

        presented = getattr(state, "presented_vehicle_catalog", None)
        if state.primary_vehicle_id:
            label = conversational_label_for_id(
                state.primary_vehicle_id,
                presented=presented if isinstance(presented, dict) else None,
            )
            if label:
                return label, "catalog"
    for key in ("desired_vehicle_text", "desired_model"):
        raw = facts.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), "stated_model"
    return None, "none"


def build_dialogue_plan(
    *,
    inbound_text: str,
    action: Action | str,
    ask_field: str | None = None,
    intent: BusinessIntent | str | None = None,
    should_introduce: bool = False,
    assistant_turn_count: int = 0,
    ack_kind: str | None = None,
    inbound_content_type: str = "TEXT",
    facts_context: Mapping[str, Any] | None = None,
    turn_facts: TurnFacts | None = None,
    state: ConversationCanonicalState | None = None,
    reason_code: str | None = None,
    visit_cta_style: str | None = None,
    document_kind: str | None = None,
    lifecycle_status: str | None = None,
    vehicle_chosen_this_turn: bool = False,
    availability_status: str | None = None,
) -> DialoguePlan:
    """Build the semantic plan for this turn from canonical state + inbound."""
    action_val = action.value if isinstance(action, Action) else str(action or "")
    facts = dict(facts_context or {})
    if state is not None and not facts:
        facts = dict(state.facts or {})
    intent_val = intent
    if intent_val is None and state is not None:
        intent_val = state.intent
    lifecycle = lifecycle_status or (state.lifecycle.status.value if state is not None else "BOT_ACTIVE")

    questions = classify_direct_questions(inbound_text)
    courtesy = is_courtesy_only(inbound_text, turn_facts)
    vehicle_ctx = _has_vehicle_context(state, facts)
    known_intent = _intent_known(intent_val)
    wellbeing = any(q.kind == DirectQuestionKind.WELLBEING for q in questions)
    commercial_qs = [q for q in questions if q.kind != DirectQuestionKind.WELLBEING]

    new_fact_keys: list[str] = []
    if turn_facts and turn_facts.facts:
        new_fact_keys = _filled_fields(turn_facts.facts)
    elif ack_kind:
        mapped = {
            "payment_financing": "payment_method",
            "payment_cash": "payment_method",
            "down_payment": "down_payment",
            "desired_installment": "desired_installment",
            "deal_purchase": "deal_type",
            "deal_trade": "deal_type",
            "document_received": "documents",
            "difference_financing": "payment_method",
            "difference_cash": "payment_method",
        }
        if ack_kind in mapped:
            new_fact_keys = [mapped[ack_kind]]

    if inbound_content_type.upper() == "DOCUMENT" and "documents" not in new_fact_keys:
        new_fact_keys.append("documents")
    if vehicle_chosen_this_turn and "vehicle_choice" not in new_fact_keys:
        new_fact_keys.append("vehicle_choice")

    known_fields = _filled_fields(facts)
    forbid_reask = list(dict.fromkeys(known_fields + new_fact_keys))

    acts: list[str] = []
    restrictions: list[str] = [
        "Não invente estoque, preço, taxa, parcela ou aprovação.",
        "Não diga que é IA, robô, pré-atendente, nem use handoff/triagem/CRM/Decision Engine.",
        "Não afirme confirmação do vendedor nem agenda individual.",
        "Uma pergunta principal por vez.",
    ]

    if commercial_qs:
        acts.append(DialogueAct.ANSWER_DIRECT_QUESTION.value)
    if wellbeing and not courtesy:
        acts.append(DialogueAct.RAPPORT.value)
    if new_fact_keys and not courtesy:
        acts.append(DialogueAct.ACKNOWLEDGE_FACT.value)
    if courtesy:
        acts.append(DialogueAct.RAPPORT.value)

    if any(q.kind == DirectQuestionKind.FINANCING_100 for q in commercial_qs) or (
        facts.get("down_payment") in (0, "0") and "payment_method" in (new_fact_keys + known_fields)
        and facts.get("payment_method") == "financing"
    ):
        acts.append(DialogueAct.SAFETY_DISCLAIMER.value)
        restrictions.append(
            "Financiamento sem entrada: simulação possível; aprovação e condições dependem da financeira."
        )
        restrictions.append("Proibido: financiamento aprovado, vamos financiar tudo, 100% garantido, taxa garantida.")

    if action_val == Action.SHOW_OFFERS.value:
        acts.append(DialogueAct.PRESENT_VEHICLE.value)
    if action_val == Action.REGISTER_VISIT_INTEREST.value:
        if visit_cta_style in ("location_close",) or (
            state is not None and (state.visit_accepted_offered or state.visit_preferred_time)
        ):
            acts.append(DialogueAct.CONFIRM_VISIT.value)
        else:
            acts.append(DialogueAct.INVITE_VISIT.value)
    if action_val == Action.SEND_LOCATION.value:
        acts.append(DialogueAct.INVITE_VISIT.value)
    if action_val == Action.HANDOFF_VENDOR.value:
        acts.append(DialogueAct.HANDOFF_MESSAGE.value)
    if action_val == Action.COMMERCIAL_UNKNOWN.value:
        acts.append(DialogueAct.CLARIFY.value)

    ask = ask_field if ask_field not in (None, "", "intent") else None
    if (
        ask
        and action_val == Action.ASK_INFO.value
        and not courtesy
        and ask not in forbid_reask
    ):
        acts.append(DialogueAct.ASK_NEXT_FIELD.value)
    elif ask and action_val in (
        Action.SHOW_OFFERS.value,
        Action.SEND_PHOTOS.value,
        Action.SEND_LOCATION.value,
    ):
        acts.append(DialogueAct.ASK_NEXT_FIELD.value)

    skip_menu = known_intent or vehicle_ctx or bool(commercial_qs)
    if skip_menu:
        restrictions.append(
            "NÃO apresente o menu genérico comprar/trocar/vender/consignar/refinanciar."
        )
    if skip_menu and action_val == Action.SHOW_OFFERS.value:
        restrictions.append(
            "Não elogie o modelo de forma genérica (excelente opção) sem fato de estoque."
        )
    if "desired_installment" in new_fact_keys:
        restrictions.append(
            "Reconheça a parcela de forma factual, em reais (R$), sem celebração artificial."
        )
    if should_introduce and action_val == Action.SMALLTALK.value:
        restrictions.append(
            "Convite aberto e natural. Não presuma que o cliente possui um veículo."
        )
    skip_reintro = (not should_introduce) or assistant_turn_count > 0 or lifecycle in (
        "HANDOFF_SENT",
        "HUMAN_ACTIVE",
    )

    use_name = bool(
        should_introduce
        or action_val in (Action.HANDOFF_VENDOR.value, Action.REGISTER_VISIT_INTEREST.value)
        or inbound_content_type.upper() == "DOCUMENT"
        or document_kind
        or ack_kind == "document_received"
    )

    max_bubbles = 2
    if action_val in (Action.SHOW_OFFERS.value, Action.SEND_PHOTOS.value):
        max_bubbles = 3
    remaining_docs: list[str] = []
    primary_action = None
    supporting_acts: list[str] = []
    forbidden_concurrent: list[str] = []
    if state is not None:
        from sdr.domain.qualification_policy import (
            ACT_HANDOFF,
            ACT_INVITE_VISIT,
            PRIMARY_ASK_REMAINING_DOCUMENTS,
            remaining_document_components,
        )

        remaining_docs = remaining_document_components(state)
        remaining_this_turn = (
            action_val == Action.ASK_INFO.value
            and ask == "documents"
            and bool(remaining_docs)
            and (
                state.document_received
                or any(status == "received" for status in (state.facts.get("document_status") or {}).values())
            )
        )
        if remaining_this_turn:
            primary_action = PRIMARY_ASK_REMAINING_DOCUMENTS
            supporting_acts = ["acknowledge_document"]
            forbidden_concurrent = [ACT_INVITE_VISIT, ACT_HANDOFF]
            max_bubbles = 2
            restrictions.append(
                "Peça só os comprovantes restantes. Não convide visita nem encaminhe neste turno."
            )
            acts = [a for a in acts if a != DialogueAct.INVITE_VISIT.value]
        elif action_val == Action.REGISTER_VISIT_INTEREST.value:
            primary_action = "invite_visit"
            forbidden_concurrent = ["ask_remaining_documents"]

    if inbound_content_type.upper() == "DOCUMENT" and primary_action != "ask_remaining_documents":
        max_bubbles = 3
    if courtesy:
        max_bubbles = 2
        ask = None

    # Preserve unique act order.
    seen: set[str] = set()
    ordered_acts: list[str] = []
    for act in acts:
        if act not in seen:
            seen.add(act)
            ordered_acts.append(act)

    label, label_source = _proven_vehicle_label(state, facts)

    return DialoguePlan(
        acts=ordered_acts,
        direct_questions=[
            {
                "kind": q.kind.value,
                "answerable": q.answerable,
                "allowed_answer": q.allowed_answer,
            }
            for q in questions
            if q.kind != DirectQuestionKind.WELLBEING or wellbeing
        ],
        facts_to_acknowledge=new_fact_keys,
        canonical_question=None if courtesy else ask,
        use_name=use_name,
        skip_generic_intent_menu=skip_menu,
        skip_reintroduce=skip_reintro,
        courtesy_only=courtesy,
        wellbeing_reciprocity=wellbeing,
        forbid_reask_fields=forbid_reask,
        restrictions=restrictions,
        proven_vehicle_label=label,
        vehicle_label_source=label_source,
        primary_action=primary_action,
        supporting_acts=supporting_acts,
        forbidden_concurrent_actions=forbidden_concurrent,
        remaining_documents=remaining_docs,
        max_text_bubbles=max_bubbles,
        max_questions=0 if courtesy or action_val == Action.HANDOFF_VENDOR.value else 1,
        availability_status=availability_status,
    )


def dialogue_objective_suffix(plan: DialoguePlan) -> str:
    """Natural-language obligations appended to response_objective — not a copy template."""
    parts: list[str] = []
    if plan.wellbeing_reciprocity:
        parts.append("Responda com reciprocidade à pergunta de cortesia do cliente neste turno.")
    if plan.courtesy_only:
        parts.append("Agradeça de forma breve. Não reabra o roteiro nem faça nova pergunta de qualificação.")
    kinds = [str(q.get("kind")) for q in plan.direct_questions]
    commercial = [k for k in kinds if k and k != DirectQuestionKind.WELLBEING.value]
    if commercial:
        parts.append(
            "Responda primeiro a pergunta comercial direta do cliente antes de qualquer campo do roteiro."
        )
        for q in plan.direct_questions:
            if q.get("kind") == DirectQuestionKind.WELLBEING.value:
                continue
            parts.append(f"Pergunta ({q.get('kind')}): {q.get('allowed_answer')}")
    if plan.facts_to_acknowledge:
        parts.append(
            "Reconheça de forma breve o que o cliente acabou de informar: "
            + ", ".join(plan.facts_to_acknowledge)
            + ". Não pergunte de novo esses campos."
        )
    if plan.skip_generic_intent_menu:
        parts.append(
            "NÃO apresente o menu genérico comprar/trocar/vender/consignar/refinanciar."
        )
    if plan.skip_reintroduce:
        parts.append("NÃO se apresente de novo nem reabra como primeiro contato.")
    if plan.canonical_question:
        parts.append(f"Uma pergunta principal: campo `{plan.canonical_question}`.")
    elif plan.max_questions == 0:
        parts.append("Não faça pergunta de qualificação neste turno.")
    if not plan.use_name:
        parts.append("Não use o nome do cliente neste turno.")
    else:
        parts.append("Pode usar o primeiro nome no máximo uma vez.")
    parts.extend(plan.restrictions)
    return " ".join(parts)


def infer_realized_acts(bubbles: Sequence[str], plan: DialoguePlan) -> list[str]:
    """Best-effort acts observed in outbound — for trace, not for copy matching."""
    joined = " ".join(b for b in bubbles if isinstance(b, str)).lower()
    realized: list[str] = []
    if DialogueAct.ANSWER_DIRECT_QUESTION.value in plan.acts:
        kinds = {str(q.get("kind")) for q in plan.direct_questions}
        if DirectQuestionKind.FINANCING_100.value in kinds and any(
            token in joined for token in ("simula", "sem entrada", "análise", "financeira")
        ):
            realized.append(DialogueAct.ANSWER_DIRECT_QUESTION.value)
        elif DirectQuestionKind.ACCEPT_TRADE.value in kinds and "troca" in joined:
            realized.append(DialogueAct.ANSWER_DIRECT_QUESTION.value)
        elif DirectQuestionKind.AVAILABILITY.value in kinds and any(
            token in joined
            for token in (
                "dispon",
                "vendid",
                "reserv",
                "não consegui confirmar",
                "mais de uma",
                "estoque",
            )
        ):
            realized.append(DialogueAct.ANSWER_DIRECT_QUESTION.value)
        elif DirectQuestionKind.UNKNOWN.value in kinds and any(
            token in joined for token in ("não tenho", "não consigo confirmar", "equipe", "não está")
        ):
            realized.append(DialogueAct.ANSWER_DIRECT_QUESTION.value)
        elif "?" not in joined or len(kinds) == 0:
            pass
        else:
            # Other commercial questions: presence of a declarative clause before "?".
            if re.search(r"[.!] ", joined) or "sim" in joined:
                realized.append(DialogueAct.ANSWER_DIRECT_QUESTION.value)
    if DialogueAct.RAPPORT.value in plan.acts:
        if plan.wellbeing_reciprocity and any(
            token in joined for token in ("tudo bem", "bem sim", "e você", "e com você", "por aqui", "tudo certo")
        ):
            realized.append(DialogueAct.RAPPORT.value)
        elif plan.courtesy_only and any(
            token in joined for token in ("por nada", "disponha", "imagina", "que isso", "qualquer")
        ):
            realized.append(DialogueAct.RAPPORT.value)
        elif not plan.wellbeing_reciprocity:
            realized.append(DialogueAct.RAPPORT.value)
    if DialogueAct.ACKNOWLEDGE_FACT.value in plan.acts:
        if any(
            token in joined
            for token in ("entendi", "perfeito", "ótimo", "certo", "anotei", "recebi", "boa escolha", "legal")
        ):
            realized.append(DialogueAct.ACKNOWLEDGE_FACT.value)
    if DialogueAct.SAFETY_DISCLAIMER.value in plan.acts:
        if any(token in joined for token in ("análise", "financeira", "sujeito", "simula")):
            realized.append(DialogueAct.SAFETY_DISCLAIMER.value)
    if DialogueAct.ASK_NEXT_FIELD.value in plan.acts and "?" in joined:
        realized.append(DialogueAct.ASK_NEXT_FIELD.value)
    if DialogueAct.PRESENT_VEHICLE.value in plan.acts:
        realized.append(DialogueAct.PRESENT_VEHICLE.value)
    if DialogueAct.INVITE_VISIT.value in plan.acts:
        realized.append(DialogueAct.INVITE_VISIT.value)
    if DialogueAct.CONFIRM_VISIT.value in plan.acts:
        realized.append(DialogueAct.CONFIRM_VISIT.value)
    if DialogueAct.HANDOFF_MESSAGE.value in plan.acts:
        realized.append(DialogueAct.HANDOFF_MESSAGE.value)
    if DialogueAct.CLARIFY.value in plan.acts:
        realized.append(DialogueAct.CLARIFY.value)
    return realized


def first_name_from(customer_name: str | None) -> str | None:
    return display_first_name(customer_name)


def contains_internal_leak(text: str) -> bool:
    return bool(_INTERNAL_LEAK.search(text or ""))


def contains_vendor_confirmation(text: str) -> bool:
    return bool(_VENDOR_CONFIRM.search(text or ""))


def contains_financing_approval_claim(text: str) -> bool:
    return bool(_APPROVAL_CLAIM.search(text or ""))


_HONEST_UNKNOWN = re.compile(
    r"n[aã]o\s+tenho|n[aã]o\s+consigo\s+confirmar|n[aã]o\s+est[aá]\s+no|"
    r"n[aã]o\s+tenho\s+essa|equipe|n[aã]o\s+consta",
    re.I,
)
_RECIPROCITY = re.compile(
    r"tudo\s+bem(?:\s+sim)?|bem\s+sim|e\s+voc[eê]|e\s+com\s+voc[eê]|por\s+aqui|tudo\s+certo",
    re.I,
)
_DOWN_REASK = re.compile(r"\b(?:tem\s+ideia\s+de\s+entrada|valor\s+de\s+entrada|quanto\s+de\s+entrada)\b", re.I)
_INSTALLMENT_REASK = re.compile(r"at[eé]\s+quanto\s+de\s+parcela", re.I)


def fallback_bubbles(
    plan: DialoguePlan,
    *,
    language: str = "pt-BR",
    customer_name: str | None = None,
    next_question: str | None = None,
    document_kind: str | None = None,
    should_introduce: bool = False,
) -> list[str]:
    """Contextual safety fallback — not the primary production voice."""
    es = (language or "").lower().startswith("es")
    name = first_name_from(customer_name) if plan.use_name else None
    kinds = {str(q.get("kind")) for q in plan.direct_questions}
    bubbles: list[str] = []

    if plan.courtesy_only:
        return ["Por nada! Qualquer coisa é só chamar."] if not es else ["¡De nada! Cualquier cosa, me avisas."]

    if should_introduce and not plan.skip_reintroduce:
        if plan.wellbeing_reciprocity:
            if es:
                hello = (
                    f"Hola{f', {name}' if name else ''}! Todo bien sí, ¿y tú? Soy Júlia de FacilCar."
                )
            else:
                hello = (
                    f"Oi{f', {name}' if name else ''}! Tudo bem sim, e com você? Sou a Júlia da FacilCar."
                )
        elif name:
            hello = f"Oi, {name}! Sou a Júlia da FacilCar." if not es else f"Hola, {name}. Soy Júlia de FacilCar."
        else:
            hello = "Oi! Sou a Júlia da FacilCar." if not es else "¡Hola! Soy Júlia de FacilCar."
        bubbles.append(hello)

    if plan.wellbeing_reciprocity and not should_introduce:
        bubbles.append("Tudo bem sim, e com você?" if not es else "Todo bien sí, ¿y tú?")

    if DirectQuestionKind.FINANCING_100.value in kinds or DialogueAct.SAFETY_DISCLAIMER.value in plan.acts:
        if es:
            bubbles.append(
                "Podemos hacer una simulación sin entrada. La aprobación y las condiciones "
                "dependen del análisis de la financiera."
            )
        else:
            bubbles.append(
                "Podemos fazer uma simulação sem entrada. A aprovação e as condições "
                "dependem da análise da financeira."
            )
    elif DirectQuestionKind.ACCEPT_TRADE.value in kinds:
        bubbles.append(
            "Sim, trabalhamos com troca."
            if not es
            else "Sí, trabajamos con permuta."
        )
    elif DirectQuestionKind.AVAILABILITY.value in kinds:
        label = plan.proven_vehicle_label or ("o veículo" if not es else "el vehículo")
        status = plan.availability_status or "unknown"
        if status == "sold":
            bubbles.append(
                f"Esse {label} já foi vendido."
                if not es
                else f"Ese {label} ya fue vendido."
            )
        elif status == "reserved":
            bubbles.append(
                f"Esse {label} está reservado no momento."
                if not es
                else f"Ese {label} está reservado en este momento."
            )
        elif status == "ambiguous":
            bubbles.append(
                "Encontrei mais de uma possibilidade no estoque. Qual dessas opções é a sua?"
                if not es
                else "Encontré más de una posibilidad. ¿Cuál de esas opciones es la tuya?"
            )
        elif status == "available":
            bubbles.append(
                f"Sim, {label} está disponível."
                if not es
                else f"Sí, {label} está disponible."
            )
        elif status == "unpublished":
            bubbles.append(
                f"Esse {label} não está disponível no estoque publicado."
                if not es
                else f"Ese {label} no está disponible en el stock publicado."
            )
        else:
            bubbles.append(
                "Não consegui confirmar a disponibilidade desse veículo com segurança."
                if not es
                else "No pude confirmar la disponibilidad de ese vehículo con seguridad."
            )
    elif DirectQuestionKind.BUY_MY_CAR.value in kinds:
        bubbles.append(
            "Sim, avaliamos a compra do seu veículo."
            if not es
            else "Sí, evaluamos la compra de tu vehículo."
        )
    elif DirectQuestionKind.DOCUMENTS_LATER.value in kinds:
        bubbles.append(
            "Pode enviar os documentos depois, sem problema."
            if not es
            else "Puedes enviar los documentos después, sin problema."
        )
    elif DirectQuestionKind.SATURDAY_HOURS.value in kinds:
        bubbles.append(
            "Atendemos aos sábados. Se quiser, te passo um horário."
            if not es
            else "Atendemos los sábados. Si quieres, te paso un horario."
        )
    elif DirectQuestionKind.STORE_LOCATION.value in kinds:
        bubbles.append(
            "Te envio a localização da loja."
            if not es
            else "Te envío la ubicación de la tienda."
        )
    elif DirectQuestionKind.WARRANTY.value in kinds or DirectQuestionKind.UNKNOWN.value in kinds:
        bubbles.append(
            "Esse detalhe eu não tenho confirmado aqui. Posso encaminhar para a equipe."
            if not es
            else "Ese detalle no lo tengo confirmado aquí. Puedo pasarlo al equipo."
        )
    elif DirectQuestionKind.PRICE.value in kinds:
        bubbles.append(
            "O valor é o publicado no anúncio que te mostrei. Se não estiver à mão, confirmo com a equipe."
            if not es
            else "El valor es el publicado en el anuncio. Si no está a mano, lo confirmo con el equipo."
        )

    if "documents" in plan.facts_to_acknowledge or document_kind:
        kind = (document_kind or "CNH").upper()
        if kind == "CNH":
            ack = f"Recebi sua CNH{f', {name}' if name else ''}." if not es else f"Recibí tu CNH{f', {name}' if name else ''}."
        else:
            ack = "Recebi seu documento." if not es else "Recibí tu documento."
        bubbles.append(ack)

    if DialogueAct.ACKNOWLEDGE_FACT.value in plan.acts and "vehicle_choice" in plan.facts_to_acknowledge:
        label = plan.proven_vehicle_label
        if label:
            bubbles.append(f"Boa escolha, o {label}." if not es else f"Buena elección, el {label}.")
        else:
            bubbles.append("Boa escolha." if not es else "Buena elección.")
    if DialogueAct.ACKNOWLEDGE_FACT.value in plan.acts and "desired_installment" in plan.facts_to_acknowledge:
        bubbles.append(
            "Anotei uma parcela desejada, em reais."
            if not es
            else "Anoté una cuota deseada."
        )
    elif DialogueAct.ACKNOWLEDGE_FACT.value in plan.acts and "payment_method" in plan.facts_to_acknowledge:
        if "down_payment" not in kinds and DirectQuestionKind.FINANCING_100.value not in kinds:
            bubbles.append("Certo." if not es else "De acuerdo.")

    if DialogueAct.CONFIRM_VISIT.value in plan.acts:
        bubbles.append(
            "Perfeito, registrei sua preferência de visita."
            if not es
            else "Perfecto, registré tu preferencia de visita."
        )

    if plan.canonical_question and next_question and DialogueAct.ASK_NEXT_FIELD.value in plan.acts:
        bubbles.append(next_question)
    elif should_introduce and not plan.skip_generic_intent_menu and not plan.canonical_question:
        invite = (
            "Como posso te ajudar?"
            if not es
            else "¿Cómo puedo ayudarte?"
        )
        if invite not in bubbles:
            bubbles.append(invite)
    elif should_introduce and plan.skip_generic_intent_menu and not any("?" in b for b in bubbles):
        invite = (
            "Como posso te ajudar?"
            if not es
            else "¿Cómo puedo ayudarte?"
        )
        bubbles.append(invite)

    cleaned = [b.strip() for b in bubbles if isinstance(b, str) and b.strip()]
    # Merge if we produced too many short text bubbles.
    if len(cleaned) > plan.max_text_bubbles:
        head, tail = cleaned[: plan.max_text_bubbles - 1], cleaned[plan.max_text_bubbles - 1 :]
        cleaned = [*head, " ".join(tail)]
    return cleaned[: plan.max_text_bubbles]


def question_count(bubbles: Sequence[str]) -> int:
    return sum(str(b).count("?") for b in bubbles if b)


def reciprocity_present(text: str) -> bool:
    return bool(_RECIPROCITY.search(text or ""))
