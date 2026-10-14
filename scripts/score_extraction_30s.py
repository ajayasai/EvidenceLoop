"""Explicit prospective latency analysis; preserve the original strict score."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals.extraction.score import load_corpus, read_jsonl, score_records


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus-root', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Do not overwrite existing results.')
    allowed = {'extraction-next-20261013', 'extraction-final-20261013', 'extraction-challenge-20261013'}
    if args.corpus_root.resolve() not in {ROOT / 'evals' / name for name in allowed}:
        parser.error('This protocol is limited to its three recorded fictional partitions.')
    inputs, labels, original_manifest = load_corpus('validation', args.corpus_root)
    manifest = deepcopy(original_manifest)
    manifest['engineering_gate']['extraction_stage_seconds_max'] = 30.0
    result = score_records(inputs, labels, read_jsonl(args.predictions), manifest)
    protocol = ROOT / 'docs/EXTRACTION_30S_PROTOCOL_20261014.md'
    result['analysis_kind'] = 'prospectively_recorded_30_second_latency_protocol'
    result['original_extraction_stage_seconds_max'] = original_manifest['engineering_gate']['extraction_stage_seconds_max']
    result['extraction_stage_seconds_max'] = 30.0
    result['semantic_thresholds_unchanged'] = True
    result['protocol_sha256'] = hashlib.sha256(protocol.read_bytes()).hexdigest()
    result['original_manifest_sha256'] = hashlib.sha256((args.corpus_root / 'manifest.json').read_bytes()).hexdigest()
    result['scorer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('benchmark_id', 'engineering_gate_passed', 'analysis_kind')}))
