"""Offline admission checks for the required nullable slot wire contract."""
from copy import deepcopy
import hashlib
from typing import get_args
import unicodedata

import pytest
from pydantic import ValidationError

from services.api.app import domain
from services.api.app.contracts import CompactExtractedField
from services.api.app.slot_extraction import (
    SLOT_FIELDS, SlotExtractionCandidate, SlotProposition, SlotQuote, expand_slot_claim,
)


INTENT = {
    "action_kind": "learn", "actor": "hypothetical",
    "current_care_relationship": "unrelated", "endorsement": "rejects",
}


def quote(text, occurrence=None, **extra):
    return {"quote": text, "occurrence": occurrence, **extra}


def proposition(**changes):
    return {"speaker": "user", "speech_act": "assertion",
            **{name: None for name in SLOT_FIELDS}, **changes}


def payload(**changes):
    return {"propositions": [proposition(**changes)]}


def test_every_existing_compact_slot_is_required_but_nullable():
    assert set(SLOT_FIELDS) == set(get_args(CompactExtractedField.model_fields["name"].annotation))
    assert len(SLOT_FIELDS) == 17
    schema = SlotProposition.model_json_schema()
    assert set(schema["required"]) == {"speaker", "speech_act", *SLOT_FIELDS}
    assert set(SlotQuote.model_json_schema()["required"]) == {"quote", "occurrence"}
    SlotExtractionCandidate.model_validate(payload())


@pytest.mark.parametrize("missing", ["speaker", "speech_act", *SLOT_FIELDS])
def test_missing_slot_keys_do_not_silently_become_unknown(missing):
    raw = payload()
    del raw["propositions"][0][missing]
    with pytest.raises(domain.DomainError, match="invalid slot extraction"):
        expand_slot_claim("A fictional statement.", raw, INTENT)


@pytest.mark.parametrize("name,bad", [
    ("relation", "causes"), ("polarity", "positive"),
    ("certainty", "certain"), ("generalization", "everyone"),
])
def test_classification_values_are_typed_not_free_text(name, bad):
    with pytest.raises(domain.DomainError, match="invalid slot extraction"):
        expand_slot_claim("A fictional statement.", payload(**{name: quote("fictional", value=bad)}), INTENT)


@pytest.mark.parametrize("occurrence", [-1, 100, True, "1", 1.5])
def test_occurrence_is_a_bounded_integer_or_explicit_null(occurrence):
    with pytest.raises(ValidationError):
        SlotQuote.model_validate(quote("fictional", occurrence))


def test_quote_shape_rejects_missing_occurrence_extras_empty_and_oversize():
    for raw in ({"quote": "text"}, quote(""), quote("x" * 601), quote("text", value="different")):
        with pytest.raises(ValidationError):
            SlotQuote.model_validate(raw)


@pytest.mark.parametrize("count", [0, 4])
def test_proposition_count_is_bounded(count):
    with pytest.raises(domain.DomainError, match="invalid slot extraction"):
        expand_slot_claim("A fictional statement.", {"propositions": [proposition()] * count}, INTENT)


def test_model_cannot_supply_ids_intent_or_unresolved_metadata():
    for raw in (
        payload(proposition_id="chosen-by-model"),
        {**payload(), "intent_candidate": {"endorsement": "supports"}},
        {**payload(), "unresolved_fields": []},
    ):
        with pytest.raises(domain.DomainError, match="invalid slot extraction"):
            expand_slot_claim("A fictional statement.", raw, INTENT)


