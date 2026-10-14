"""Verify this frozen corpus and scorer with fabricated gold-shaped objects only.

No provider or model is invoked. Gold-shaped predictions remain in memory and
are never written to a model-results file. This does not measure model quality.
Run from the repository root with the project Python environment.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unicodedata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "services/api"))

from app.domain import expand_compact_claim
from evals.extraction.score import load_corpus, score_case, score_records


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gold_shaped(item, label):
    fields = []
    for name, expected in label["fields"].items():
        if expected["state"] == "unknown":
            continue
        quote = expected.get("surfaces", expected.get("support_fragments"))[0]
        fields.append({"name": name, "value": expected.get("surfaces", [expected.get("value")])[0],
                       "quote": quote, "occurrence": 0 if item["text"].count(quote) > 1 else None})
    candidate = {"propositions": [{"proposition_id": "p1", "speaker": label["speaker"],
        "speech_act": label["speech_act"], "fields": fields}],
        "unresolved_fields": [name for name, expected in label["fields"].items() if expected["state"] == "unknown"]}
    # This is the production converter only, supplied fabricated expected data.
    # Its normalized mode field is not evidence of a model execution.
    result = expand_compact_claim(item["text"], candidate, item["intent"])
    return {"case_id": item["case_id"], "wall_seconds": 0.01, "result": result}


def main():
    inputs, labels, manifest = load_corpus("validation", root=HERE)
    original = json.loads((REPO / "evals/extraction/manifest.json").read_text(encoding="utf-8"))
    development = [json.loads(line) for line in (REPO / "evals/extraction/development.inputs.jsonl")
                   .read_text(encoding="utf-8").splitlines() if line.strip()]
    assert manifest["engineering_gate"] == original["engineering_gate"]
    assert manifest["required_metrics"] == original["required_metrics"]
    assert manifest["partition_counts"] == {"validation": 12}
    assert len(inputs) == len(labels) == 12
    assert len({item["text"] for item in inputs}) == 12
    assert not ({item["text"] for item in inputs} & {item["text"] for item in development})
    fields = set(manifest["label_field_names"])
    for item, label in zip(inputs, labels, strict=True):
        assert set(item) == {"case_id", "text", "intent"}
        assert label["partition"] == "validation" and label["expected_proposition_count"] == 1
        assert set(label["fields"]) == fields
        assert len(item["text"]) <= 6000 and len(item["text"].encode("utf-8")) <= 24 * 1024
        assert item["intent"] == {"action_kind": "learn", "actor": "hypothetical", "endorsement": "uncertain"}
        for expected in label["fields"].values():
            assert expected["state"] in {"stated", "unknown"}
            if expected["state"] == "unknown":
                assert expected == {"state": "unknown"}
            else:
                literals = expected.get("surfaces", []) + expected.get("support_fragments", [])
                assert literals and len(literals) == len(set(literals))
                assert all(isinstance(value, str) and value and value in item["text"] for value in literals)
    assert any("\r\n" in item["text"] for item in inputs)
    assert any(any(ord(char) > 0xFFFF for char in item["text"]) for item in inputs)
    assert any(any(unicodedata.combining(char) for char in item["text"]) for item in inputs)

    records = [gold_shaped(item, label) for item, label in zip(inputs, labels, strict=True)]
    control = score_records(inputs, labels, records, manifest)
    assert control["engineering_gate_passed"]
    assert control["exact_case_success"] == {"correct": 12, "total": 12}
    assert control["known_field_accuracy"]["fraction"] == 1
    assert control["unknown_field_preservation"]["fraction"] == 1
    assert all(not case["unscored_stated_fields"] for case in control["cases"])

    missing = score_records(inputs, labels, [], manifest)
    assert missing["case_count"] == 12 and missing["operational_failures"] == 12
    assert not missing["engineering_gate_passed"]
    try:
        score_records(inputs, labels, records + [records[0]], manifest)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate predictions were accepted")
    late = deepcopy(records)
    late[0]["wall_seconds"] = 10.01
    assert not score_records(inputs, labels, late, manifest)["engineering_gate_passed"]

    polarity_index = next(index for index, label in enumerate(labels)
                          if label["fields"]["polarity"].get("value") == "negated")
    changed = deepcopy(records[polarity_index])
    changed["result"]["claim"]["propositions"][0]["polarity"]["value"] = "affirmed"
    assert "polarity" in score_case(inputs[polarity_index], labels[polarity_index], changed)["critical_errors"]
    changed = deepcopy(records[0])
    frame = changed["result"]["claim"]["propositions"][0]
    target = next(name for name, expected in labels[0]["fields"].items() if expected["state"] == "unknown")
    frame[target] = deepcopy(frame["intervention"])
    assert score_case(inputs[0], labels[0], changed)["invented_unknown_fields"] == 1
    changed = deepcopy(records[0])
    changed["result"]["claim"]["propositions"][0]["intervention"]["provenance"][0]["start"] += 1
    assert "intervention" in score_case(inputs[0], labels[0], changed)["span_errors"]

    report = {
        "artifact_kind": "offline_corpus_integrity_and_scorer_selftest",
        "not_model_results": True, "model_calls": 0,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_id": manifest["benchmark_id"], "case_count": 12,
        "corpus_files_sha256": {name: sha(HERE / name) for name in
                                ("validation.inputs.jsonl", "validation.labels.jsonl")},
        "scorer_sha256": sha(REPO / "evals/extraction/score.py"),
        "selftest_sha256": sha(Path(__file__).resolve()),
        "unchanged_engineering_gates": True, "integrity_passed": True,
        "fabricated_gold_shaped_converter_cases_passed": 12,
        "fabricated_gold_shaped_scorer_cases_passed": 12,
        "negative_scorer_controls_passed": ["missing_predictions", "duplicate_predictions",
            "over_stage_latency", "reversed_negation", "invented_unknown", "corrupted_span"],
        "human_adjudication": False,
        "claim_limit": "Checks authored data consistency, the production converter, and scorer mechanics only. No inference or model performance was measured.",
    }
    output = HERE / "offline_integrity.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(output), "case_count": 12, "integrity_passed": True,
                      "gold_shaped_controls_passed": 12, "negative_controls_passed": 6, "model_calls": 0}))


if __name__ == "__main__":
    main()
