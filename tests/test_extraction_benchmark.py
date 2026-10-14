"""Scoring mechanics only. Fabricated gold-shaped objects are NOT model results."""
from copy import deepcopy
import hashlib

import pytest

from app.domain import fixture_catalog
from evals.extraction.score import load_corpus, score_case, score_records


def gold_shaped(item, label):
    frame = {"proposition_id": "p1", "speaker": label["speaker"], "speech_act": label["speech_act"]}
    for name, expected in label["fields"].items():
        if expected["state"] == "unknown":
            frame[name] = {"state": "unknown", "value": None, "provenance": []}
            continue
        quote = expected.get("surfaces", expected.get("support_fragments"))[0]
        start = item["text"].index(quote)
        value = {"surface": quote, "concept_id": None} if "surfaces" in expected and name != "attribution_text" else quote if "surfaces" in expected else expected["value"]
        frame[name] = {"state": "stated", "value": value, "provenance": [{"kind": "input_span", "quote": quote,
            "start": start, "end": start+len(quote), "input_hash": hashlib.sha256(item["text"].encode("utf-8")).hexdigest()}]}
    return {"case_id": item["case_id"], "wall_seconds": 0.01, "result": {"mode": "live", "system_status": "ok",
        "claim": {"propositions": [frame]}, "intent": {k: {"state": "stated", "value": v} for k, v in item["intent"].items()}}}


def test_frozen_partitions_have_exact_grounded_labels_and_novel_inputs():
    seen = {case["text"] for case in fixture_catalog()}
    for partition in ("development", "validation"):
        inputs, labels, manifest = load_corpus(partition)
        assert len(inputs) == len(labels) == 12
        assert manifest["partition_counts"][partition] == 12
        for item, label in zip(inputs, labels, strict=True):
            assert item["text"] not in seen
            seen.add(item["text"])
            for expected in label["fields"].values():
                for literal in expected.get("surfaces", [])+expected.get("support_fragments", []):
                    assert literal in item["text"]


def test_gold_shaped_scorer_control_passes_without_becoming_a_model_result():
    inputs, labels, manifest = load_corpus("development")
    result = score_records(inputs, labels, [gold_shaped(i, l) for i, l in zip(inputs, labels, strict=True)], manifest)
    assert result["engineering_gate_passed"]
    assert result["exact_case_success"] == {"correct": 12, "total": 12}


def test_unrelated_but_grounded_source_quote_is_not_a_population():
    inputs, labels, _ = load_corpus("development")
    item, label = inputs[1], labels[1]
    record = gold_shaped(item, label)
    frame = record["result"]["claim"]["propositions"][0]
    frame["population"] = deepcopy(frame["attribution_text"])
    frame["population"]["value"] = {"surface": frame["population"]["value"], "concept_id": None}
    scored = score_case(item, label, record)
    assert "population" in scored["critical_errors"]
    assert scored["span_errors"] == []


def test_correct_surface_with_an_unrelated_valid_quote_is_not_grounded():
    inputs, labels, _ = load_corpus("development")
    record = gold_shaped(inputs[1], labels[1])
    frame = record["result"]["claim"]["propositions"][0]
    frame["population"]["provenance"] = deepcopy(frame["attribution_text"]["provenance"])
    scored = score_case(inputs[1], labels[1], record)
    assert not scored["field_checks"]["population"]
    assert "population" in scored["critical_errors"]


def test_negation_error_and_invented_unknown_do_not_pass_schema_only_scoring():
    inputs, labels, _ = load_corpus("development")
    record = gold_shaped(inputs[2], labels[2])
    record["result"]["claim"]["propositions"][0]["polarity"]["value"] = "affirmed"
    assert "polarity" in score_case(inputs[2], labels[2], record)["critical_errors"]
    record = gold_shaped(inputs[4], labels[4])
    frame = record["result"]["claim"]["propositions"][0]
    frame["population"] = deepcopy(frame["intervention"])
    assert score_case(inputs[4], labels[4], record)["invented_unknown_fields"] == 1


def test_unicode_span_corruption_is_detected():
    inputs, labels, _ = load_corpus("development")
    record = gold_shaped(inputs[-1], labels[-1])
    record["result"]["claim"]["propositions"][0]["intervention"]["provenance"][0]["start"] += 1
    assert "intervention" in score_case(inputs[-1], labels[-1], record)["span_errors"]


def test_missing_timeout_and_duplicate_predictions_cannot_shrink_denominators():
    inputs, labels, manifest = load_corpus("development")
    result = score_records(inputs, labels, [], manifest)
    assert result["case_count"] == 12
    assert result["operational_failures"] == 12
    assert not result["engineering_gate_passed"]
    records = [gold_shaped(i, l) for i, l in zip(inputs, labels, strict=True)]
    records[0]["wall_seconds"] = 10.01
    assert not score_records(inputs, labels, records, manifest)["engineering_gate_passed"]
    with pytest.raises(ValueError):
        score_records(inputs, labels, records+[records[0]], manifest)
