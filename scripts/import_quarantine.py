"""Import inspected source packets into quarantine. Never approve or publish evidence."""
from pathlib import Path
import argparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from services.api.app.review import EvidenceReviewStore, SourceImport
from services.api.app.storage import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT/'evidence/quarantine')
    args = parser.parse_args()
    load_dotenv(ROOT/'.env')
    reviews = EvidenceReviewStore(Store(os.environ['DATABASE_URL']))
    for file in sorted(args.directory.glob('*.json')):
        packet = SourceImport.model_validate(json.loads(file.read_text(encoding='utf-8')))
        result = reviews.import_source('local-evidence-editor',packet.model_dump(mode='json'))
        print(json.dumps({'file':file.name,'source_version_id':result['source_version_id'],'approval':'not_performed'}))


if __name__ == '__main__':
    main()
