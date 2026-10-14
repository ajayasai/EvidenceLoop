"""Operational contract tests use an in-memory HTTP transport; no paid calls."""
import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
import pytest

from app.provider import AttemptBudget, ProviderConfig, ProviderError, StructuredProvider, compact_schema


SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}
CONFIG = ProviderConfig(enabled=True, base_url="http://127.0.0.1:8089/v1", model="test-model",
                        free_budget_verified=True, billing_disabled=True,
                        schema_capability_verified=True, verification_reference="mock-only",
                        max_requests=20)
GEMINI_CONFIG = replace(CONFIG, base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                        model="gemini-test", api_key="mock")


def envelope(text='{"ok":true}', *, finish="stop", usage=True):
    result = {"model": "test-model-revision", "choices": [{"finish_reason": finish,
              "message": {"role": "assistant", "content": text}}]}
    if usage:
        result["usage"] = {"prompt_tokens": 100, "completion_tokens": 20}
    return result


def run(provider, ledger=None, **kwargs):
    return asyncio.run(provider.call("extraction", {"original_text": "synthetic"}, SCHEMA,
                                     ledger or AttemptBudget(), **kwargs))


def test_disabled_does_not_dispatch_or_discover_ambient_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-use")
    monkeypatch.delenv("EVIDENCELOOP_LIVE_ENABLED", raising=False)
    config = ProviderConfig.from_env()
    assert not config.enabled and config.api_key == ""
    with pytest.raises(ProviderError, match="live_inference_disabled"):
        run(StructuredProvider(config))


@pytest.mark.parametrize("field,value", [("billing_disabled", False),
    ("free_budget_verified", False), ("schema_capability_verified", False),
    ("verification_reference", ""), ("max_requests", 0)])
def test_all_free_runtime_gates_required(field, value):
    with pytest.raises(ProviderError, match="free_runtime_unverified"):
        run(StructuredProvider(replace(CONFIG, **{field: value})))


def test_newer_gemini_can_omit_sampling_control_from_environment(monkeypatch):
    monkeypatch.setenv("EVIDENCELOOP_TEMPERATURE", "none")
    cfg = ProviderConfig.from_env()
    body = StructuredProvider(cfg)._body("extraction", {"original_text":"fictional"}, SCHEMA, 0)
    assert cfg.temperature is None
    assert "temperature" not in body


@pytest.mark.parametrize("value", ["bad", "nan", "inf", "-1"])
def test_invalid_temperature_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv("EVIDENCELOOP_TEMPERATURE", value)
    cfg = replace(CONFIG, temperature=ProviderConfig.from_env().temperature)
    with pytest.raises(ProviderError, match="invalid_provider_configuration"):
        cfg.require_enabled()


def test_success_is_structured_and_prompt_has_no_tool_authority():
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json=envelope())
    ledger = AttemptBudget()
    result = run(StructuredProvider(CONFIG, transport=httpx.MockTransport(handler)), ledger)
    assert result.payload == {"ok": True}
    assert result.model_revision == "test-model-revision"
    assert ledger.input_tokens == 100 and ledger.output_tokens == 20
    assert ledger.calls == {"extraction": 1}
    assert ledger.automated_seconds >= 0  # mocked HTTP may complete in one Windows timer tick
    assert seen[0]["response_format"]["json_schema"]["strict"] is True
    assert seen[0]["max_tokens"] == 1800 and "tools" not in seen[0]


@pytest.mark.parametrize("bad", ['not JSON', '{"ok":"yes"}', '{"ok":true,"secret":"x"}',
                                '{"ok":true,"ok":false}', '{"ok":NaN}'])
def test_one_schema_repair_and_usage_accumulates(bad):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=envelope(bad if len(calls) == 1 else '{"ok":true}'))
    ledger = AttemptBudget()
    result = run(StructuredProvider(CONFIG, transport=httpx.MockTransport(handler)), ledger)
    assert len(calls) == 2 and result.repair_count == 1
    assert result.transient_retry_count == 0
    assert ledger.input_tokens == 200 and ledger.output_tokens == 40
    assert bad not in calls[1]["messages"][1]["content"]
    assert "Previous response failed" in calls[1]["messages"][0]["content"]


def test_second_invalid_output_is_terminal_and_same_attempt_cannot_reset():
    provider = StructuredProvider(CONFIG, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=envelope('{}'))))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match="invalid_structured_output"):
        run(provider, ledger)
    with pytest.raises(ProviderError, match="stage_exhausted"):
        run(provider, ledger)
    assert provider.requests_used == 2


