import asyncio
from copy import deepcopy
from dataclasses import replace
import json

import httpx
import pytest

from app.gemini import GeminiTokenCounter, OFFICIAL_BASE
from app.provider import AttemptBudget, ProviderConfig, ProviderError, StructuredProvider


CONFIG = ProviderConfig(enabled=True, base_url=OFFICIAL_BASE, model="gemini-2.5-flash-lite",
    api_key="FAKE-TEST-KEY", free_budget_verified=True, billing_disabled=True,
    schema_capability_verified=True, verification_reference="mocked test only", max_requests=4)
SCHEMA = {"type": "object", "properties": {"source": {"type": ["string", "null"]}},
          "required": ["source"], "additionalProperties": False}
BODY = {"model": CONFIG.model, "messages": [
    {"role": "system", "content": "Copy exact Unicode spans. No inventions."},
    {"role": "user", "content": 'A fictional café says “quiet cards do not improve recall”.'}],
    "response_format": {"type": "json_schema", "json_schema": {"name": "extract", "strict": True, "schema": SCHEMA}},
    "max_tokens": 1800, "stream": False, "temperature": 0.0, "reasoning_effort": "none"}


def run(counter, body=None):
    return asyncio.run(counter(deepcopy(BODY) if body is None else body))


def test_native_count_preserves_every_text_character_and_schema_without_url_key():
    seen = []
    def handler(request):
        seen.append(request)
        assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:countTokens"
        assert not request.url.query
        assert request.headers["x-goog-api-key"] == CONFIG.api_key
        assert "authorization" not in request.headers
        payload = json.loads(request.content)
        assert set(payload) == {"generateContentRequest"}
        native = payload["generateContentRequest"]
        assert native["model"] == "models/" + CONFIG.model
        assert native["systemInstruction"] == {"parts": [{"text": BODY["messages"][0]["content"]}]}
        assert native["contents"] == [{"role": "user", "parts": [{"text": BODY["messages"][1]["content"]}]}]
        assert native["generationConfig"] == {"responseMimeType": "application/json", "responseJsonSchema": SCHEMA,
                                              "maxOutputTokens": 1800, "temperature": 0.0}
        return httpx.Response(200, json={"totalTokens": 127})
    counter = GeminiTokenCounter(CONFIG, transport=httpx.MockTransport(handler))
    original = deepcopy(BODY)
    assert run(counter, original) == 127 + 512
    assert original == BODY and len(seen) == counter.requests_used == 1
    assert CONFIG.api_key not in repr(counter) and CONFIG.api_key not in repr(counter.config)


def test_model_resource_prefix_is_canonicalized_and_multiple_users_remain_separate():
    config = replace(CONFIG, model="models/" + CONFIG.model)
    body = deepcopy(BODY)
    body["model"] = config.model
    body["messages"] = [{"role": "user", "content": "First"}, {"role": "user", "content": "Second"}]
    def handler(request):
        native = json.loads(request.content)["generateContentRequest"]
        assert "systemInstruction" not in native
        assert [part["parts"][0]["text"] for part in native["contents"]] == ["First", "Second"]
        return httpx.Response(200, json={"totalTokens": 20})
    assert run(GeminiTokenCounter(config, transport=httpx.MockTransport(handler), overhead_tokens=256), body) == 276


@pytest.mark.parametrize("status,code", [
    (429, "gemini_counter_quota_exhausted"), (401, "gemini_counter_access_denied"),
    (403, "gemini_counter_access_denied"), (404, "gemini_counter_model_unavailable"),
    (500, "token_counter_unavailable"),
    (302, "token_counter_unavailable")])
def test_error_or_redirect_is_terminal_without_body_or_key_exposure(status, code):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json={"error": "SECRET RAW INPUT"}, headers={"location": "https://other.invalid/stolen"})
    counter = GeminiTokenCounter(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match=code) as exc:
        run(counter)
    assert len(seen) == counter.requests_used == 1
    assert str(exc.value) == code
    assert "SECRET" not in str(exc.value) and CONFIG.api_key not in str(exc.value)


def test_total_wall_timeout_cancels_slow_response_without_retry(monkeypatch):
    monkeypatch.setattr("app.gemini.COUNT_TIMEOUT_SECONDS", 0.02)
    calls, cancelled = [], []
    async def handler(request):
        calls.append(request)
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
    counter = GeminiTokenCounter(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="token_counter_timeout"):
        run(counter)
    assert len(calls) == counter.requests_used == 1 and cancelled == [True]


