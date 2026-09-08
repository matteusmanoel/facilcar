"""Safe financing disclaimer vs invented financial promise.

The word ``taxa`` in a lender-dependency disclaimer is not a promise.
A numeric or guaranteed rate still is.
"""

from __future__ import annotations

import re

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
)


def contains_forbidden_financial_promise(text: str) -> bool:
    """True when outbound invents a rate, installment, approval, or reservation."""
    raw = text or ""
    return any(pattern.search(raw) for pattern in _FORBIDDEN_FINANCIAL_PROMISE)