@pytest.mark.parametrize("status,code", [(429, "provider_quota_exhausted"),
    (401, "provider_access_denied"), (403, "provider_access_denied"),
    (502, "provider_temporarily_unavailable"), (503, "provider_temporarily_unavailable"),
    (504, "provider_temporarily_unavailable"), (302, "provider_http_error")])
def test_http_failures_never_retry_or_leak_body(status, code):
    provider = StructuredProvider(CONFIG, transport=httpx.MockTransport(
        lambda _: httpx.Response(status, text="SECRET RAW HEALTH BODY")))
    with pytest.raises(ProviderError, match=code) as exc:
        run(provider)
    assert "SECRET" not in str(exc.value)
    assert provider.requests_used == 1


@pytest.mark.parametrize("config", [CONFIG, GEMINI_CONFIG])
def test_timeout_never_retries_and_reserves_unknown_usage(config):
    def handler(request):
        raise httpx.ReadTimeout("sensitive request", request=request)
    provider = StructuredProvider(config, transport=httpx.MockTransport(handler))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match="provider_timeout"):
        run(provider, ledger)
    assert provider.requests_used == 1 and ledger.output_tokens == 1800


@pytest.mark.parametrize("config", [CONFIG, GEMINI_CONFIG])
def test_truncated_output_never_schema_repairs(config):
    provider = StructuredProvider(config, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=envelope('{"ok":', finish="length"))))
    with pytest.raises(ProviderError, match="provider_incomplete_output"):
        run(provider)
    assert provider.requests_used == 1


def test_explicit_length_regeneration_is_opt_in_and_preserves_full_reservation():
    responses = [envelope('{"ok":', finish='length'), envelope()]
    bodies, admitted = [], []
    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=responses[len(bodies)-1])
    provider = StructuredProvider(replace(GEMINI_CONFIG, retry_truncated_extraction=True),
        token_counter=lambda _: 500, transport=httpx.MockTransport(handler))
    ledger = AttemptBudget()
    result = run(provider, ledger, validator=admitted.append)
    assert result.payload == {'ok': True} and admitted == [{'ok': True}]
    assert result.truncation_retry_count == 1 and result.repair_count == result.transient_retry_count == 0
    assert result.usage.estimated
    assert ledger.calls == {'extraction': 2}
    assert (ledger.input_tokens, ledger.output_tokens) == (600, 1820)
    assert bodies[0] == bodies[1]  # Partial model text is never fed back.


@pytest.mark.parametrize('config,stage', [(CONFIG, 'extraction'), (GEMINI_CONFIG, 'alignment')])
def test_length_regeneration_does_not_apply_to_other_providers_or_alignment(config, stage):
    provider = StructuredProvider(replace(config, retry_truncated_extraction=True),
        token_counter=lambda _: 500,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope('{', finish='length'))))
    with pytest.raises(ProviderError, match='provider_incomplete_output'):
        asyncio.run(provider.call(stage, {}, SCHEMA, AttemptBudget()))
    assert provider.requests_used == 1


@pytest.mark.parametrize('finish', ['content_filter', 'tool_calls', 'function_call', None, 'unknown'])
def test_non_length_stops_never_regenerate(finish):
    provider = StructuredProvider(replace(GEMINI_CONFIG, retry_truncated_extraction=True),
        token_counter=lambda _: 500,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope('{', finish=finish))))
    with pytest.raises(ProviderError, match='provider_incomplete_output'):
        run(provider)
    assert provider.requests_used == 1


@pytest.mark.parametrize('field,value', [('refusal','blocked'), ('tool_calls',[{'id':'call'}]), ('function_call',{'name':'tool'})])
def test_length_with_refusal_or_tool_content_never_regenerates(field, value):
    response = envelope('{', finish='length')
    response['choices'][0]['message'][field] = value
    provider = StructuredProvider(replace(GEMINI_CONFIG, retry_truncated_extraction=True),
        token_counter=lambda _: 500, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)))
    with pytest.raises(ProviderError, match='provider_refusal_or_tool_output'):
        run(provider)
    assert provider.requests_used == 1


@pytest.mark.parametrize('sequence', [('length','length'), ('length','schema'), ('schema','length'),
                                      ('length','transient'), ('transient','length')])
def test_length_repair_and_transient_recovery_share_two_dispatches(sequence, retry_clock):
    sent = []
    def handler(_):
        kind = sequence[len(sent)]; sent.append(kind)
        if kind == 'transient':
            return httpx.Response(503)
        return httpx.Response(200, json=envelope('{' if kind == 'length' else '{}',
                                                finish='length' if kind == 'length' else 'stop'))
    provider = StructuredProvider(replace(GEMINI_CONFIG, retry_truncated_extraction=True),
        token_counter=lambda _: 500, transport=httpx.MockTransport(handler))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError):
        run(provider, ledger)
    assert provider.requests_used == 2 and ledger.calls == {'extraction': 2}
    assert ledger.output_tokens <= 4000


