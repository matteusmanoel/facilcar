"""Phase 12 consolidated corpus — existing goldens, no duplicated journeys.

The 17 commercial journeys stay in tests/golden/scenarios/.
Contracts 18–31 are proven by Phase 9–11 goldens already in-tree.
Do not inflate the file count just to reach 31.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios"
PHASE9 = ROOT / "phase9"
PHASE9R = ROOT / "phase9r"
PHASE10 = ROOT / "phase10"
PHASE10R = ROOT / "phase10r"
PHASE11 = ROOT / "phase11"

CORE_17: tuple[str, ...] = (
    "compra_avista",
    "compra_financiada_com_entrada",
    "compra_financiada_sem_entrada",
    "troca_quitada",
    "troca_financiada",
    "troca_com_debitos",
    "venda_direta",
    "consignacao",
    "refinanciamento",
    "civic_vendido_foto",
    "gol_nao_encontrado",
    "fox_peugeot_troca",
    "pedido_de_vendedor",
    "agendamento_semana",
    "agendamento_sabado",
    "whatsapp_fox_image_financing_burst_visit",
    "whatsapp_strada_quoted_primary_financing_visit",
)

# gate_id, relative path from apps/sdr/tests/golden
HIGH_RISK: tuple[tuple[str, Path], ...] = (
    ("HR1_fox_burst", SCENARIOS / "whatsapp_fox_image_financing_burst_visit.json"),
    ("HR2_strada_quoted", SCENARIOS / "whatsapp_strada_quoted_primary_financing_visit.json"),
    ("HR3_cnh_partial", PHASE9 / "p9_07_somente_cnh.json"),
    ("HR4_docs_callback", PHASE11 / "g1_documents_tomorrow_14h.json"),
    ("HR5_spouse", PHASE11 / "g2_spouse_without_time.json"),
    ("HR6_unsafe_question", PHASE9 / "p9_15_item_sem_informacao_segura.json"),
    ("HR7_post_handoff", PHASE10R / "g1_document_after_handoff.json"),
    ("HR8_human_cancel", PHASE11 / "g4_human_assume.json"),
    ("HR9_opt_out", PHASE11 / "g5_opt_out.json"),
    ("HR10_sold_before_followup", PHASE11 / "g8_vehicle_sold.json"),
)

# Extra files for full regression (not already in CORE_17).
REGRESSION_EXTRA: tuple[Path, ...] = (
    PHASE9 / "p9_06_parcela_informada.json",
    PHASE9 / "p9_07_somente_cnh.json",
    PHASE9 / "p9_09_documentos_indisponiveis.json",
    PHASE9 / "p9_10_todos_documentos.json",
    PHASE9 / "p9_11_vendedor_durante_documentos.json",
    PHASE9 / "p9_12_visita_durante_documentos.json",
    PHASE9 / "p9_15_item_sem_informacao_segura.json",
    PHASE9R / "g6_qual_taxa.json",
    PHASE10 / "p10_02_assume_resume.json",
    PHASE10 / "p10_04_crm_same_lead.json",
    PHASE10R / "g1_document_after_handoff.json",
    PHASE11 / "g1_documents_tomorrow_14h.json",
    PHASE11 / "g2_spouse_without_time.json",
    PHASE11 / "g3_reply_before_due.json",
    PHASE11 / "g4_human_assume.json",
    PHASE11 / "g5_opt_out.json",
    PHASE11 / "g8_vehicle_sold.json",
    PHASE11 / "g9_dormant_after_followup.json",
    PHASE11 / "g10_post_handoff_before_human.json",
)

# contract_id -> (label, proving files)
COVERAGE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("01", "compra à vista", ("compra_avista",)),
    ("02", "compra financiada com entrada", ("compra_financiada_com_entrada",)),
    ("03", "compra financiada sem entrada", ("compra_financiada_sem_entrada",)),
    ("04", "troca quitada", ("troca_quitada",)),
    ("05", "troca financiada", ("troca_financiada",)),
    ("06", "troca com débitos", ("troca_com_debitos",)),
    ("07", "venda direta", ("venda_direta",)),
    ("08", "consignação", ("consignacao",)),
    ("09", "refinanciamento", ("refinanciamento",)),
    ("10", "civic vendido + foto", ("civic_vendido_foto",)),
    ("11", "gol não encontrado", ("gol_nao_encontrado",)),
    ("12", "fox + peugeot troca", ("fox_peugeot_troca",)),
    ("13", "pedido de vendedor", ("pedido_de_vendedor", "p9_11_vendedor_durante_documentos")),
    ("14", "agendamento semana", ("agendamento_semana",)),
    ("15", "agendamento sábado", ("agendamento_sabado",)),
    ("16", "fox texto+imagem+financiamento burst", ("whatsapp_fox_image_financing_burst_visit",)),
    ("17", "reply Strada 2018 + financiamento", ("whatsapp_strada_quoted_primary_financing_visit",)),
    ("18", "financiamento só com CNH", ("p9_07_somente_cnh",)),
    ("19", "documentos adiados sem callback", ("p9_09_documentos_indisponiveis",)),
    ("20", "callback explícito para documentos", ("g1_documents_tomorrow_14h",)),
    ("21", "pacote documental completo", ("p9_10_todos_documentos",)),
    ("22", "visita durante coleta documental", ("p9_12_visita_durante_documentos",)),
    ("23", "pedido de vendedor durante documentos", ("p9_11_vendedor_durante_documentos",)),
    ("24", "decisão com cônjuge + follow-up contextual", ("g2_spouse_without_time",)),
    ("25", "silêncio depois da parcela", ("p9_06_parcela_informada", "g9_dormant_after_followup")),
    ("26", "follow-up cancelado por resposta", ("g3_reply_before_due",)),
    ("27", "follow-up cancelado por humano", ("g4_human_assume",)),
    ("28", "nova informação depois do handoff", ("g1_document_after_handoff", "g10_post_handoff_before_human")),
    ("29", "opt-out com tarefa pendente", ("g5_opt_out",)),
    ("30", "veículo vendido antes do follow-up", ("g8_vehicle_sold",)),
    ("31", "assunção e resume só para futuros inbounds", ("p10_02_assume_resume",)),
)


def core_paths() -> list[Path]:
    return [SCENARIOS / f"{name}.json" for name in CORE_17]


def regression_paths() -> list[Path]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in (*core_paths(), *REGRESSION_EXTRA):
        key = path.resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def high_risk_cases() -> list[tuple[str, Path]]:
    return [(gate_id, path) for gate_id, path in HIGH_RISK]