def test_network_error_is_content_free_and_not_retried():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("SECRET socket detail", request=request)
    counter = GeminiTokenCounter(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="token_counter_unavailable") as exc:
        run(counter)
    assert "SECRET" not in str(exc.value) and len(calls) == 1


def test_counter_process_quota_cannot_be_refreshed_by_another_attempt():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"totalTokens": 10})
    counter = GeminiTokenCounter(replace(CONFIG, max_requests=1), transport=httpx.MockTransport(handler))
    assert run(counter) == 522
    with pytest.raises(ProviderError, match="gemini_counter_quota_exhausted"):
        run(counter)
    assert len(calls) == counter.requests_used == 1


@pytest.mark.parametrize("raw", [b"{}", b"[]", b'{"totalTokens":true}', b'{"totalTokens":0}',
    b'{"totalTokens":-1}', b'{"totalTokens":"12"}', b'{"totalTokens":1.5}',
    b'{"totalTokens":NaN}', b'{"totalTokens":1,"totalTokens":2}', b"not-json",
    b'{"totalTokens":10000001}', b"x" * (16 * 1024 + 1)])
def test_invalid_counts_and_oversized_responses_fail_closed(raw):
    counter = GeminiTokenCounter(CONFIG, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=raw)))
    with pytest.raises(ProviderError, match="token_counter_invalid"):
        run(counter)


@pytest.mark.parametrize("change", [
    {"base_url": "https://other.invalid/v1beta/openai"},
    {"base_url": OFFICIAL_BASE + "?api_key=secret"},
    {"base_url": "http://generativelanguage.googleapis.com/v1beta/openai"},
    {"model": "gemini-2.5-flash/../../other"}, {"api_key": "key\nheader"},
    {"free_budget_verified": False}, {"billing_disabled": False}, {"enabled": False}])
def test_unverified_or_nonofficial_configuration_never_creates_a_counter(change):
    with pytest.raises(ProviderError):
        GeminiTokenCounter(replace(CONFIG, **change))


@pytest.mark.parametrize("change", [
    {"model": "gemini-different"}, {"tools": [{"type": "function"}]}, {"stream": True},
    {"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": "https://private.invalid"}]}]},
    {"messages": [{"role": "assistant", "content": "hidden text"}]},
    {"messages": [{"role": "user", "content": "Hi"}, {"role": "system", "content": "late steering"}]},
    {"messages": [{"role": "system", "content": "No user"}]},
    {"response_format": {"type": "json_object"}}, {"max_tokens": 3000},
    {"temperature": float("nan")}, {"reasoning_effort": "unrecognized"}])
def test_unknown_prompt_shapes_are_rejected_before_network_dispatch(change):
    counter = GeminiTokenCounter(CONFIG)
    with pytest.raises(ProviderError, match="gemini_counter_unsupported_request"):
        run(counter, deepcopy(BODY) | change)
    assert counter.requests_used == 0


def test_external_schema_and_large_text_are_rejected_before_dispatch():
    counter = GeminiTokenCounter(CONFIG)
    body = deepcopy(BODY)
    body["response_format"]["json_schema"]["schema"] = {"$ref": "https://private.invalid/schema"}
    with pytest.raises(ProviderError, match="gemini_counter_unsupported_request"):
        run(counter, body)
    body = deepcopy(BODY)
    body["messages"][1]["content"] = "x" * (96 * 1024)
    with pytest.raises(ProviderError, match="gemini_counter_request_too_large"):
        run(counter, body)
    assert counter.requests_used == 0


def test_cancellation_propagates_and_consumes_counter_attempt():
    async def handler(_):
        raise asyncio.CancelledError()
    counter = GeminiTokenCounter(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(asyncio.CancelledError):
        run(counter)
    assert counter.requests_used == 1


def test_actual_generation_usage_above_native_count_and_margin_still_aborts():
    counter = GeminiTokenCounter(CONFIG, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"totalTokens": 100})))
    response = {"model": CONFIG.model, "choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": '{"source":null}'}}],
        "usage": {"prompt_tokens": 613, "completion_tokens": 5}}
    provider = StructuredProvider(CONFIG, token_counter=counter, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=response)))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match="provider_token_bound_violation"):
        asyncio.run(provider.call("extraction", {"input_text": "Fictional input."}, SCHEMA, ledger))
    assert ledger.input_tokens == 613 and provider.requests_used == counter.requests_used == 1
