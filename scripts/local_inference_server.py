"""Loopback-only ONNX Runtime GenAI candidate service; synthetic development use.

Uses local model data and Microsoft's installed runtime. No downloads, tools,
external APIs, credential handling, public listening or prompt logging.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import multiprocessing as mp
import time

from fastapi import FastAPI, HTTPException, Request
import onnxruntime_genai as og
import uvicorn

MODEL_ID = "qwen2.5-0.5b-onnx-int4-pilot"
THREADS = 4
FAST_FORWARD = False
model = tokenizer = None
worker = connection = None
gate = asyncio.Lock()
settings = None
ready = False
restart_task = None
worker_generation = 0
generations_started = 0
warmup_seconds = None


def prompt_tokens(body):
    if body.get("model") != MODEL_ID or body.get("tools") or body.get("stream"):
        raise ValueError("unsupported_request")
    schema = body["response_format"]["json_schema"]["schema"]
    messages = [dict(m) for m in body["messages"]]
    if not messages or len(messages) > 3 or any(m.get("role") not in {"system", "user"} for m in messages):
        raise ValueError("invalid_messages")
    messages[0]["content"] += "\nOutput JSON schema: " + json.dumps(schema, separators=(",", ":"))
    # This pinned Qwen2.5 export does not ship an embedded ORT chat template.
    # Use its documented ChatML framing; do not evaluate downloaded code/templates.
    if any("<|" in message["content"] for message in messages):
        raise ValueError("reserved_control_token")
    prompt = "".join("<|im_start|>" + message["role"] + "\n" + message["content"] + "<|im_end|>\n"
                     for message in messages) + "<|im_start|>assistant\n"
    return tokenizer.encode(prompt), schema


async def body_limited(request):
    raw = await request.body()
    if len(raw) > 96 * 1024:
        raise HTTPException(413, "request_too_large")
    try:
        return json.loads(raw)
    except ValueError:
        raise HTTPException(400, "invalid_json") from None


app = FastAPI(docs_url=None, redoc_url=None)


@app.get("/health")
def health():
    return {"status": "ok" if ready else "loading", "busy": gate.locked(),
            "model": MODEL_ID, "mode": "local_live_candidate", "clinical_validation": False,
            "threads": THREADS, "grammar_fast_forward": FAST_FORWARD,
            "worker_generation": worker_generation, "generations_started": generations_started,
            "warmup_seconds": warmup_seconds,
            "worker_pid": worker.pid if worker is not None else None}


@app.post("/v1/token-count")
async def count(request: Request):
    body = await body_limited(request)
    return await dispatch(request, "count", body, 1.5)


def generate(body, deadline):
    request_started = time.perf_counter()
    tokens, schema = prompt_tokens(body)
    tokenized_at = time.perf_counter()
    output_limit = body.get("max_tokens", 0)
    if type(output_limit) is not int or not 1 <= output_limit <= 2200 or len(tokens) > 7500:
        raise HTTPException(400, "token_budget")
    params = og.GeneratorParams(model)
    params.set_search_options(max_length=len(tokens) + output_limit, do_sample=False)
    params.set_guidance("json_schema", json.dumps(schema), FAST_FORWARD)
    guidance_at = time.perf_counter()
    generator = og.Generator(model, params)
    constructed_at = time.perf_counter()
    started = time.perf_counter()
    generator.append_tokens(tokens)
    prefill_seconds = time.perf_counter() - started
    output = []
    while not generator.is_done() and len(output) < output_limit:
        if time.monotonic() >= deadline - 0.15:
            break
        generator.generate_next_token()
        output = [int(t) for t in generator.get_sequence(0)[len(tokens):]]
    # Grammar fast-forward can finish at the closing brace without emitting
    # an EOS token. is_done plus unused output capacity distinguishes this
    # normal completion from max_length truncation; the provider validates JSON.
    complete = generator.is_done() and bool(output) and len(output) < output_limit
    content = tokenizer.decode(output)
    # EOS markers are decoding controls, not user content.
    for marker in ("<|im_end|>", "<|endoftext|>"):
        if content.endswith(marker):
            content = content[:-len(marker)]
    return {"model": MODEL_ID, "choices": [{"finish_reason": "stop" if complete else "length",
            "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": len(tokens), "completion_tokens": len(output)},
            "local_timing": {"tokenize_seconds": round(tokenized_at - request_started, 4),
                             "guidance_seconds": round(guidance_at - tokenized_at, 4),
                             "construction_seconds": round(constructed_at - guidance_at, 4),
                             "prefill_seconds": round(prefill_seconds, 4),
                             "generation_seconds": round(time.perf_counter() - started - prefill_seconds, 4),
                             "total_seconds": round(time.perf_counter() - request_started, 4)}}

def worker_main(pipe, options):
    """The runtime owns this process; a stalled native call cannot block HTTP."""
    global model, tokenizer, MODEL_ID, THREADS, FAST_FORWARD
    MODEL_ID, THREADS, FAST_FORWARD = options.model_id, options.threads, options.fast_forward
    try:
        config = og.Config(options.model_path)
        config.clear_providers()
        config.overlay(json.dumps({"model": {"decoder": {"session_options": {
            "intra_op_num_threads": THREADS, "inter_op_num_threads": 1}}}}))
        model = og.Model(config)
        tokenizer = og.Tokenizer(model)
        # Build the runtime's grammar/tokenizer tables before admitting requests.
        # No user prompt, model generation or external call is used for this step.
        warmup_started = time.perf_counter()
        warmup_params = og.GeneratorParams(model)
        warmup_params.set_search_options(max_length=64, do_sample=False)
        warmup_params.set_guidance("json_schema", '{"type":"object","properties":{"ready":{"type":"boolean"}},"required":["ready"],"additionalProperties":false}', FAST_FORWARD)
        warmup_generator = og.Generator(model, warmup_params)
        del warmup_generator, warmup_params
        pipe.send({"ready": True, "warmup_seconds": round(time.perf_counter() - warmup_started, 4)})
        while True:
            kind, body, deadline = pipe.recv()
            try:
                result = ({"input_tokens": len(prompt_tokens(body)[0])} if kind == "count"
                          else generate(body, deadline))
                pipe.send({"result": result})
            except Exception:
                pipe.send({"error": "local_inference_failed"})
    except (EOFError, BrokenPipeError):
        pass
    except Exception:
        pipe.send({"error": "local_runtime_failed"})
    finally:
        pipe.close()


def stop_worker():
    global worker, connection, ready, worker_generation
    ready = False
    if worker is not None:
        if worker.is_alive():
            worker.terminate()
        worker.join(timeout=0.5)
        if worker.is_alive():
            worker.kill()
            worker.join(timeout=0.5)
    if connection is not None:
        connection.close()
    worker = connection = None


async def start_worker():
    global worker, connection, ready, worker_generation, warmup_seconds
    if ready and worker is not None and worker.is_alive():
        return
    stop_worker()
    connection, child = mp.get_context("spawn").Pipe()
    worker = mp.get_context("spawn").Process(target=worker_main, args=(child, settings), daemon=True)
    worker.start()
    worker_generation += 1
    child.close()
    deadline = time.monotonic() + 20
    while not connection.poll():
        if not worker.is_alive() or time.monotonic() > deadline:
            stop_worker()
            raise RuntimeError("local_runtime_start_failed")
        await asyncio.sleep(0.025)
    startup = connection.recv()
    if not startup.get("ready"):
        stop_worker()
        raise RuntimeError("local_runtime_start_failed")
    warmup_seconds = startup.get("warmup_seconds")
    ready = True


def schedule_restart():
    global restart_task
    if restart_task is None or restart_task.done():
        restart_task = asyncio.create_task(start_worker())
        # Observe startup failures without logging prompts or unhandled exceptions.
        restart_task.add_done_callback(lambda task: None if task.cancelled() else task.exception())


@asynccontextmanager
async def lifespan(application):
    await start_worker()
    try:
        yield
    finally:
        if restart_task is not None and not restart_task.done():
            restart_task.cancel()
        stop_worker()


app.router.lifespan_context = lifespan


async def dispatch(request, kind, body, seconds):
    global generations_started
    if gate.locked():
        raise HTTPException(429, "local_model_busy")
    async with gate:
        if not ready or worker is None or not worker.is_alive():
            # Restart prepares later requests; the failed inference is not retried.
            schedule_restart()
            raise HTTPException(503, "local_runtime_loading")
        deadline = time.monotonic() + seconds
        if kind == "generate":
            generations_started += 1
        connection.send((kind, body, deadline))
        while not connection.poll():
            if await request.is_disconnected() or time.monotonic() >= deadline:
                stop_worker()
                schedule_restart()
                raise HTTPException(504, "local_inference_deadline")
            if not worker.is_alive():
                stop_worker()
                schedule_restart()
                raise HTTPException(503, "local_runtime_failed")
            await asyncio.sleep(0.01)
        response = connection.recv()
        if "error" in response:
            raise HTTPException(503, response["error"])
        result = response["result"]
        if kind == "generate" and result["choices"][0]["finish_reason"] != "stop":
            # A truncated request is terminal. Dispose of all runtime state and
            # prepare a fresh worker without automatically resubmitting its data.
            stop_worker()
            schedule_restart()
        return result


@app.post("/v1/chat/completions")
async def completion(request: Request):
    body = await body_limited(request)
    # Leave a small transport margin inside the provider's hard stage deadline.
    seconds = 9.5 if body.get("max_tokens") == 1800 else 13.5
    return await dispatch(request, "generate", body, seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--fast-forward", action="store_true")
    args = parser.parse_args()
    MODEL_ID = args.model_id
    THREADS = args.threads
    FAST_FORWARD = args.fast_forward
    settings = args
    # Loopback is fixed; no configuration can make this a public model endpoint.
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="error")
