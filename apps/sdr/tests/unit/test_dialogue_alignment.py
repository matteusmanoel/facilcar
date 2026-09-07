"""Next customer turn must answer Júlia's last question."""

from __future__ import annotations

from sdr.domain.dialogue_alignment import (
    evaluate_dialogue_alignment,
    inbound_answers_field,
)


def test_next_turn_answers_ask_field() -> None:
    report = evaluate_dialogue_alignment(
        expected_question_field="name",
        detected_question_field="name",
        inbound="Me chamo Débora Martins",
        turn_def={"responds_to_field": "name"},
    )
    assert report["dialogue_alignment"] is True
    assert report["next_customer_response_type"] == "name"
    assert inbound_answers_field("Me chamo Débora Martins", "name")


def test_voluntary_fact_is_allowed() -> None:
    report = evaluate_dialogue_alignment(
        expected_question_field="name",
        detected_question_field="name",
        inbound="Sem débitos, espero 75 mil",
        turn_def={"response_mode": "voluntary_fact"},
    )
    assert report["dialogue_alignment"] is True


def test_intent_change_is_allowed() -> None:
    report = evaluate_dialogue_alignment(
        expected_question_field="name",
        detected_question_field="name",
        inbound="Na verdade quero vender meu carro",
        turn_def={"response_mode": "intent_change"},
    )
    assert report["dialogue_alignment"] is True


def test_incompatible_reply_fails() -> None:
    report = evaluate_dialogue_alignment(
        expected_question_field="name",
        detected_question_field="name",
        inbound="Sim, aceito deixar na loja",
        turn_def={"responds_to_field": "leave_at_store"},
    )
    assert report["dialogue_alignment"] is False


def test_consignment_opening_is_intent_not_leave_reply() -> None:
    report = evaluate_dialogue_alignment(
        expected_question_field=None,
        detected_question_field=None,
        inbound="Quero deixar meu carro em consignação na FacilCar",
        turn_def={"response_mode": "intent_change"},
    )
    assert report["dialogue_alignment"] is True
    later = evaluate_dialogue_alignment(
        expected_question_field="name",
        detected_question_field="name",
        inbound="Me chamo Débora Martins",
        turn_def={"responds_to_field": "name"},
    )
    assert later["dialogue_alignment"] is True
