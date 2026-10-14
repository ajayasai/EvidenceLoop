"""Offline scoring of developer-authored fictional extraction cases; no model calls.

Accept normalized extraction results, not a model-specific wire format. Missing
predictions remain failures in every relevant denominator. Do not use this file
as an extractor, a production fallback, or clinical ground truth.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import unicodedata

ROOT = Path(__file__).resolve().parent


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(value):
    return unicodedata.normalize("NFC", value.strip()) if isinstance(value, str) else value


def load_corpus(partition, root=ROOT):
    if partition not in {"development", "validation"}:
        raise ValueError("Unknown extraction partition")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    paths = [root / f"{partition}.{kind}.jsonl" for kind in ("inputs", "labels")]
    for path in paths:
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["files_sha256"][path.name]:
            raise ValueError("Frozen corpus hash changed; version the benchmark before reuse")
    inputs, labels = map(read_jsonl, paths)
    if [x["case_id"] for x in inputs] != [x["case_id"] for x in labels]:
        raise ValueError("Input and label identities do not match")
    if len({x["case_id"] for x in inputs}) != len(inputs):
        raise ValueError("Duplicate benchmark identity")
    return inputs, labels, manifest


def _grounded(field, text):
    origins = field.get("provenance", [])
    if not origins:
        return False
    for origin in origins:
        if not isinstance(origin, dict) or origin.get("kind") != "input_span":
            return False
        start, end = origin.get("start"), origin.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            return False
        if origin.get("quote") != text[start:end]:
            return False
        if origin.get("input_hash") != hashlib.sha256(text.encode("utf-8")).hexdigest():
            return False
    return True


def score_case(item, label, record):
    record = record or {}
    result = record.get("result", {})
    if not isinstance(result, dict):
        result = {}
    claim = result.get("claim", result)
    if not isinstance(claim, dict):
        claim = {}
    propositions = claim.get("propositions", [])
    if not isinstance(propositions, list):
        propositions = []
    frame = propositions[0] if propositions and isinstance(propositions[0], dict) else {}
    operational = bool(record.get("error") or not record or result.get("system_status") == "model_error" or result.get("mode") == "manual")
    details = {}
    known_correct = unknown_correct = known_total = unknown_total = 0
    invented_unknown = 0
    critical_errors = []
    for name, expected in label["fields"].items():
        observed = frame.get(name, {"state": "unknown", "value": None})
        observed = observed if isinstance(observed, dict) else {}
        stated = observed.get("state") == "stated" and observed.get("value") is not None
        if expected["state"] == "unknown":
            unknown_total += 1
            correct = not stated and observed.get("value") is None and observed.get("state") in {"unknown", "ambiguous"}
            unknown_correct += int(correct and not operational)
            invented_unknown += int(stated)
        else:
            known_total += 1
            value = observed.get("value")
            if isinstance(value, dict):
                value = value.get("surface")
            accepted = expected.get("surfaces", [expected.get("value")])
            correct = stated and _norm(value) in [_norm(x) for x in accepted] and _grounded(observed, item["text"])
            if correct and expected.get("surfaces"):
                correct = any(_norm(p["quote"]) == _norm(value) for p in observed["provenance"])
            if correct and expected.get("support_fragments"):
                quotes = " ".join(p["quote"] for p in observed["provenance"])
                correct = any(fragment in quotes for fragment in expected["support_fragments"])
            known_correct += int(correct and not operational)
        correct = bool(correct and not operational)
        details[name] = correct
        if not correct and name in label["critical_fields"]:
            critical_errors.append(name)
    for name in ("speaker", "speech_act"):
        correct = frame.get(name) == label[name] and not operational
        details[name] = correct
        if not correct:
            critical_errors.append(name)
    # Every stated field needs valid original provenance, including unscored fields.
    span_errors = [name for name, value in frame.items() if isinstance(value, dict)
                   and value.get("state") == "stated" and not _grounded(value, item["text"])]
    unscored_stated = [name for name, value in frame.items() if isinstance(value, dict)
                      and value.get("state") == "stated" and name not in label["fields"]]
    intention = result.get("intent", {})
    intent_preserved = isinstance(intention, dict) and all(
        isinstance(intention.get(key), dict) and intention[key].get("state") == "stated"
        and intention[key].get("value") == value for key, value in item["intent"].items())
    if not intent_preserved:
        critical_errors.append("explicit_intent_preservation")
    count_ok = len(propositions) == label["expected_proposition_count"]
    if not count_ok:
        critical_errors.append("proposition_count")
    useful_eligible = all(label["fields"][name]["state"] == "stated" for name in ("intervention", "measured_outcome"))
    useful = useful_eligible and all(details[name] for name in ("intervention", "measured_outcome", "polarity")) and intent_preserved and count_ok
    wall = record.get("wall_seconds")
    wall = wall if type(wall) in (int, float) and math.isfinite(wall) and wall >= 0 else None
    return {"case_id": item["case_id"], "field_checks": details,
            "known_correct": known_correct, "known_total": known_total,
            "unknown_correct": unknown_correct, "unknown_total": unknown_total,
            "invented_unknown_fields": invented_unknown, "critical_errors": critical_errors,
            "span_errors": span_errors, "unscored_stated_fields": unscored_stated,
            "explicit_intent_preserved": intent_preserved, "operational_failure": operational,
            "useful_eligible": useful_eligible, "useful_essential_extraction": bool(useful),
            "exact_case_success": bool(all(details.values()) and count_ok and intent_preserved and not span_errors and not operational),
            "wall_seconds": wall}


def score_records(inputs, labels, records, manifest):
    identities = Counter(r.get("case_id") for r in records)
    expected = {item["case_id"] for item in inputs}
    if any(count > 1 for count in identities.values()) or set(identities) - expected:
        raise ValueError("Prediction IDs must be unique and belong to the selected partition")
    by_id = {r["case_id"]: r for r in records}
    cases = [score_case(item, label, by_id.get(item["case_id"])) for item, label in zip(inputs, labels, strict=True)]
    def metric(correct, total):
        n, d = sum(case[correct] for case in cases), sum(case[total] for case in cases)
        return {"correct": n, "total": d, "fraction": n/d if d else None}
    known = metric("known_correct", "known_total")
    unknown = metric("unknown_correct", "unknown_total")
    useful = metric("useful_essential_extraction", "useful_eligible")
    times = sorted(case["wall_seconds"] for case in cases if case["wall_seconds"] is not None)
    thresholds = manifest["engineering_gate"]
    totals = {"critical_field_errors": sum(len(c["critical_errors"]) for c in cases),
              "invented_unknown_fields": sum(c["invented_unknown_fields"] for c in cases),
              "span_integrity_errors": sum(len(c["span_errors"]) for c in cases),
              "operational_failures": sum(c["operational_failure"] for c in cases)}
    gate = bool(known["fraction"] is not None and known["fraction"] >= thresholds["known_field_accuracy_min"]
                and useful["fraction"] is not None and useful["fraction"] >= thresholds["useful_essential_extraction_min"]
                and all(totals[key] <= thresholds[key+"_max"] for key in totals)
                and len(times) == len(cases) and max(times, default=math.inf) <= thresholds["extraction_stage_seconds_max"])
    return {"benchmark_id": manifest["benchmark_id"], "claim_limit": manifest["claim_limit"],
            "case_count": len(cases), "submitted_count": len(records),
            "known_field_accuracy": known, "unknown_field_preservation": unknown,
            "useful_essential_extraction": useful, **totals,
            "exact_case_success": {"correct": sum(c["exact_case_success"] for c in cases), "total": len(cases)},
            "latency_all_attempts": {"reported": len(times), "missing": len(cases)-len(times),
                "median_seconds": (times[(len(times)-1)//2]+times[len(times)//2])/2 if times else None,
                "maximum_seconds": max(times) if times else None,
                "over_stage_limit": sum(t > thresholds["extraction_stage_seconds_max"] for t in times)},
            "engineering_gate_passed": gate, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", choices=("development", "validation"), required=True)
    parser.add_argument("--corpus-root", type=Path, default=ROOT)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new run artifact instead of overwriting results")
    inputs, labels, manifest = load_corpus(args.partition, args.corpus_root)
    result = score_records(inputs, labels, read_jsonl(args.predictions), manifest)
    result["partition"] = args.partition
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("benchmark_id", "partition", "case_count", "engineering_gate_passed")}))


if __name__ == "__main__":
    main()