def test_length_regeneration_respects_remaining_tokens_and_request_cap():
    for config, ledger, code in [
        (replace(GEMINI_CONFIG, retry_truncated_extraction=True), AttemptBudget(output_tokens=1000), 'token_budget_exhausted'),
        (replace(GEMINI_CONFIG, retry_truncated_extraction=True, max_requests=1), AttemptBudget(), 'free_request_quota_exhausted'),
    ]:
        provider = StructuredProvider(config, token_counter=lambda _: 500,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope('{', finish='length'))))
        with pytest.raises(ProviderError, match=code):
            run(provider, ledger)
        assert provider.requests_used == 1
        assert ledger.output_tokens >= 1800


def test_length_regeneration_keeps_original_deadline(retry_clock, monkeypatch):
    now, _ = retry_clock
    provider = StructuredProvider(replace(GEMINI_CONFIG, extraction_seconds=30, retry_truncated_extraction=True),
                                  token_counter=lambda _: 500)
    timeouts = []
    async def request(_, timeout):
        timeouts.append(timeout)
        now[0] += 22 if len(timeouts) == 1 else 3
        return envelope('{' if len(timeouts) == 1 else '{"ok":true}',
                        finish='length' if len(timeouts) == 1 else 'stop')
    monkeypatch.setattr(provider, '_request', request)
    result = run(provider)
    assert timeouts == [30, 8] and result.latency_seconds == 25


def test_length_regeneration_configuration_is_explicit_boolean(monkeypatch):
    monkeypatch.delenv('EVIDENCELOOP_RETRY_TRUNCATED_EXTRACTION', raising=False)
    assert ProviderConfig.from_env().retry_truncated_extraction is False
    monkeypatch.setenv('EVIDENCELOOP_RETRY_TRUNCATED_EXTRACTION','true')
    assert ProviderConfig.from_env().retry_truncated_extraction is True
    with pytest.raises(ProviderError, match='invalid_provider_configuration'):
        replace(GEMINI_CONFIG, retry_truncated_extraction='true').require_enabled()


@pytest.mark.parametrize("config", [CONFIG, GEMINI_CONFIG])
def test_semantic_policy_rejection_is_not_retried(config):
    provider = StructuredProvider(config, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=envelope())))
    def reject(_):
        raise ValueError("raw text should not leak")
    with pytest.raises(ProviderError, match="candidate_admission_failed"):
        run(provider, validator=reject)
    assert provider.requests_used == 1


def test_schema_repair_must_fit_remaining_token_budget():
    provider = StructuredProvider(CONFIG, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=envelope('{}', usage=False))))
    ledger = AttemptBudget(output_tokens=1000)
    with pytest.raises(ProviderError, match="token_budget_exhausted"):
        run(provider, ledger)
    assert provider.requests_used == 1


