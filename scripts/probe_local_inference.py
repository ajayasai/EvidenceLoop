"""Record a tiny synthetic development probe; never a sealed benchmark."""
import asyncio
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
from app.contracts import CompactExtractionCandidate
from app.domain import expand_compact_claim
from app.provider import AttemptBudget, LocalTokenCounter, ProviderConfig, StructuredProvider, PROMPT_VERSION


async def main(args):
    output = ROOT / "evals" / "development" / f"{args.model}-probe-{PROMPT_VERSION}{args.suffix}.json"
    config = ProviderConfig(enabled=True, base_url=args.base_url,
        model=args.model, free_budget_verified=True,
        billing_disabled=True, schema_capability_verified=True,
        verification_reference="docs/FREE_INFERENCE.md local synthetic smoke", max_requests=6)
    provider = StructuredProvider(config, token_counter=LocalTokenCounter(config.base_url))
    texts = ["A fictional lab reported that glow water made ferns taller over seven days than plain water.",
             "The fictional Study Club says quiet cards do not improve next-day recall.",
             "The advertisement says glow water helps every plant, but I disagree with that guarantee."]
    report = {"kind": "synthetic_development_probe", "sealed_benchmark": False,
              "clinical_review": False, "started_utc": datetime.now(timezone.utc).isoformat(),
              "model": config.model, "prompt_version": PROMPT_VERSION, "results": []}
    for index, text in enumerate(texts):
        ledger = AttemptBudget()
        before = time.monotonic()
        record = {"case_id": f"local-{index+1}", "input": text}
        data = {"original_text": text, "field_rules": "Use compact fields with exact quote substrings. "
            "Use string surfaces for concept values. Omit missing fields, do not infer endorsement. "
            "Occurrence is zero-based and needed only if a quote occurs more than once."}
        try:
            result = await provider.call("extraction", data, CompactExtractionCandidate.model_json_schema(), ledger)
            record["candidate"] = result.payload
            record["schema_valid"] = True
            try:
                expand_compact_claim(text, result.payload)
                record["domain_admitted"] = True
            except Exception as exc:
                record["domain_admitted"] = False
                record["domain_error"] = getattr(exc, "code", type(exc).__name__)
        except Exception as exc:
            record["provider_error"] = getattr(exc, "code", type(exc).__name__)
        record["seconds"] = time.monotonic() - before
        record["budget"] = ledger.metadata()
        report["results"].append(record)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "domain_admitted": sum(r.get("domain_admitted", False) for r in report["results"]), "cases": len(texts)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8090/v1")
    parser.add_argument("--model", default="qwen2.5-0.5b-onnx-int4-pilot")
    parser.add_argument("--suffix", default="")
    asyncio.run(main(parser.parse_args()))
