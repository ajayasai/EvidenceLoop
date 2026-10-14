"""Bounded, private, offline synthetic pilot; never a live app server.

Copy this script and a generated synthetic pilot-tasks.json into a private Kaggle
kernel. No account credentials, datasets, ports, tunnels, or real health data.
Outputs checkpoint after each attempt. This is a development experiment, not the
sealed evaluation or independent clinical review.
"""
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MODELS = [
    ("Qwen/Qwen2.5-1.5B-Instruct", "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"),
]


def grammar_schema(value):
    """LMFE cannot combine pattern and length; full validation remains mandatory."""
    if isinstance(value, list):
        return [grammar_schema(item) for item in value]
    if isinstance(value, dict):
        return {key: grammar_schema(item) for key, item in value.items()
                if not ("pattern" in value and key in {"minLength", "maxLength"})}
    return value


def main():
    started = time.monotonic()
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                    "lm-format-enforcer==0.11.3", "transformers>=4.37,<5", "jsonschema"],
                   check=True, timeout=180)
    import torch
    import transformers
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
    from jsonschema import Draft202012Validator

    if not torch.cuda.is_available():
        raise RuntimeError("Expected free GPU is unavailable; refusing an unplanned CPU run")
    output_dir = Path("/kaggle/working")
    tasks = json.loads(Path("pilot-tasks.json").read_text())
    manifest = {"kind": "private_synthetic_development_pilot", "torch": torch.__version__,
                "transformers": transformers.__version__, "gpu": torch.cuda.get_device_name(0),
                "models": MODELS, "tasks_sha256": hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest(),
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "clinical_review": False, "live_api_latency": False}
    (output_dir / "pilot-manifest.json").write_text(json.dumps(manifest, indent=2))
    with (output_dir / "pilot-results.jsonl").open("w", encoding="utf-8") as out:
        for model_id, revision in MODELS:
            if time.monotonic() - started > 420:
                break
            tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, token=False, trust_remote_code=False)
            model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, token=False,
                trust_remote_code=False, use_safetensors=True, torch_dtype=torch.float16).to("cuda").eval()
            for task in tasks[:3]:
                if time.monotonic() - started > 510:
                    break
                record = {"model": model_id, "revision": revision, "case_id": task["case_id"],
                          "original_text": task["data"]["original_text"], "mode": "offline_live_model"}
                before = time.monotonic()
                try:
                    messages = [dict(message) for message in task["messages"]]
                    # Explicit schema context is needed for small instruction models;
                    # grammar enforces syntax but cannot communicate field semantics.
                    messages[0]["content"] += "\nOutput schema:" + json.dumps(task["schema"], separators=(",", ":"))
                    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
                    count = inputs["input_ids"].shape[-1]
                    record["input_tokens"] = count
                    if count > 3500:
                        record["error"] = "stage_input_budget_exceeded"
                    else:
                        prefix = build_transformers_prefix_allowed_tokens_fn(tokenizer, JsonSchemaParser(grammar_schema(task["schema"])))
                        with torch.inference_mode():
                            generated = model.generate(**inputs, max_new_tokens=1800, max_time=10.0,
                                do_sample=False, prefix_allowed_tokens_fn=prefix,
                                pad_token_id=tokenizer.eos_token_id)
                        ids = generated[0, count:]
                        record["output_tokens"] = len(ids)
                        record["output"] = tokenizer.decode(ids, skip_special_tokens=True)
                        record["eos"] = ids[-1].item() in model.generation_config.eos_token_id if isinstance(model.generation_config.eos_token_id, list) else ids[-1].item() == model.generation_config.eos_token_id
                        value = json.loads(record["output"])
                        Draft202012Validator(task["schema"]).validate(value)
                        record["schema_valid"] = True
                except Exception as exc:
                    record["error_type"] = type(exc).__name__
                    record["error_detail"] = str(exc)[:500]  # synthetic development artifact only
                    record["schema_valid"] = False
                record["wall_seconds"] = time.monotonic() - before
                record["within_stage_deadline"] = record["wall_seconds"] <= 10.0
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())
                print(json.dumps({k: record[k] for k in ["case_id", "model", "wall_seconds", "within_stage_deadline", "schema_valid", "error"] if k in record}), flush=True)
            del model
            gc.collect()
            torch.cuda.empty_cache()
    print("Pilot checkpoint complete; inspect all outputs before making performance claims.", flush=True)


if __name__ == "__main__":
    main()