def test_cumulative_time_budget_and_human_dwell(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.provider.time.monotonic", lambda: now[0])
    ledger = AttemptBudget()
    with ledger.meter():
        now[0] += 3
        with ledger.meter():
            now[0] += 2
    assert ledger.automated_seconds == 5
    now[0] += 3600  # confirmation dwell is outside a metered endpoint
    assert ledger.remaining_seconds == 35
    with ledger.meter():
        now[0] += 35
    with pytest.raises(ProviderError, match="time_budget_exhausted"):
        run(StructuredProvider(CONFIG), ledger)


def test_stage_deadline_includes_counting_and_does_not_reset_for_repair(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.provider.time", SimpleNamespace(monotonic=lambda: now[0]))
    def counter(_):
        now[0] += 1
        return 500
    provider = StructuredProvider(CONFIG, token_counter=counter)
    timeouts = []
    async def request(_, timeout):
        timeouts.append(timeout)
        now[0] += 5 if len(timeouts) == 1 else 2
        return envelope('{}' if len(timeouts) == 1 else '{"ok":true}')
    monkeypatch.setattr(provider, "_request", request)
    result = run(provider)
    assert result.repair_count == 1
    assert timeouts == [9, 3]
    assert result.latency_seconds == 9


@pytest.mark.parametrize('value', ['bad', 'nan', 'inf', '9.9', '30.1', '-1'])
def test_extraction_deadline_configuration_rejects_invalid_or_unbounded_values(monkeypatch, value):
    monkeypatch.setenv('EVIDENCELOOP_EXTRACTION_SECONDS', value)
    config = replace(CONFIG, extraction_seconds=ProviderConfig.from_env().extraction_seconds)
    with pytest.raises(ProviderError, match='invalid_provider_configuration'):
        config.require_enabled()


def test_extraction_deadline_default_and_explicit_environment_setting(monkeypatch):
    monkeypatch.delenv('EVIDENCELOOP_EXTRACTION_SECONDS', raising=False)
    assert ProviderConfig.from_env().extraction_seconds == 10
    monkeypatch.setenv('EVIDENCELOOP_EXTRACTION_SECONDS', '30')
    assert ProviderConfig.from_env().extraction_seconds == 30
    with pytest.raises(ProviderError, match='invalid_provider_configuration'):
        replace(CONFIG, extraction_seconds=True).require_enabled()


def test_extended_extraction_shares_deadline_across_counting_and_repair(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('app.provider.time', SimpleNamespace(monotonic=lambda: now[0]))
    def counter(_):
        now[0] += 1
        return 500
    provider = StructuredProvider(replace(CONFIG, extraction_seconds=30), token_counter=counter)
    timeouts = []
    async def request(_, timeout):
        timeouts.append(timeout)
        now[0] += 19 if len(timeouts) == 1 else 2
        return envelope('{}' if len(timeouts) == 1 else '{"ok":true}')
    monkeypatch.setattr(provider, '_request', request)
    ledger = AttemptBudget()
    result = run(provider, ledger)
    assert timeouts == [29, 9]
    assert result.repair_count == 1 and ledger.calls == {'extraction': 2}
    assert result.latency_seconds == ledger.automated_seconds == 23
    assert ledger.input_tokens == 200 and ledger.output_tokens == 40


def test_extended_extraction_does_not_extend_alignment_or_cumulative_budget(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('app.provider.time', SimpleNamespace(monotonic=lambda: now[0]))
    provider = StructuredProvider(replace(CONFIG, extraction_seconds=30), token_counter=lambda _: 500)
    timeouts = []
    async def request(_, timeout):
        timeouts.append(timeout)
        now[0] += 29 if len(timeouts) == 1 else 10
        return envelope()
    monkeypatch.setattr(provider, '_request', request)
    ledger = AttemptBudget()
    run(provider, ledger)
    asyncio.run(provider.call('alignment', {}, SCHEMA, ledger))
    assert timeouts == [30, 11]
    assert ledger.automated_seconds == 39
    # A fresh ledger still has the unchanged fourteen-second alignment cap.
    asyncio.run(provider.call('alignment', {}, SCHEMA, AttemptBudget()))
    assert timeouts[-1] == 14


def test_extended_extraction_admission_cannot_cross_thirty_seconds(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('app.provider.time', SimpleNamespace(monotonic=lambda: now[0]))
    provider = StructuredProvider(replace(CONFIG, extraction_seconds=30), token_counter=lambda _: 500)
    async def request(_, timeout):
        return envelope()
    monkeypatch.setattr(provider, '_request', request)
    def admission(_):
        now[0] += 30.1
    with pytest.raises(ProviderError, match='stage_time_budget_exhausted'):
        run(provider, validator=admission)
    assert provider.requests_used == 1


def test_exhausted_stage_does_not_dispatch_a_repair(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.provider.time", SimpleNamespace(monotonic=lambda: now[0]))
    provider = StructuredProvider(CONFIG, token_counter=lambda _: 500)
    async def request(_, timeout):
        now[0] += 10
        return envelope('{}')
    monkeypatch.setattr(provider, "_request", request)
    with pytest.raises(ProviderError, match="stage_time_budget_exhausted"):
        run(provider)
    assert provider.requests_used == 1


def test_admission_cannot_return_a_result_after_stage_deadline(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.provider.time", SimpleNamespace(monotonic=lambda: now[0]))
    provider = StructuredProvider(CONFIG, token_counter=lambda _: 500)
    async def request(_, timeout):
        return envelope()
    monkeypatch.setattr(provider, "_request", request)
    def admission(_):
        now[0] += 10.1
    with pytest.raises(ProviderError, match="stage_time_budget_exhausted"):
        run(provider, validator=admission)


def test_stage_limits_and_request_cap_preflight():
    provider = StructuredProvider(CONFIG, token_counter=lambda _: 3501)
    with pytest.raises(ProviderError, match="stage_input_budget_exceeded"):
        run(provider)
    assert provider.requests_used == 0
    provider = StructuredProvider(replace(CONFIG, max_requests=1), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=envelope('{}'))))
    with pytest.raises(ProviderError, match="free_request_quota_exhausted"):
        run(provider)
    assert provider.requests_used == 1


def test_provider_undercount_aborts_instead_of_silently_overrunning():
    bad_usage = envelope()
    bad_usage["usage"]["completion_tokens"] = 1900
    provider = StructuredProvider(CONFIG, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=bad_usage)))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match="provider_token_bound_violation"):
        run(provider, ledger)
    assert ledger.output_tokens == 1900


def test_cancellation_retains_ledger_and_terminal_stage():
    async def handler(_):
        raise asyncio.CancelledError()
    provider = StructuredProvider(CONFIG, transport=httpx.MockTransport(handler))
    ledger = AttemptBudget()
    with pytest.raises(asyncio.CancelledError):
        run(provider, ledger)
    assert ledger.calls == {"extraction": 1} and "extraction" in ledger.terminal_stages
    assert not ledger._inflight


def test_no_external_schema_fetch():
    with pytest.raises(ProviderError, match="external_schema_reference"):
        asyncio.run(StructuredProvider(CONFIG).call("extraction", {},
            {"$ref": "https://example.invalid/schema"}, AttemptBudget()))


@pytest.mark.parametrize("url", ["http://remote.test/v1", "https://user:secret@host/v1",
                                    "https://host/v1?api_key=secret"])
def test_remote_cleartext_and_url_credentials_rejected(url):
    with pytest.raises(ProviderError, match="invalid_provider_configuration"):
        run(StructuredProvider(replace(CONFIG, base_url=url)))


def test_parallel_calls_on_same_attempt_are_rejected():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(_):
            entered.set()
            await release.wait()
            return httpx.Response(200, json=envelope())
        provider = StructuredProvider(CONFIG, transport=httpx.MockTransport(handler))
        ledger = AttemptBudget()
        first = asyncio.create_task(provider.call("extraction", {}, SCHEMA, ledger))
        await entered.wait()
        with pytest.raises(ProviderError, match="attempt_in_progress"):
            await provider.call("alignment", {}, SCHEMA, ledger)
        release.set()
        await first
    asyncio.run(scenario())


def test_schema_compaction_preserves_literal_values_and_property_names():
    schema = {"title": "annotations can go", "type": "object", "properties": {
        "title": {"type": "string", "title": "this annotation can go"},
        "literal": {"const": {"title": "literal", "default": 3}}}}
    compact = compact_schema(schema)
    assert "title" not in compact
    assert compact["properties"]["title"] == {"type": "string"}
    assert compact["properties"]["literal"]["const"] == {"title": "literal", "default": 3}


def test_gemini_projection_is_wire_only_and_local_bounds_still_reject():
    schema = {"type":"object", "properties":{"value":{"type":"string","maxLength":3}},
              "required":["value"], "additionalProperties":False}
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200,json=envelope('{"value":"too long"}'))
    config = replace(CONFIG,base_url="https://generativelanguage.googleapis.com/v1beta/openai",api_key="mock")
    provider = StructuredProvider(config,transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError,match="invalid_structured_output"):
        asyncio.run(provider.call("extraction",{},schema,AttemptBudget()))
    assert len(seen) == 2
    assert "maxLength" not in seen[0]["response_format"]["json_schema"]["schema"]["properties"]["value"]
    assert schema["properties"]["value"]["maxLength"] == 3
    local_body = StructuredProvider(CONFIG)._body("extraction",{},schema,0)
    assert local_body["response_format"]["json_schema"]["schema"]["properties"]["value"]["maxLength"] == 3


def test_async_verified_token_counter_is_supported_and_settled():
    async def count(_):
        return 108
    provider = StructuredProvider(CONFIG, token_counter=count, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=envelope())))
    ledger = AttemptBudget()
    run(provider, ledger)
    assert ledger.input_tokens == 100


