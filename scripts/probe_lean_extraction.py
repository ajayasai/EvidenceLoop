"""Real local diagnostics with literal spans, separate from release evaluation."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = {"type": "object", "properties": {key: {"type": "string"} for key in
    ["source", "population", "intervention", "predicate", "outcome"]},
    "required": ["source", "population", "intervention", "predicate", "outcome"], "additionalProperties": False}
INSTRUCTION = ('Copy five spans from the claim. source = who made the statement, not the studied population. '
    'population = who or what was studied. intervention = tested thing. predicate = exact effect verb phrase, '
    'including negation. outcome = measured result. Use exact substrings; use "" if missing. '
    'Do not infer the user\'s agreement. Return compact JSON on one line.')
EXAMPLE = (' Example: A bulletin says blue pens do not improve recall in artists. '
    'Answer: {"source":"A bulletin","population":"artists","intervention":"blue pens",'
    '"predicate":"do not improve","outcome":"recall"}')
REFINED = ('Copy exact claim substrings into the five slots. Missing MUST be "". '
    'Source is the reporting speaker, never the treatment or user disagreement. '
    'Predicate includes negation. Outcome is a measured property, not study subjects. One-line JSON. '
    'Example: Lime tabs improve memory in sailors. '
    '{"source":"","population":"sailors","intervention":"Lime tabs","predicate":"improve","outcome":"memory"} '
    'Example: A poster says pebble spray helps every fern, but I disagree. '
    '{"source":"A poster","population":"every fern","intervention":"pebble spray","predicate":"helps","outcome":""}')
NULLABLE = ('Copy exact claim substrings. Missing means null. Source is who reports the claim, '
    'never the intervention or a disagreeing user. Population is studied subjects. '
    'Predicate includes negation. Outcome is the measured property, not subjects. '
    'Comparator is the alternative being compared. One-line JSON. '
    'Example: Lime tabs improve memory in sailors compared with blank cards. '
    '{"source":null,"population":"sailors","intervention":"Lime tabs","comparator":"blank cards","predicate":"improve","outcome":"memory"}')
SIX = ('Copy exact statement spans; missing MUST be "". Source is the reporting speaker before '
    'says/reports/claims/found; otherwise empty. Population is studied subjects, never the source. '
    'Intervention is the tested thing. Predicate includes negation. Outcome is a measured property, '
    'never the population. Comparator is an explicitly compared alternative. One-line JSON. '
    'Example: A leaflet says violet tabs do not improve memory. '
    '{"source":"A leaflet","population":"","intervention":"violet tabs","comparator":"",'
    '"predicate":"do not improve","outcome":"memory"}')
CASES = [
    ("A fictional trial found that amber cards improved recall in students.",
     {"source": "A fictional trial", "population": "students", "intervention": "amber cards", "predicate": "improved", "outcome": "recall"}),
    ("The fictional Study Club says quiet cards do not improve next-day recall.",
     {"source": "The fictional Study Club", "population": "", "intervention": "quiet cards", "predicate": "do not improve", "outcome": "next-day recall"}),
    ("The advertisement says glow water helps every plant, but I disagree with that guarantee.",
     {"source": "The advertisement", "population": "every plant", "intervention": "glow water", "predicate": "helps", "outcome": ""}),
    ("Soft bells increased task accuracy in gardeners over two weeks.",
     {"source": "", "population": "gardeners", "intervention": "Soft bells", "predicate": "increased", "outcome": "task accuracy"}),
]


async def main(args):
    destination = ROOT / "evals/development" / ("lean-extraction-" + args.label + ".json")
    if destination.exists():
        raise RuntimeError("Refusing to overwrite previous results")
    report = {"kind": "local_literal_span_diagnostic", "clinical_review": False, "sealed_evaluation": False,
              "started_utc": datetime.now(timezone.utc).isoformat(), "schema": SCHEMA, "results": []}
    async with httpx.AsyncClient(timeout=12, trust_env=False) as client:
        report["runtime"] = (await client.get(args.base_url + "/health")).json()
        for variant in args.variants.split(","):
            instruction = SIX if variant == "six" else NULLABLE if variant == "nullable" else REFINED if variant == "refined" else INSTRUCTION + (EXAMPLE if variant == "fewshot" else "")
            schema = SCHEMA
            if variant in {"nullable", "six"}:
                keys = ["source", "population", "intervention", "comparator", "predicate", "outcome"]
                schema = {"type": "object", "properties": {key: {"type": ["string", "null"] if variant == "nullable" else "string"} for key in keys},
                          "required": keys, "additionalProperties": False}
            for index, (claim, expected) in enumerate(CASES):
                if variant == "nullable":
                    expected = {key: value or None for key, value in expected.items()} | {"comparator": None}
                elif variant == "six":
                    expected = expected | {"comparator": ""}
                for _ in range(80):
                    health = (await client.get(args.base_url + "/health")).json()
                    if health["status"] == "ok" and not health["busy"]:
                        break
                    await asyncio.sleep(0.25)
                messages = [{"role": "system", "content": instruction}, {"role": "user", "content": claim}]
                body = {"model": report["runtime"]["model"], "messages": messages,
                        "response_format": {"type": "json_schema", "json_schema": {"name": "literal_spans", "strict": True, "schema": schema}},
                        "max_tokens": 1800, "stream": False}
                record = {"case_id": index + 1, "variant": variant, "messages": messages, "schema": schema, "expected": expected}
                start = time.perf_counter()
                try:
                    response = await client.post(args.base_url + "/v1/chat/completions", json=body)
                    record["http_status"] = response.status_code
                    record["response"] = response.json()
                    if response.status_code == 200:
                        value = json.loads(record["response"]["choices"][0]["message"]["content"])
                        record["all_spans_literal"] = all(not v or v in claim for v in value.values())
                        record["exact_expected"] = value == expected
                        record["field_matches"] = {key: value.get(key) == v for key, v in expected.items()}
                except Exception as exc:
                    record["error_type"] = type(exc).__name__
                record["wall_seconds"] = round(time.perf_counter() - start, 4)
                report["results"].append(record)
                destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps({"variant": variant, "case": index + 1, "seconds": record["wall_seconds"],
                    "exact": record.get("exact_expected"), "response": record.get("response")}), flush=True)
    print(str(destination))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8091")
    parser.add_argument("--variants", default="lean,fewshot")
    parser.add_argument("--label", required=True)
    asyncio.run(main(parser.parse_args()))
