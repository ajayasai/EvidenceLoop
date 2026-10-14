"""Bounded real extraction probe using frozen fictional inputs, never labels."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.api.app.compiler import ClaimCompiler
from services.api.app.provider import AttemptBudget, ProviderConfig, ProviderError, StructuredProvider


class FictionalProbeProvider(StructuredProvider):
    """Retain only output text from this fixed fictional corpus for diagnosis."""
    candidate_outputs: list[str]
    provider_errors: list[str]
    finish_metadata: list[dict]

    async def _request(self, body, timeout):
        try:
            envelope = await super()._request(body, timeout)
        except ProviderError as exc:
            self.provider_errors.append(exc.code)
            raise
        for choice in envelope.get('choices', []):
            content = choice.get('message', {}).get('content') if isinstance(choice, dict) else None
            if isinstance(content, str):
                self.candidate_outputs.append(content)
            if isinstance(choice, dict):
                reason = choice.get('finish_reason')
                usage = envelope.get('usage', {})
                usage = usage if isinstance(usage, dict) else {}
                details = usage.get('completion_tokens_details', {})
                details = details if isinstance(details, dict) else {}
                def count(value):
                    return value if type(value) is int and 0 <= value <= 100000000 else None
                self.finish_metadata.append({
                    'finish_reason': reason if isinstance(reason, str) and reason in {'stop','length','content_filter','tool_calls','function_call'} else 'unknown',
                    'reported_completion_tokens': count(usage.get('completion_tokens')),
                    'reported_reasoning_tokens': count(details.get('reasoning_tokens')),
                })
        return envelope


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def run(args):
    if not args.verified_free_reference:
        raise SystemExit('A dated verification reference for the unpaid account is required.')
    inputs = (args.corpus_root / f'{args.partition}.inputs.jsonl').resolve()
    frozen = json.loads((inputs.parent / 'manifest.json').read_text())
    if sha(inputs) != frozen['files_sha256'][inputs.name]:
        raise SystemExit('Frozen input hash changed.')
    records = [json.loads(line) for line in inputs.read_text(encoding='utf-8').splitlines() if line.strip()]
    if args.case_id:
        requested = set(args.case_id)
        if requested - {row['case_id'] for row in records}:
            raise SystemExit('Unknown development case ID.')
        records = [row for row in records if row['case_id'] in requested]
    records = records[:args.limit]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    private = dotenv_values(ROOT / '.env.ai', encoding='utf-8-sig')
    config = ProviderConfig(enabled=True, base_url=args.base_url, model=args.model,
        api_key=private.get('EVIDENCELOOP_MODEL_API_KEY') or '', free_budget_verified=True,
        billing_disabled=True, schema_capability_verified=True,
        verification_reference=args.verified_free_reference, max_requests=len(records)*2,
        max_requests_per_minute=args.max_requests_per_minute,
        extraction_seconds=args.stage_seconds,
        retry_truncated_extraction=args.retry_truncated_extraction,
        reasoning_effort=args.reasoning_effort,
        temperature=None if args.temperature == 'none' else float(args.temperature))
    config.require_enabled()
    provider = FictionalProbeProvider(config)
    # The adapter factory uses a service-specific counter only for the official
    # Gemini endpoint; all returned usage still passes the same hard bounds.
    if args.base_url.rstrip('/') == 'https://generativelanguage.googleapis.com/v1beta/openai':
        from services.api.app.gemini import GeminiTokenCounter
        provider.token_counter = GeminiTokenCounter(config)
    compiler = ClaimCompiler(provider, alignment_enabled=False)
    source_paths = [ROOT / 'services/api/app' / name for name in
                    ('compiler.py','provider.py','domain.py','contracts.py','gemini.py','gemini_schema.py','slot_extraction.py')]
    source_paths.append(Path(__file__).resolve())
    source_hashes = {str(path.relative_to(ROOT)):sha(path) for path in source_paths if path.exists()}
    manifest = {'kind':'fictional_extraction_probe','independent_clinical_review':False,
        'started_utc':datetime.now(timezone.utc).isoformat(), 'partition':args.partition,
        'benchmark_id':frozen['benchmark_id'],
        'model':config.model,'base_url':config.base_url,'reasoning_effort':config.reasoning_effort,
        'temperature':config.temperature,
        'free_verification':config.verification_reference,'planned_cases':[row['case_id'] for row in records],
        'input_sha256':sha(inputs),'code_sha256':source_hashes,'pause_seconds':args.pause_seconds,
        'stage_seconds':config.extraction_seconds,'max_model_requests':config.max_requests,'automatic_paid_fallback':False}
    manifest['max_generation_requests_per_minute'] = config.max_requests_per_minute
    manifest['retry_truncated_extraction'] = config.retry_truncated_extraction
    manifest['transient_recovery'] = 'At most one Gemini extraction 502/503/504 retry, sharing the original deadline and two-dispatch ceiling with schema repair.'
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    started, results = [], []
    with (output/'predictions.jsonl').open('x',encoding='utf-8') as stream:
        for index,item in enumerate(records):
            if index:
                await asyncio.sleep(args.pause_seconds)
            started.append({'case_id':item['case_id'],'utc':datetime.now(timezone.utc).isoformat()})
            (output/'started.json').write_text(json.dumps(started,indent=2),encoding='utf-8')
            before = time.monotonic()
            ledger = AttemptBudget()
            provider.candidate_outputs = []
            provider.provider_errors = []
            provider.finish_metadata = []
            result = await compiler.extract(item['text'],item['intent'],ledger)
            row = {'case_id':item['case_id'],'result':result,'wall_seconds':round(time.monotonic()-before,6),
                   'candidate_outputs':provider.candidate_outputs,'provider_errors':provider.provider_errors,
                   'finish_metadata':provider.finish_metadata}
            if result.get('system_status') == 'model_error':
                row['error'] = result['reason_codes'][-1]
            stream.write(json.dumps(row,ensure_ascii=False)+'\n'); stream.flush()
            results.append(row)
            print(json.dumps({'case_id':item['case_id'],'mode':result['mode'],
                'seconds':row['wall_seconds'],'error':row.get('error'),'budget':ledger.metadata()}),flush=True)
            if row.get('error') in {'provider_quota_exhausted','provider_access_denied','free_request_quota_exhausted',
                                   'local_rate_limit_reached','provider_timeout','token_counter_timeout',
                                   'stage_time_budget_exhausted',
                                   'provider_http_error','provider_temporarily_unavailable',
                                   'gemini_counter_quota_exhausted','gemini_counter_access_denied',
                                   'gemini_counter_model_unavailable'}:
                break
    unchanged = all(sha(ROOT / name)==digest for name,digest in source_hashes.items())
    summary = {'planned':len(records),'recorded':len(results),'unrecorded':len(records)-len(results),
        'model_requests':provider.requests_used,'code_unchanged':unchanged,
        'token_count_requests':getattr(provider.token_counter,'requests_used',0),
        'additional_paid_service_enabled':False,'quality_result':'Run the separate scorer; successful HTTP is not accuracy.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    return 0 if unchanged else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--partition',choices=['development','validation'],default='development')
    parser.add_argument('--corpus-root',type=Path,default=ROOT/'evals/extraction')
    parser.add_argument('--limit',type=int,choices=range(1,13),default=2)
    parser.add_argument('--case-id',action='append',help='Targeted development diagnostics only; never validation selection')
    parser.add_argument('--pause-seconds',type=float,default=25)
    parser.add_argument('--max-requests-per-minute',type=int,choices=range(1,31),default=5,
                        help='Verified project/model generation limit; counts repairs and transient recovery calls')
    parser.add_argument('--base-url',default='https://generativelanguage.googleapis.com/v1beta/openai')
    parser.add_argument('--model',default='gemini-3.8-flash')
    parser.add_argument('--reasoning-effort',default='low')
    parser.add_argument('--stage-seconds',type=int,choices=[10,30],default=10,
                        help='Explicit extraction deadline; does not change the frozen scorer or cumulative forty-second budget')
    parser.add_argument('--retry-truncated-extraction',action='store_true',
                        help='One Gemini length-stop regeneration sharing existing request, token and time budgets')
    parser.add_argument('--temperature',default='none',help='none omits deprecated sampling controls on newer Gemini models')
    parser.add_argument('--verified-free-reference',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    if args.case_id and args.partition != 'development':
        parser.error('Validation must not be selectively probed.')
    if args.pause_seconds < 6:
        parser.error('Keep at least six seconds between development requests.')
    raise SystemExit(asyncio.run(run(args)))