def test_literals_and_classifications_expand_with_original_provenance_and_separate_intent():
    text = "A fictional note says indigo lamps may reduce timing errors in table-top robots."
    predicate = "may reduce timing errors"
    raw = payload(
        speaker="quoted_source", speech_act="reported_assertion",
        attribution_text=quote("A fictional note"), population=quote("table-top robots"),
        intervention=quote("indigo lamps"), measured_outcome=quote("timing errors"),
        relation=quote(predicate, value="causal"), polarity=quote(predicate, value="affirmed"),
        certainty=quote(predicate, value="possible"),
    )
    original, intent = deepcopy(raw), deepcopy(INTENT)
    result = expand_slot_claim(text, raw, intent)
    assert raw == original and intent == INTENT
    assert result["mode"] == "live" and result["system_status"] == "ok"
    assert result["case_state"] == "needs_confirmation"
    p = result["claim"]["propositions"][0]
    assert p["proposition_id"] == "p1" and p["speaker"] == "quoted_source"
    assert p["population"]["value"]["surface"] == "table-top robots"
    assert p["attribution_text"]["value"] == "A fictional note"
    assert p["polarity"]["value"] == "affirmed" and p["certainty"]["value"] == "possible"
    assert p["comparator"]["state"] == "unknown" and p["comparator"]["value"] is None
    assert "comparator" in result["claim"]["unresolved_fields"]
    assert "population" not in result["claim"]["unresolved_fields"]
    for name, slot in raw["propositions"][0].items():
        if name not in SLOT_FIELDS or slot is None:
            continue
        origin = p[name]["provenance"][0]
        assert text[origin["start"]:origin["end"]] == slot["quote"]
        assert origin["input_hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    for name, value in INTENT.items():
        assert result["intent"][name]["value"] == value


def test_absent_or_case_changed_quotes_are_rejected():
    for wrong in ("invented lamps", "Indigo lamps"):
        with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
            expand_slot_claim("indigo lamps may help robots.", payload(intervention=quote(wrong)), INTENT)


@pytest.mark.parametrize("name", [
    '\u201clime\u201d sleeves', "'lime' sleeves", 'lime\u2014green sleeves',
    'li\u0301me sleeves', 'lime\r\ngreen sleeves',
])
def test_named_literal_preserves_internal_punctuation_marks_and_line_breaks(name):
    text = f"Fictional {name} increase wheel steadiness."
    raw = payload(intervention=quote(name))
    result = expand_slot_claim(text, raw, INTENT)
    origin = result['claim']['propositions'][0]['intervention']['provenance'][0]
    assert text[origin['start']:origin['end']] == name == origin['quote']
    assert origin['input_hash'] == hashlib.sha256(text.encode('utf-8')).hexdigest()


@pytest.mark.parametrize("name,changed", [
    ('\u201clime\u201d sleeves', 'lime sleeves'),
    ("'lime' sleeves", 'lime sleeves'),
    ('lime\u2014green sleeves', 'lime-green sleeves'),
    ('lime\r\ngreen sleeves', 'lime green sleeves'),
])
def test_typographic_cleanup_never_becomes_an_admitted_literal(name, changed):
    with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
        expand_slot_claim(f"Fictional {name} increase wheel steadiness.",
                          payload(intervention=quote(changed)), INTENT)


def test_repeated_quote_requires_occurrence_and_resolves_the_selected_original_span():
    text = "Indigo lamps differ from indigo lamps; indigo lamps remain fictional."
    with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
        expand_slot_claim(text, payload(intervention=quote("indigo lamps")), INTENT)
    with pytest.raises(domain.DomainError, match="invalid quote occurrence"):
        expand_slot_claim(text, payload(intervention=quote("indigo lamps", 2)), INTENT)
    result = expand_slot_claim(text, payload(intervention=quote("indigo lamps", 1)), INTENT)
    origin = result["claim"]["propositions"][0]["intervention"]["provenance"][0]
    assert origin["start"] == text.rindex("indigo lamps")


def test_unicode_values_are_nfc_while_quotes_hashes_and_offsets_remain_original():
    text = "🧩 Cafe\u0301 lamps help fictional robots.\r\n"
    literal = "Cafe\u0301 lamps"
    result = expand_slot_claim(text, payload(intervention=quote(literal)), INTENT)
    field = result["claim"]["propositions"][0]["intervention"]
    assert field["value"]["surface"] == unicodedata.normalize("NFC", literal)
    origin = field["provenance"][0]
    assert origin["start"] == 2 and origin["quote"] == literal
    assert origin["end"] == 2 + len(literal)
    assert text[origin["start"]:origin["end"]] == literal
    assert result["claim"]["original_text"] == text
    assert result["claim"]["normalized_text"] == unicodedata.normalize("NFC", text).replace("\r\n", "\n")
    canonical = expand_slot_claim(text, payload(intervention=quote("Café lamps")), INTENT)
    assert canonical["claim"]["propositions"][0]["intervention"] == field


def test_all_null_ambiguous_proposition_is_retained_and_cannot_authorize_assessment():
    result = expand_slot_claim("It made things better for them.", payload(), INTENT)
    p = result["claim"]["propositions"][0]
    for name in SLOT_FIELDS:
        assert p[name]["state"] == "unknown" and p[name]["value"] is None
        assert p[name]["provenance"] == []
    assert result["claim"]["unresolved_fields"] == list(SLOT_FIELDS)
    assert p["timeframe"]["state"] == "unknown"  # Full IR fields outside the wire stay intact.
    confirmed = domain.confirm(result["claim"], result["intent"])
    assessment = domain.assess(confirmed["snapshot"], confirmed["intent"])
    assert assessment["route"] == "clarify"
    assert assessment["evidence_status"] == "not_assessable" and not assessment["save_eligible"]


def test_explicit_population_survives_a_missing_outcome_and_other_unknowns():
    text = "For miniature robots, indigo lamps may help."
    result = expand_slot_claim(text, payload(
        population=quote("miniature robots"), intervention=quote("indigo lamps"),
        relation=quote("may help", value="causal"), polarity=quote("may help", value="affirmed"),
        certainty=quote("may help", value="possible"),
    ), INTENT)
    p = result["claim"]["propositions"][0]
    assert p["population"]["value"]["surface"] == "miniature robots"
    assert p["measured_outcome"]["state"] == "unknown"
    assert "measured_outcome" in result["claim"]["unresolved_fields"]
    assert "population" not in result["claim"]["unresolved_fields"]
    confirmed = domain.confirm(result["claim"], result["intent"])
    assert not domain.assess(confirmed["snapshot"], confirmed["intent"])["save_eligible"]


def test_slot_expansion_retains_the_compact_paths_normalized_ir_and_admission_limits():
    text = "Indigo lamps do not improve recall in miniature robots."
    slots = payload(
        population=quote("miniature robots"), intervention=quote("Indigo lamps"),
        measured_outcome=quote("recall"), relation=quote("do not improve recall", value="causal"),
        polarity=quote("do not improve recall", value="negated"),
    )
    fields = []
    for name in SLOT_FIELDS:
        item = slots["propositions"][0][name]
        if item is not None:
            fields.append({"name": name, "value": item.get("value", item["quote"]),
                           "quote": item["quote"], "occurrence": item["occurrence"]})
    compact = {"propositions": [{"proposition_id": "p1", "speaker": "user",
                "speech_act": "assertion", "fields": fields}]}
    expected = domain.expand_compact_claim(text, compact, INTENT)
    actual = expand_slot_claim(text, slots, INTENT)
    assert actual["claim"]["propositions"] == expected["claim"]["propositions"]
    for name in ("case_state", "route", "system_status", "mode", "synthetic_label"):
        assert actual[name] == expected[name]

    # Wire quotes may be longer than a concept surface; the existing full IR
    # still rejects values beyond its tighter 160-character concept limit.
    too_long = "z" * 161
    with pytest.raises(domain.DomainError, match="invalid claim schema"):
        expand_slot_claim(too_long, payload(intervention=quote(too_long)), INTENT)


def test_three_propositions_get_server_ids_and_unresolved_names_stay_bounded():
    result = expand_slot_claim(
        "Three ambiguous fictional statements.", {"propositions": [proposition() for _ in range(3)]}, INTENT,
    )
    assert [p["proposition_id"] for p in result["claim"]["propositions"]] == ["p1", "p2", "p3"]
    assert result["claim"]["unresolved_fields"] == list(SLOT_FIELDS)


@pytest.mark.parametrize("literal", [
    "It", "itself", "they", "them", "theirs", "themselves", "he", "him", "his",
    "she", "her", "herself", "this", "that", "these", "those",
    "this one", "that thing", "these ones", "those things", "these\nthings",
    "something", "anything", "everything", "nothing", "somebody", "someone",
    "anyone", "nobody", "no one", "none", "something else", "anybody else",
])
@pytest.mark.parametrize("name", ["population", "intervention", "measured_outcome"])
def test_bare_pronominal_core_references_become_ambiguous_after_literal_validation(name, literal):
    text = f"A fictional note contains {literal}."
    result = expand_slot_claim(text, payload(**{name: quote(literal)}), INTENT)
    field = result["claim"]["propositions"][0][name]
    assert field["state"] == "ambiguous" and field["value"] is None
    assert field["reason_code"] == "unresolved_reference"
    assert name in result["claim"]["unresolved_fields"]
    origin = field["provenance"][0]
    assert text[origin["start"]:origin["end"]] == literal
    assert origin["input_hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("literal", [
    "these miniature robots", "this lamp", "those red cards", "Something New lamps",
    "Anything Company", "Themselves Club", "Noone", "IT systems", "items", "objects", "things",
    "the robot", "another lamp", "everyone in the robot club", "a thing called Indigo",
])
def test_pronoun_guard_does_not_match_inside_ordinary_entity_noun_phrases(literal):
    text = f"A fictional claim mentions {literal}."
    result = expand_slot_claim(text, payload(population=quote(literal)), INTENT)
    field = result["claim"]["propositions"][0]["population"]
    assert field["state"] == "stated" and field["value"]["surface"] == literal
    assert "population" not in result["claim"]["unresolved_fields"]