def test_model_metadata_cannot_smuggle_raw_free_text():
    response = envelope()
    response["model"] = "private health text must not become audit metadata"
    provider = StructuredProvider(CONFIG, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=response)))
    with pytest.raises(ProviderError, match="invalid_provider_envelope"):
        run(provider)


def test_concurrent_attempts_recheck_quota_after_async_token_count():
    async def scenario():
        both_counting, release = asyncio.Event(), asyncio.Event()
        count_calls = 0
        generation_calls = 0

        async def count(_):
            nonlocal count_calls
            count_calls += 1
            if count_calls == 2:
                both_counting.set()
            await release.wait()
            return 500

        def handler(_):
            nonlocal generation_calls
            generation_calls += 1
            return httpx.Response(200, json=envelope())

        provider = StructuredProvider(replace(CONFIG, max_requests=1), token_counter=count,
                                      transport=httpx.MockTransport(handler))
        ledgers = [AttemptBudget(), AttemptBudget()]
        tasks = [asyncio.create_task(provider.call("extraction", {}, SCHEMA, ledger))
                 for ledger in ledgers]
        await asyncio.wait_for(both_counting.wait(), 1)
        release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)

        denied = [i for i, result in enumerate(results) if isinstance(result, ProviderError)]
        assert len(denied) == 1
        assert results[denied[0]].code == "free_request_quota_exhausted"
        winner = 1 - denied[0]
        assert results[winner].payload == {"ok": True}
        assert generation_calls == provider.requests_used == 1
        assert ledgers[winner].calls == {"extraction": 1}
        assert (ledgers[winner].input_tokens, ledgers[winner].output_tokens) == (100, 20)
        assert ledgers[denied[0]].calls == {}
        assert (ledgers[denied[0]].input_tokens, ledgers[denied[0]].output_tokens) == (0, 0)
        assert all(ledger.terminal_stages == {"extraction"} and not ledger._inflight
                   for ledger in ledgers)
        with pytest.raises(ProviderError, match="free_request_quota_exhausted"):
            await provider.call("extraction", {}, SCHEMA, AttemptBudget())
        assert count_calls == 2

    asyncio.run(scenario())


