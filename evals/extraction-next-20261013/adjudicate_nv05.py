"""Separate known-regression sensitivity analysis, never the sealed gate scorer."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from evals.extraction.score import load_corpus, read_jsonl, score_records


def score_with_recorded_adjudication(records, *, stage_seconds=10):
    if stage_seconds not in (10, 30):
        raise ValueError('Only the original or prospectively documented latency limit is permitted.')
    inputs, labels, manifest = load_corpus('validation', ROOT)
    manifest = deepcopy(manifest)
    manifest['engineering_gate']['extraction_stage_seconds_max'] = stage_seconds
    adjusted = deepcopy(labels)
    matched = False
    for record in records:
        if record.get('case_id') != 'NV05':
            continue
        props = record.get('result', {}).get('claim', {}).get('propositions', [])
        if not props:
            continue
        frame = props[0]
        def surface(name):
            field = frame.get(name, {})
            value = field.get('value')
            return value.get('surface') if field.get('state') == 'stated' and isinstance(value, dict) else None
        # Only this complete alternative pair is eligible, not independently
        # interchangeable field surfaces, duplicates, missing roles or unknowns.
        if (surface('intervention'), surface('measured_outcome')) == ('higher spool tension', 'grooved bobbins'):
            label = next(label for label in adjusted if label['case_id'] == 'NV05')
            label['fields']['intervention'], label['fields']['measured_outcome'] = (
                label['fields']['measured_outcome'], label['fields']['intervention'])
            matched = True
    result = score_records(inputs, adjusted, records, manifest)
    review = ROOT / 'NV05_ADJUDICATION_20261014.md'
    result['analysis_kind'] = 'known_regression_annotation_sensitivity_only'
    result['independent_human_adjudication'] = False
    result['adjusted_case_ids'] = ['NV05'] if matched else []
    result['adjudication_reference'] = review.name
    result['adjudication_sha256'] = hashlib.sha256(review.read_bytes()).hexdigest()
    result['scorer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['qualification_claim'] = 'Not unseen validation; inspect the unchanged strict score separately.'
    result['extraction_stage_seconds_max'] = stage_seconds
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage-seconds', type=int, choices=[10, 30], default=10)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Never overwrite an existing result.')
    result = score_with_recorded_adjudication(read_jsonl(args.predictions), stage_seconds=args.stage_seconds)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('engineering_gate_passed', 'adjusted_case_ids', 'qualification_claim')}))