def test_pronoun_guard_keeps_other_grounded_fields_and_does_not_resolve_an_antecedent():
    text = "Indigo lamps are fictional. They may improve timing in robots."
    result = expand_slot_claim(text, payload(
        intervention=quote("They"), population=quote("robots"), measured_outcome=quote("timing"),
        relation=quote("may improve timing", value="causal"),
        polarity=quote("may improve timing", value="affirmed"),
        certainty=quote("may improve timing", value="possible"),
    ), INTENT)
    p = result["claim"]["propositions"][0]
    assert p["intervention"]["state"] == "ambiguous" and p["intervention"]["value"] is None
    assert p["population"]["value"]["surface"] == "robots"
    assert p["measured_outcome"]["value"]["surface"] == "timing"
    assert p["certainty"]["value"] == "possible"
    assert p["comparator"]["state"] == "unknown" and p["comparator"]["provenance"] == []
    confirmed = domain.confirm(result["claim"], result["intent"])
    assert not domain.assess(confirmed["snapshot"], confirmed["intent"])["save_eligible"]


def test_pronoun_guard_does_not_repair_nonexistent_case_changed_or_ambiguous_quotes():
    for text, literal, occurrence in (
        ("A fictional lamp helps robots.", "them", None),
        ("It helps robots.", "it", None),
        ("It helps. It changes.", "It", None),
    ):
        with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
            expand_slot_claim(text, payload(intervention=quote(literal, occurrence)), INTENT)
    with pytest.raises(domain.DomainError, match="invalid quote occurrence"):
        expand_slot_claim("It helps.", payload(intervention=quote("It", 1)), INTENT)
    result = expand_slot_claim("It helps. It changes.", payload(intervention=quote("It", 1)), INTENT)
    field = result["claim"]["propositions"][0]["intervention"]
    assert field["state"] == "ambiguous" and field["provenance"][0]["start"] == 10