def test_deeply_nested_outer_envelope_fails_closed_without_repair():
    calls = 0
    raw = b'{"private":"RAW TEXT MUST NOT LEAK","ignored":' + b"[" * 12000 + b"0" + b"]" * 12000 + b"}"

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=raw)

    provider = StructuredProvider(CONFIG, token_counter=lambda _: 500,
                                  transport=httpx.MockTransport(handler))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match="^invalid_provider_envelope$") as error:
        run(provider, ledger)
    assert "RAW TEXT" not in str(error.value)
    assert calls == provider.requests_used == 1
    assert ledger.calls == {"extraction": 1}
    assert (ledger.input_tokens, ledger.output_tokens) == (500, 1800)
    assert ledger.terminal_stages == {"extraction"} and not ledger._inflight


@pytest.fixture
def retry_clock(monkeypatch):
    now, sleeps = [100.0], []
    monkeypatch.setattr("app.provider.time", SimpleNamespace(monotonic=lambda: now[0]))

    async def sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    monkeypatch.setattr("app.provider.asyncio.sleep", sleep)
    return now, sleeps


@pytest.mark.parametrize("status", [502, 503, 504])
def test_gemini_transient_retry_preserves_prompt_reservations_and_dispatch_limits(status, retry_clock):
    _, sleeps = retry_clock
    bodies, counts = [], []

    async def counter(body):
        counts.append(body)
        return 500

    def handler(request):
        bodies.append(json.loads(request.content))
        return (httpx.Response(status, text="PRIVATE FAILURE BODY") if len(bodies) == 1
                else httpx.Response(200, json=envelope()))

    provider = StructuredProvider(replace(GEMINI_CONFIG, max_requests_per_minute=2),
                                  token_counter=counter, transport=httpx.MockTransport(handler))
    ledger = AttemptBudget()
    result = run(provider, ledger)
    assert result.payload == {"ok": True}
    assert result.repair_count == 0 and result.transient_retry_count == 1
    assert result.usage.estimated
    assert (result.usage.input_tokens, result.usage.output_tokens) == (600, 1820)
    assert (ledger.input_tokens, ledger.output_tokens) == (600, 1820)
    assert sleeps == [1.0] and result.latency_seconds == ledger.automated_seconds == 1.0
    assert len(bodies) == len(counts) == provider.requests_used == 2
    assert bodies[0] == bodies[1] and counts[0] == counts[1]
    assert "Previous response failed" not in bodies[1]["messages"][0]["content"]
    assert ledger.calls == {"extraction": 2}
    # Both actual attempts consume the local rolling window; deny before count.
    with pytest.raises(ProviderError, match="^local_rate_limit_reached$"):
        run(provider)
    assert len(counts) == 2 and provider.requests_used == 2


