"""Engineering assertions for denominators, quota, seal custody and offline transport."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app import domain
from app.compiler import ClaimCompiler
from app.provider import AttemptBudget, ProviderConfig, ProviderError
from evals.harness.quota import FreeQuota
from evals.harness.runner import (ComparisonProvider, attempt, builtin_cases, claim_seal, digest,
                                  execute, load_cases, parser, retrieve, schedule, summarize)


def configured(max_requests=10):
    return ProviderConfig(enabled=True, base_url='http://127.0.0.1:8999/v1', model='test-model-v1',
        free_budget_verified=True, billing_disabled=True, schema_capability_verified=True,
        verification_reference='mock transport only; no account', max_requests=max_requests)


def quota_file(path, **overrides):
    value = {'model': 'test-model-v1', 'billing_disabled': True, 'additional_spend_limit': 0,
        'verification_reference': 'test-only capacity; no real provider',
        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        'remaining_calls': 8, 'remaining_input_tokens': 22000, 'remaining_output_tokens': 8000,
        'requests_per_minute': 100, 'tokens_per_minute': 100000, 'max_concurrency': 5}
    path.write_text(json.dumps({**value, **overrides}), encoding='utf-8')
    return path


def response(answer='A test-only offline answer.'):
    return httpx.Response(200, json={'model': 'test-model-v1',
        'usage': {'prompt_tokens': 80, 'completion_tokens': 15},
        'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'answer': answer, 'citations': []})}}]})


def test_builtin_counts_and_protocol_denominators():
    cases = builtin_cases()
    assert len([case for case in cases if case['kind'] == 'nonclinical_fixture']) == 14
    assert len([case for case in cases if case['kind'] == 'internal_policy_fixture']) == 3
    work = schedule(cases, ['candidate', 'plain', 'retrieval'], latency=True, stress=True)
    assert len(work) == 17 * 3 + 165 + 15
    for variant in ('candidate', 'plain', 'retrieval'):
        assert sum(item['variant'] == variant and item['phase'] == 'latency' for item in work) == 50
        assert sum(item['variant'] == variant and item['phase'] == 'latency_warmup' for item in work) == 5
        assert sum(item['variant'] == variant and item['phase'] == 'stress' for item in work) == 5


def test_cross_partition_component_and_real_data_are_rejected(tmp_path):
    cases = builtin_cases()[:2]
    cases[0]['partition'] = 'development'
    cases[1]['partition'] = 'sealed'
    path = tmp_path / 'cases.jsonl'
    path.write_text('\n'.join(json.dumps(case) for case in cases), encoding='utf-8')
    with pytest.raises(ValueError, match='crosses partitions'): load_cases(path)
    cases[1]['partition'] = 'development'
    cases[1]['synthetic'] = False
    path.write_text('\n'.join(json.dumps(case) for case in cases), encoding='utf-8')
    with pytest.raises(ValueError, match='fictional-data'): load_cases(path)


def test_quota_is_zero_spend_expiring_and_cumulative(tmp_path):
    path = quota_file(tmp_path / 'quota.json')
    FreeQuota(path, 'test-model-v1').reserve('run-a/one', 4)
    FreeQuota(path, 'test-model-v1').reserve('run-b/one', 4)
    after = path.read_bytes()
    with pytest.raises(ValueError, match='insufficient'): FreeQuota(path, 'test-model-v1').reserve('run-c/one', 1)
    assert path.read_bytes() == after
    quota_file(path, billing_disabled=False)
    with pytest.raises(ValueError, match='disabled billing'): FreeQuota(path, 'test-model-v1')
    quota_file(path, expires_at='2020-01-01T00:00:00Z')
    with pytest.raises(ValueError, match='expired'): FreeQuota(path, 'test-model-v1')


def test_failed_or_started_seal_cannot_be_reused_in_another_directory(tmp_path):
    cases = builtin_cases()[:1]
    cases[0]['partition'] = 'sealed'
    custody = {'seal_id': 'test-seal', 'custodian': 'test-custodian', 'independence_attested': True,
        'case_hash': digest(cases), 'schedule_hash': digest([]), 'labels_frozen_at': '2026-09-30T00:00:00Z'}
    path = tmp_path / 'custody.json'
    path.write_text(json.dumps(custody), encoding='utf-8')
    claim_seal(path, cases, 'frozen-manifest', tmp_path / 'first', tmp_path / 'registry')
    with pytest.raises(ValueError, match='already been executed or started'):
        claim_seal(path, cases, 'changed-manifest', tmp_path / 'second', tmp_path / 'registry')


def test_baselines_share_model_request_cap_and_never_receive_gold():
    seen = []
    def transport(request):
        seen.append(json.loads(request.content))
        return response()
    provider = ComparisonProvider(configured(2), transport=httpx.MockTransport(transport), token_counter=lambda _: 100)
    case, pack = builtin_cases()[0], domain.load_pack()
    async def run():
        await provider.baseline(case, 'plain', pack, AttemptBudget())
        await provider.baseline(case, 'retrieval', pack, AttemptBudget())
        with pytest.raises(ProviderError, match='free_request_quota_exhausted'):
            await provider.baseline(case, 'plain', pack, AttemptBudget())
    asyncio.run(run())
    assert provider.requests_used == 2
    first = json.loads(seen[0]['messages'][1]['content'])
    second = json.loads(seen[1]['messages'][1]['content'])
    assert 'expected' not in first and 'label_provenance' not in first and 'evidence' not in first
    assert first['claim'] == second['claim'] and first['explicit_intent'] == second['explicit_intent']
    assert second['evidence']['conclusions'] and len(second['evidence']['conclusions']) <= 8
    assert all(body['model'] == 'test-model-v1' and body['max_tokens'] == 4000 for body in seen)


def test_retrieval_keeps_conflicts_and_blocks_withdrawn_dependencies():
    case = next(case for case in builtin_cases() if case['id'] == 'blue-conflicting')
    pack = domain.load_pack()
    assert len(retrieve(case, pack)['conclusions']) == 2
    next(source for source in pack['sources'] if source['source_id'] == 'SYN-BLUE-A')['trust_state'] = 'withdrawn'
    with pytest.raises(ProviderError, match='retrieval_source_not_current'): retrieve(case, pack)


def test_model_failure_remains_in_declared_check_and_completion_denominators():
    async def fail(text, intent, ledger):
        value = domain.interpret(text, intent, mode='manual')
        return {**value, 'system_status': 'model_error', 'reason_codes': ['provider_timeout']}
    provider = ComparisonProvider(configured())
    compiler = SimpleNamespace(provider=provider, extract=fail)
    case = builtin_cases()[0]
    item = schedule([case], ['candidate'])[0]
    record = asyncio.run(attempt(item, case, 'live', domain.load_pack(), compiler))
    assert record['status'] == 'failed' and record['error_code'] == 'provider_timeout'
    assert len(record['checks']) == 1 and record['checks'][0]['passed'] is False
    summary = summarize([record], [item])['variants']['candidate']
    assert summary['primary_attempts'] == 1 and summary['automatic_checks'] == {'passed': 0, 'denominator': 1}


def test_concurrent_attempts_keep_individual_call_events():
    async def transport(request):
        await asyncio.sleep(.001)
        return response()
    provider = ComparisonProvider(configured(), transport=httpx.MockTransport(transport), token_counter=lambda _: 100)
    compiler = ClaimCompiler(provider)
    case, pack = builtin_cases()[0], domain.load_pack()
    work = schedule([case], ['plain'], stress=True)[1:]
    async def run():
        return await asyncio.gather(*(attempt(item, case, 'live', pack, compiler) for item in work))
    records = asyncio.run(run())
    assert len(records) == 5 and provider.requests_used == 5
    assert all(len(row['call_events']) == 1 for row in records)
    assert summarize(records, work)['variants']['plain']['provider_calls'] == 5


def test_default_pilot_records_two_cases_and_refuses_overwrite(tmp_path, capsys):
    output = tmp_path / 'pilot'
    args = parser().parse_args(['--output', str(output)])
    assert asyncio.run(execute(args)) == 0
    summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
    assert summary['planned_attempts'] == summary['recorded_attempts'] == 2
    assert summary['variants']['candidate']['provider_calls'] == 0
    assert summary['clinical_validation'] == 'not established'
    assert len((output / 'output-review-queue.jsonl').read_text(encoding='utf-8').splitlines()) == 2
    with pytest.raises(ValueError, match='already exists'): asyncio.run(execute(args))