def test_pronoun_guard_is_limited_to_the_three_core_literal_slots():
    text = "A fictional note quotes this."
    result = expand_slot_claim(text, payload(speaker="quoted_source", speech_act="reported_assertion",
                                             attribution_text=quote("this")), INTENT)
    field = result["claim"]["propositions"][0]["attribution_text"]
    assert field["state"] == "stated" and field["value"] == "this"


@pytest.mark.parametrize("original,model_quote", [
    ("Cafe\u0301 lamps", "Café lamps"),
    ("Café lamps", "Cafe\u0301 lamps"),
    ("a\u0315\u0300 lamps", "à\u0315 lamps"),
    ("\u1100\u1161\u11a8 lamps", "각 lamps"),
    ("가\u11a8 lamps", "각 lamps"),
    ("Å lamps", "Å lamps"),  # Canonical singleton, not compatibility folding.
    ("q\u0344 lamps", "q\u0308\u0301 lamps"),  # NFC can expand one code point.
    ("👩‍🔬 Cafe\u0301 lamps", "👩‍🔬 Café lamps"),
    ("👍🏽 Cafe\u0301 lamps", "👍🏽 Café lamps"),
    ("🇸🇬 Cafe\u0301 lamps", "🇸🇬 Café lamps"),
    ("Cafe\u0301\r\nlamps", "Café\r\nlamps"),
])
def test_canonical_equivalence_preserves_original_slice_offsets_hash_and_candidate(original, model_quote):
    text = "🧩 Before: " + original + "; after."
    raw = payload(intervention=quote(model_quote))
    unchanged = deepcopy(raw)
    result = expand_slot_claim(text, raw, INTENT)
    field = result["claim"]["propositions"][0]["intervention"]
    origin = field["provenance"][0]
    assert raw == unchanged
    assert origin == {"kind": "input_span", "input_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "start": len("🧩 Before: "), "end": len("🧩 Before: ") + len(original), "quote": original}
    assert field["value"]["surface"] == unicodedata.normalize("NFC", original)
    assert text[origin["start"]:origin["end"]] == original


@pytest.mark.parametrize("original,model_quote", [
    ("Cafe\u0301 lamps", "café lamps"),
    ("Ｃafe\u0301 lamps", "Café lamps"),
    ("ﬀ Cafe\u0301 lamps", "ff Café lamps"),
    ("Cafe\u0301\u00a0lamps", "Café lamps"),
    ("Cafe\u0301  lamps", "Café lamps"),
    ("Cafe\u0301\r\nlamps", "Café\nlamps"),
    ("Cafe\u0301 lamps", "Café invented lamps"),
    ("Cafe\u0301 lamps", "Café…lamps"),
])
def test_nfc_fallback_never_folds_case_compatibility_whitespace_or_invents_text(original, model_quote):
    with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
        expand_slot_claim(original, payload(intervention=quote(model_quote)), INTENT)


@pytest.mark.parametrize("original,model_quote", [
    ("Cafe\u0301\u0327 lamps", "Café"),
    ("Cafe\u0301👩‍🔬", "Café👩"),
    ("Cafe\u0301👍🏽", "Café👍"),
    ("Cafe\u0301🇸🇬", "Café🇸"),
    ("Cafe\u0301🇸🇬🇨🇦", "Café🇸🇬"),  # RI runs are conservatively indivisible.
    ("Cafe\u0301 1️⃣", "Café 1"),
    ("Cafe\u0301\r\n", "Café\r"),
    ("\u1100\u1161\u11a8", "가"),
    ("\u0344", "\u0308"),
    ("Cafe\u0301 क्क", "Café क"),  # No guessed interior Indic boundary.
    ("Cafe\u0301 \u0d4eക", "Café \u0d4e"),  # Unsupported Prepend letter.
])
def test_nfc_fallback_rejects_partial_or_unsupported_unit_boundaries(original, model_quote):
    with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
        expand_slot_claim(original, payload(intervention=quote(model_quote)), INTENT)


def test_exact_match_priority_and_occurrence_numbering_are_not_broadened_by_nfc():
    text = "Cafe\u0301 lamps then Café lamps."
    result = expand_slot_claim(text, payload(intervention=quote("Café lamps")), INTENT)
    origin = result["claim"]["propositions"][0]["intervention"]["provenance"][0]
    assert origin["start"] == text.index("Café lamps") and origin["quote"] == "Café lamps"
    with pytest.raises(domain.DomainError, match="invalid quote occurrence"):
        expand_slot_claim(text, payload(intervention=quote("Café lamps", 1)), INTENT)
    # Existing exact substring behavior is preserved; only fallback is hardened.
    exact = expand_slot_claim("Cafe\u0301", payload(intervention=quote("Cafe")), INTENT)
    assert exact["claim"]["propositions"][0]["intervention"]["provenance"][0]["quote"] == "Cafe"


def test_nfc_occurrence_selects_original_variants_and_rejects_ambiguity():
    originals = ["a\u0315\u0300 lamps", "à\u0315 lamps"]
    text, model_quote = " / ".join(originals), "a\u0300\u0315 lamps"
    with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
        expand_slot_claim(text, payload(intervention=quote(model_quote)), INTENT)
    for occurrence, original in enumerate(originals):
        result = expand_slot_claim(text, payload(intervention=quote(model_quote, occurrence)), INTENT)
        origin = result["claim"]["propositions"][0]["intervention"]["provenance"][0]
        assert origin["quote"] == original and origin["start"] == text.index(original)
    with pytest.raises(domain.DomainError, match="invalid quote occurrence"):
        expand_slot_claim(text, payload(intervention=quote(model_quote, 2)), INTENT)


def test_invalid_partial_nfc_match_cannot_hide_a_later_overlapping_valid_occurrence():
    text, model_quote = "éé \u200dééé", "e\u0301e\u0301"
    with pytest.raises(domain.DomainError, match="quote missing or ambiguous"):
        expand_slot_claim(text, payload(intervention=quote(model_quote)), INTENT)
    for occurrence, start in enumerate((0, 5)):
        result = expand_slot_claim(text, payload(intervention=quote(model_quote, occurrence)), INTENT)
        origin = result["claim"]["propositions"][0]["intervention"]["provenance"][0]
        assert origin["start"] == start and origin["end"] == start + 2
        assert origin["quote"] == "éé"


def test_nfc_index_is_built_once_at_maximum_input_and_existing_bounds_remain(monkeypatch):
    from services.api.app import slot_extraction
    original = slot_extraction._nfc_span_index
    calls = []
    def counted(text):
        calls.append(len(text))
        return original(text)
    monkeypatch.setattr(slot_extraction, "_nfc_span_index", counted)
    literal = "Cafe\u0301 lamps"
    text = "x" * (6000 - len(literal)) + literal
    result = expand_slot_claim(text, payload(intervention=quote("Café lamps"), population=quote("Café lamps")), INTENT)
    assert calls == [6000]
    assert result["claim"]["propositions"][0]["intervention"]["provenance"][0]["quote"] == literal
    with pytest.raises(domain.DomainError):
        expand_slot_claim(text + "x", payload(intervention=quote("Café lamps")), INTENT)
    assert calls == [6000]
    # Normalized short wire text cannot bypass the original provenance limit.
    with pytest.raises(domain.DomainError, match="invalid claim schema"):
        expand_slot_claim("e\u0301" * 301, payload(attribution_text=quote("é" * 301),
                         speaker="quoted_source", speech_act="reported_assertion"), INTENT)


@pytest.mark.parametrize("speaker,speech_act,source", [
    ("user", "assertion", "A note"),
    ("unknown", "assertion", "A note"),
    ("user", "reported_assertion", None),
])
def test_inconsistent_attribution_is_semantically_rejected_without_relabeling(speaker, speech_act, source):
    raw = payload(speaker=speaker, speech_act=speech_act,
                  attribution_text=quote(source) if source else None)
    unchanged = deepcopy(raw)
    with pytest.raises(domain.DomainError, match="inconsistent claim attribution"):
        expand_slot_claim("A note asks whether lamps help.", raw, INTENT)
    assert raw == unchanged


@pytest.mark.parametrize("speaker,speech_act,source", [
    ("quoted_source", "question", "A note"),
    ("quoted_source", "reported_assertion", None),
    ("unknown", "reported_assertion", None),
    ("user", "assertion", None),
])
def test_consistent_question_unknown_source_and_direct_assertion_keep_their_classifications(speaker, speech_act, source):
    result = expand_slot_claim("A note asks whether lamps help.", payload(
        speaker=speaker, speech_act=speech_act, attribution_text=quote(source) if source else None), INTENT)
    frame = result["claim"]["propositions"][0]
    assert frame["speaker"] == speaker and frame["speech_act"] == speech_act