@pytest.mark.parametrize("responses,code,repair_prompt,usage", [
    ([503, 503], "provider_temporarily_unavailable", False, (1000, 3600)),
    ([503, "{}"], "invalid_structured_output", False, (600, 1820)),
    (["{}", 503], "provider_temporarily_unavailable", True, (600, 1820)),
])
def test_transport_retry_and_schema_repair_share_two_attempts(
        responses, code, repair_prompt, usage, retry_clock):
    _, sleeps = retry_clock
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        response = responses[len(bodies) - 1]
        return (httpx.Response(response) if isinstance(response, int)
                else httpx.Response(200, json=envelope(response)))

    provider = StructuredProvider(GEMINI_CONFIG, token_counter=lambda _: 500,
                                  transport=httpx.MockTransport(handler))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match=f"^{code}$"):
        run(provider, ledger)
    assert len(bodies) == provider.requests_used == 2
    assert (ledger.input_tokens, ledger.output_tokens) == usage
    assert ("Previous response failed" in bodies[1]["messages"][0]["content"]) is repair_prompt
    assert sleeps == ([] if repair_prompt else [1.0])
    assert ledger.calls == {"extraction": 2} and ledger.terminal_stages == {"extraction"}


@pytest.mark.parametrize("config,stage", [
    (CONFIG, "extraction"), (GEMINI_CONFIG, "alignment"),
    (replace(GEMINI_CONFIG, model="other-model"), "extraction"),
    (replace(GEMINI_CONFIG, base_url="https://example.invalid/v1"), "extraction"),
])
def test_transient_retry_is_exclusive_to_official_gemini_extraction(config, stage, retry_clock):
    _, sleeps = retry_clock
    provider = StructuredProvider(config, token_counter=lambda _: 500,
                                  transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    with pytest.raises(ProviderError, match="^provider_temporarily_unavailable$"):
        asyncio.run(provider.call(stage, {}, SCHEMA, AttemptBudget()))
    assert provider.requests_used == 1 and sleeps == []


@pytest.mark.parametrize("status,code", [
    (429, "provider_quota_exhausted"), (401, "provider_access_denied"),
    (403, "provider_access_denied"), (400, "provider_http_error"),
    (500, "provider_http_error"),
])
def test_gemini_other_http_errors_are_terminal(status, code, retry_clock):
    _, sleeps = retry_clock
    provider = StructuredProvider(GEMINI_CONFIG, token_counter=lambda _: 500,
                                  transport=httpx.MockTransport(lambda _: httpx.Response(status)))
    with pytest.raises(ProviderError, match=f"^{code}$"):
        run(provider)
    assert provider.requests_used == 1 and sleeps == []


def test_token_counter_transient_failure_never_retries(retry_clock):
    _, sleeps = retry_clock
    calls = []

    async def counter(_):
        calls.append(True)
        raise ProviderError("provider_temporarily_unavailable")

    provider = StructuredProvider(GEMINI_CONFIG, token_counter=counter)
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match="^provider_temporarily_unavailable$"):
        run(provider, ledger)
    assert calls == [True] and sleeps == [] and provider.requests_used == 0
    assert ledger.calls == {} and (ledger.input_tokens, ledger.output_tokens) == (0, 0)


@pytest.mark.parametrize("automated_seconds,expected_timeouts", [(0, [9.5, 7.5]), (33, [6.5, 4.5])])
def test_transient_retry_keeps_stage_and_cumulative_deadlines(
        automated_seconds, expected_timeouts, retry_clock, monkeypatch):
    now, sleeps = retry_clock
    timeouts = []

    def counter(_):
        now[0] += 0.5
        return 500

    async def request(_, timeout):
        timeouts.append(timeout)
        now[0] += 0.5
        if len(timeouts) == 1:
            raise ProviderError("provider_temporarily_unavailable")
        return envelope()

    provider = StructuredProvider(GEMINI_CONFIG, token_counter=counter)
    monkeypatch.setattr(provider, "_request", request)
    ledger = AttemptBudget(automated_seconds=automated_seconds)
    result = run(provider, ledger)
    assert timeouts == expected_timeouts and sleeps == [1.0]
    assert result.latency_seconds == 3.0 and ledger.automated_seconds == automated_seconds + 3.0


@pytest.mark.parametrize("automated_seconds,elapsed", [(0, 9.25), (39, 0)])
def test_insufficient_time_for_retry_delay_never_dispatches_again(
        automated_seconds, elapsed, retry_clock, monkeypatch):
    now, sleeps = retry_clock

    async def request(_, timeout):
        now[0] += elapsed
        raise ProviderError("provider_temporarily_unavailable")

    provider = StructuredProvider(GEMINI_CONFIG, token_counter=lambda _: 500)
    monkeypatch.setattr(provider, "_request", request)
    ledger = AttemptBudget(automated_seconds=automated_seconds)
    with pytest.raises(ProviderError, match="^stage_time_budget_exhausted$"):
        run(provider, ledger)
    assert provider.requests_used == 1 and sleeps == []
    assert (ledger.input_tokens, ledger.output_tokens) == (500, 1800)


