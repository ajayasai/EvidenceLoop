"""Bounded synthetic cancellation/responsiveness check for the loopback runtime."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8091"


def process_alive(pid):
    import ctypes
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    try:
        if not kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
            return None
        return code.value == 259
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


async def main():
    async with httpx.AsyncClient(timeout=16, trust_env=False) as client:
        before = (await client.get(BASE + "/health")).json()
        if before["status"] != "ok" or before["busy"]:
            raise RuntimeError("Runtime must be ready and idle")
        body = {"model": before["model"], "messages": [
            {"role": "system", "content": "Return a JSON text field containing the letter A repeated 10000 times. This is synthetic load-test data."},
            {"role": "user", "content": "Produce the synthetic letters now."}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "load_test", "strict": True,
                "schema": {"type": "object", "properties": {"text": {"type": "string", "minLength": 10000}},
                           "required": ["text"], "additionalProperties": False}}}, "max_tokens": 1800}
        report = {"kind": "synthetic_runtime_cancellation_check", "clinical_review": False,
                  "started_utc": datetime.now(timezone.utc).isoformat(), "before": before}
        started = time.monotonic()
        pending = asyncio.create_task(client.post(BASE + "/v1/chat/completions", json=body))
        await asyncio.sleep(0.25)
        instant = time.monotonic()
        report["during"] = (await client.get(BASE + "/health")).json()
        report["health_seconds"] = round(time.monotonic() - instant, 3)
        instant = time.monotonic()
        busy = await client.post(BASE + "/v1/token-count", json=body)
        report["busy_count_status"] = busy.status_code
        report["busy_count_seconds"] = round(time.monotonic() - instant, 3)
        response = await pending
        report["generation_status"] = response.status_code
        report["generation_seconds"] = round(time.monotonic() - started, 3)
        if response.status_code == 200:
            data = response.json()
            report["finish_reason"] = data["choices"][0]["finish_reason"]
            report["usage"] = data["usage"]
            report["timing"] = data.get("local_timing")
        else:
            report["error"] = response.json()
        report["old_worker_alive"] = process_alive(before["worker_pid"])
        for _ in range(80):
            report["after"] = (await client.get(BASE + "/health")).json()
            if report["after"]["status"] == "ok":
                break
            await asyncio.sleep(0.25)
        report["no_hidden_generation_retry"] = report["after"]["generations_started"] == before["generations_started"] + 1
        report["passed"] = (report["health_seconds"] < 0.5 and report["busy_count_seconds"] < 0.5
            and report["busy_count_status"] == 429 and report["generation_seconds"] < 10
            and report["old_worker_alive"] is False and report["no_hidden_generation_retry"]
            and report["after"]["status"] == "ok")
        path = ROOT / "evals/development/local-runtime-cancellation.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
