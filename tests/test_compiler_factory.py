import asyncio
from dataclasses import replace

import pytest

from services.api.app import domain
from services.api.app.compiler import ClaimCompiler
from services.api.app.gemini import GeminiTokenCounter, OFFICIAL_BASE
from services.api.app.provider import AttemptBudget, ProviderConfig, conservative_input_bound


VALID = ProviderConfig(enabled=True, base_url=OFFICIAL_BASE, model="gemini-2.5-flash-lite",
    api_key="FAKE-NONSECRET-KEY", free_budget_verified=True, billing_disabled=True,
    schema_capability_verified=True, verification_reference="mock-only", max_requests=2)


def factory(monkeypatch, config, *, alignment=False):
    monkeypatch.setattr(ProviderConfig, "from_env", classmethod(lambda cls: config))
    return ClaimCompiler(alignment_enabled=alignment)


@pytest.mark.parametrize("config,code", [
    (replace(VALID, model="gemini-invalid/path"), "invalid_gemini_counter_configuration"),
    (replace(VALID, api_key="FAKE\nHEADER"), "invalid_gemini_counter_configuration"),
    (replace(VALID, enabled=False), "live_inference_disabled"),
    (replace(VALID, free_budget_verified=False), "free_runtime_unverified"),
])
def test_invalid_gemini_factory_preserves_startup_but_prevents_direct_extraction(monkeypatch, config, code):
    compiler = factory(monkeypatch, config)
    assert not compiler.available and not compiler.alignment_available
    assert compiler.extraction_scope is None
    assert compiler.provider.config.enabled is False
    async def forbidden(*args, **kwargs):
        raise AssertionError("Invalid configuration must never dispatch to the provider")
    monkeypatch.setattr(compiler.provider, "call", forbidden)
    ledger = AttemptBudget()
    result = asyncio.run(compiler.extract("Fictional quiet cards improve recall.", {"action_kind": "learn"}, ledger))
    assert result["mode"] == "manual" and result["system_status"] == "model_error"
    assert code in result["reason_codes"]
    assert not ledger.calls and compiler.provider.requests_used == 0
    # Replay/domain behavior still works independently of the unavailable model.
    fixture = domain.fixture_catalog()[0]
    assert domain.interpret(fixture["text"], fixture["intent"])["mode"] == "replay"


def test_invalid_gemini_factory_also_prevents_direct_live_alignment(monkeypatch):
    compiler = factory(monkeypatch, replace(VALID, model="gemini-invalid/path"), alignment=True)
    async def forbidden(*args, **kwargs):
        raise AssertionError("Invalid configuration must never dispatch to the provider")
    monkeypatch.setattr(compiler.provider, "call", forbidden)
    fixture = domain.fixture_catalog()[0]
    captured = domain.interpret(fixture["text"], fixture["intent"])
    confirmed = domain.confirm(captured["claim"], captured["intent"])
    ledger = AttemptBudget()
    result = asyncio.run(compiler.assess(confirmed["snapshot"], confirmed["intent"], domain.load_pack(), ledger))
    assert result["system_status"] == "model_error" and result["alignment_mode"] == "failed"
    assert "invalid_gemini_counter_configuration" in result["reason_codes"]
    assert not ledger.calls


def test_valid_official_gemini_configuration_uses_native_counter_without_network(monkeypatch):
    compiler = factory(monkeypatch, VALID)
    assert compiler.available and compiler.extraction_scope == "remote"
    assert isinstance(compiler.provider.token_counter, GeminiTokenCounter)
    assert compiler.provider.requests_used == compiler.provider.token_counter.requests_used == 0


def test_legitimate_generic_provider_retains_its_existing_behavior(monkeypatch):
    config = replace(VALID, base_url="https://example.invalid/v1", model="test-free-model")
    compiler = factory(monkeypatch, config)
    assert compiler.available and compiler.extraction_scope == "remote"
    assert compiler.provider.config is config
    assert compiler.provider.token_counter is conservative_input_bound


def test_disabled_configuration_can_still_show_library_context_without_a_verdict(monkeypatch):
    compiler = factory(monkeypatch, replace(VALID, enabled=False))
    fixture = domain.fixture_catalog()[0]
    captured = domain.interpret(fixture["text"], fixture["intent"])
    confirmed = domain.confirm(captured["claim"], captured["intent"])
    result = asyncio.run(compiler.assess(confirmed["snapshot"], confirmed["intent"], domain.load_pack(), AttemptBudget()))
    assert result["alignment_mode"] == "extraction_only"
    assert result["evidence_status"] == "not_assessable"
    assert result["system_status"] == "ok"