@pytest.mark.parametrize("config,initial_output,code", [
    (replace(GEMINI_CONFIG, max_requests=1), 0, "free_request_quota_exhausted"),
    (replace(GEMINI_CONFIG, max_requests_per_minute=1), 0, "local_rate_limit_reached"),
    (GEMINI_CONFIG, 1000, "token_budget_exhausted"),
])
def test_retry_limits_deny_before_delay_and_second_token_count(config, initial_output, code, retry_clock):
    _, sleeps = retry_clock
    counts = []

    def counter(_):
        counts.append(True)
        return 500

    provider = StructuredProvider(config, token_counter=counter,
                                  transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    ledger = AttemptBudget(output_tokens=initial_output)
    with pytest.raises(ProviderError, match=f"^{code}$"):
        run(provider, ledger)
    assert provider.requests_used == 1 and sleeps == [] and counts == [True]
    assert (ledger.input_tokens, ledger.output_tokens) == (500, initial_output + 1800)


def test_cancellation_during_retry_delay_keeps_failed_reservation(monkeypatch):
    async def cancelled_sleep(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr("app.provider.asyncio.sleep", cancelled_sleep)
    provider = StructuredProvider(GEMINI_CONFIG, token_counter=lambda _: 500,
                                  transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    ledger = AttemptBudget()
    with pytest.raises(asyncio.CancelledError):
        run(provider, ledger)
    assert provider.requests_used == 1 and (ledger.input_tokens, ledger.output_tokens) == (500, 1800)
    assert ledger.terminal_stages == {"extraction"} and not ledger._inflight


@pytest.mark.parametrize("value,expected", [("0", 0), ("15", 15)])
def test_optional_local_request_pacing_environment(monkeypatch, value, expected):
    monkeypatch.setenv("EVIDENCELOOP_MAX_MODEL_REQUESTS_PER_MINUTE", value)
    assert ProviderConfig.from_env().max_requests_per_minute == expected


@pytest.mark.parametrize("value", ["invalid", "-1", "1.5"])
def test_invalid_explicit_request_pacing_does_not_disable_guard(monkeypatch, value):
    monkeypatch.setenv("EVIDENCELOOP_MAX_MODEL_REQUESTS_PER_MINUTE", value)
    config = replace(CONFIG, max_requests_per_minute=ProviderConfig.from_env().max_requests_per_minute)
    with pytest.raises(ProviderError, match="^invalid_provider_configuration$"):
        config.require_enabled()


def test_schema_repair_counts_against_local_request_window(retry_clock):
    counts = []

    def counter(_):
        counts.append(True)
        return 500

    provider = StructuredProvider(replace(CONFIG, max_requests_per_minute=1), token_counter=counter,
                                  transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope('{}'))))
    ledger = AttemptBudget()
    with pytest.raises(ProviderError, match="^local_rate_limit_reached$"):
        run(provider, ledger)
    assert counts == [True] and provider.requests_used == 1
    assert (ledger.input_tokens, ledger.output_tokens) == (100, 20)


def test_concurrent_attempts_recheck_local_window_and_expire_at_sixty_seconds(retry_clock):
    now, _ = retry_clock

    async def scenario():
        both_counting, release = asyncio.Event(), asyncio.Event()
        count_calls = 0

        async def counter(_):
            nonlocal count_calls
            count_calls += 1
            if count_calls == 2:
                both_counting.set()
            await release.wait()
            return 500

        provider = StructuredProvider(replace(CONFIG, max_requests_per_minute=1), token_counter=counter,
                                      transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope())))
        ledgers = [AttemptBudget(), AttemptBudget()]
        tasks = [asyncio.create_task(provider.call("extraction", {}, SCHEMA, ledger)) for ledger in ledgers]
        await asyncio.wait_for(both_counting.wait(), 1)
        release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        denied = [i for i, result in enumerate(results) if isinstance(result, ProviderError)]
        assert len(denied) == 1 and results[denied[0]].code == "local_rate_limit_reached"
        denied_ledger = ledgers[denied[0]]
        assert denied_ledger.calls == {} and (denied_ledger.input_tokens, denied_ledger.output_tokens) == (0, 0)
        assert provider.requests_used == 1
        now[0] = 159.999
        with pytest.raises(ProviderError, match="^local_rate_limit_reached$"):
            await provider.call("extraction", {}, SCHEMA, AttemptBudget())
        assert count_calls == 2
        now[0] = 160.0
        result = await provider.call("extraction", {}, SCHEMA, AttemptBudget())
        assert result.payload == {"ok": True}
        assert provider.requests_used == 2 and count_calls == 3

    asyncio.run(scenario())
