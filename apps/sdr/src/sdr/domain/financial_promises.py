"""Safe financing disclaimer vs invented financial promise.

Outbound may offer a simulation without down payment and may say that
taxa/prazo depend on the lender. It must not assert approval, integral
financing as certain, a numeric rate, or a final installment.

Isolated ``taxa`` is not a promise. A numeric or guaranteed rate still is.
Detection is proposition-based (kind, polarity, modality, conditioning).
Regex is only complementary defense.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Promises the Composer must never produce. Isolated "taxa" is not enough.
_FORBIDDEN_FINANCIAL_PROMISE: tuple[re.Pattern[str], ...] = (
    re.compile(r"vou\s+reservar", re.I),
    re.compile(r"reservado\s+(?:para|pra)\s+você", re.I),
    re.compile(r"está\s+reservado", re.I),
    re.compile(r"deixar\s+reservado", re.I),
    re.compile(r"aprovação\s+garantida", re.I),
    re.compile(r"taxa\s+de\s+\d", re.I),
    re.compile(r"taxa\s+será\s+(?:de\s+)?\d", re.I),
    re.compile(r"tasa\s+será\s+(?:de\s+)?\d", re.I),
    re.compile(r"\b(?:taxa|tasa)\s+baixa\b", re.I),
    re.compile(r"conseguimos\s+uma\s+taxa", re.I),
    re.compile(r"negociar\s+uma\s+taxa\s+menor", re.I),
    re.compile(r"tasa\s+menor\s+para\s+ti", re.I),
    re.compile(r"aprovado\s+no\s+crédito", re.I),
    re.compile(r"financiamento\s+(?:está\s+)?aprovado", re.I),
    re.compile(r"100%\s+financiado", re.I),
    re.compile(r"financ\w*\s+100\s*%\s+com\s+certeza", re.I),
    re.compile(r"parcela\s+ficar[aá]\s+em\s+R\$", re.I),
    re.compile(r"sua\s+parcela\s+ficar[aá]", re.I),
    re.compile(r"100\s*%\s*(?:com\s+certeza|garantid)", re.I),
    re.compile(
        r"\b(?:taxa|interes[eé]s?)\s*(?:de\s*)?\d+(?:[.,]\d+)?\s*%",
        re.I,
    ),
    # Complementary: 100% financing as an outcome, not only "com certeza".
    re.compile(r"financ\w*\s+100\s*%(?!\d)", re.I),
    re.compile(r"\bbanco\s+aprova\b", re.I),
)

_SENTENCE_SPLIT = re.compile(r"[.!?]+|\n+")
_NEGATION = re.compile(r"\b(?:n[aã]o|nunca)\b", re.I)
_PROCESS_VERB = re.compile(
    r"\b(?:simula(?:r|ção|cao)|solicitar|analisar)\b",
    re.I,
)
_INTEGRAL_AMOUNT = re.compile(
    r"(?:100\s*%|"
    r"todo\s+o\s+valor|"
    r"(?:o\s+)?valor\s+(?:todo|integral|total|completo)|"
    r"el\s+valor\s+total)",
    re.I,
)
_FINANCING_OUTCOME = re.compile(
    r"\b(?:financi(?:ar|amos|a|ado|amento)|financiaremos)\b",
    re.I,
)
_CONDITIONING = re.compile(
    r"\b(?:sujeito|depende(?:m)?|an[aá]lise|condi[cç][oõ]es?\s+depend)\b",
    re.I,
)
_POSSIBILITY = re.compile(r"\b(?:pode(?:m)?|poss[ií]vel)\b", re.I)
_PREFERENCE = re.compile(
    r"\b(?:busca|buscas|tem\s+em\s+mente|em\s+torno|por\s+volta|desejad)",
    re.I,
)
_APPROVAL_CERTAIN = re.compile(
    r"(?:financiamento\s+(?:est[aá]\s+)?aprovad|"
    r"j[aá]\s+est[aá]\s+aprovad|"
    r"aprova[cç][aã]o\s+garantida|"
    r"aprovado\s+no\s+cr[eé]dito|"
    r"(?:o\s+)?banco\s+aprova|"
    r"aprova\s+sem\s+entrada|"
    r"100\s*%\s*garantid|"
    r"taxa\s+garantida|"
    r"vamos\s+financiar\s+(?:o\s+valor\s+)?(?:todo|tudo)|"
    r"financiaremos\s+el\s+valor\s+total|"
    r"financiar\s+o\s+valor\s+todo)",
    re.I,
)
_RATE_PROMISE = re.compile(
    r"(?:taxa|tasa|interes[eé]s?)\s*(?:ser[aá]\s+)?(?:de\s*)?\d|"
    r"\b(?:taxa|tasa)\s+baixa\b|"
    r"taxa\s+garantida|"
    r"conseguimos\s+uma\s+taxa|"
    r"negociar\s+uma\s+taxa\s+menor",
    re.I,
)
_INSTALLMENT_OUTCOME = re.compile(
    r"(?:sua\s+)?parcela\s+(?:ficar[aá]|fica|ser[aá]|sai)\b",
    re.I,
)
_LENDER_DEPENDENCY = re.compile(
    r"\b(?:taxa|tasa|prazo)\b.{0,48}\bdepende|"
    r"\bdepende(?:m)?\s+da\s+(?:an[aá]lise\s+da\s+)?financeira",
    re.I,
)
_SIMULATION = re.compile(
    r"\b(?:simula(?:r|ção|cao)|solicitar\s+simula)",
    re.I,
)


@dataclass(frozen=True)
class FinancialClaim:
    """A financing proposition extracted from outbound text."""

    kind: str
    polarity: str
    modality: str
    conditioned: bool
    span: str

    def is_forbidden_promise(self) -> bool:
        if self.polarity == "negated":
            return False
        if self.kind in {"simulation", "lender_dependency"}:
            return False
        if self.modality == "preference":
            return False
        if self.kind == "integral_financing":
            # Lender analysis/simulation of an integral amount is not an outcome.
            return self.modality != "process"
        if self.kind in {"approval", "bank_condition", "rate", "installment"}:
            return True
        return False


def _spans(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(raw) if part.strip()]
    if raw not in parts:
        parts.append(raw)
    return parts


def _claims_from_span(span: str) -> list[FinancialClaim]:
    polarity = "negated" if _NEGATION.search(span) else "asserted"
    conditioned = bool(_CONDITIONING.search(span))
    process = bool(_PROCESS_VERB.search(span))
    preference = bool(_PREFERENCE.search(span))
    claims: list[FinancialClaim] = []

    if _RATE_PROMISE.search(span):
        claims.append(
            FinancialClaim("rate", polarity, "certain", conditioned, span)
        )
    elif _LENDER_DEPENDENCY.search(span):
        claims.append(
            FinancialClaim("lender_dependency", polarity, "conditional", True, span)
        )

    if _INSTALLMENT_OUTCOME.search(span):
        modality = "preference" if preference else "certain"
        claims.append(
            FinancialClaim("installment", polarity, modality, conditioned, span)
        )
    elif preference and re.search(r"parcela", span, re.I):
        claims.append(
            FinancialClaim("installment", polarity, "preference", conditioned, span)
        )

    if _APPROVAL_CERTAIN.search(span):
        kind = "bank_condition" if re.search(r"\bbanco\b", span, re.I) else "approval"
        claims.append(
            FinancialClaim(kind, polarity, "certain", conditioned, span)
        )

    if _INTEGRAL_AMOUNT.search(span) and _FINANCING_OUTCOME.search(span):
        if process:
            modality = "process"
        elif conditioned and _POSSIBILITY.search(span):
            modality = "conditional"
        else:
            modality = "certain"
        claims.append(
            FinancialClaim(
                "integral_financing", polarity, modality, conditioned, span
            )
        )

    if _SIMULATION.search(span) and not _INTEGRAL_AMOUNT.search(span):
        claims.append(
            FinancialClaim(
                "simulation",
                polarity,
                "process",
                conditioned or bool(_POSSIBILITY.search(span)),
                span,
            )
        )

    return claims


def extract_financial_claims(text: str) -> list[FinancialClaim]:
    """Extract financing propositions with polarity, modality, and conditioning."""
    claims: list[FinancialClaim] = []
    for span in _spans(text):
        claims.extend(_claims_from_span(span))
    return claims


def contains_forbidden_financial_promise(text: str) -> bool:
    """True when outbound invents a rate, installment, approval, or reservation."""
    raw = text or ""
    if any(pattern.search(raw) for pattern in _FORBIDDEN_FINANCIAL_PROMISE):
        return True
    return any(claim.is_forbidden_promise() for claim in extract_financial_claims(raw))


def contains_financing_approval_claim(text: str) -> bool:
    """True when outbound asserts approval or integral financing as certain."""
    raw = text or ""
    if _APPROVAL_CERTAIN.search(raw):
        return True
    return any(
        claim.is_forbidden_promise()
        and claim.kind in {"approval", "integral_financing", "bank_condition"}
        for claim in extract_financial_claims(raw)
    )
