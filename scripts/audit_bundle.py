"""Check the proposed source bundle for ignored runtimes and known local secrets."""
from pathlib import Path
import json
import subprocess

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    files = sorted({name for name in names if name})
    # Audit both files independently: an empty value in one must not hide a
    # configured credential in the other.
    environments = [dotenv_values(ROOT/'.env'), dotenv_values(ROOT/'.env.ai',encoding='utf-8-sig')]
    secrets = [value for env in environments for key,value in env.items()
               if value and (key.endswith('_TOKEN') or key.endswith('_API_KEY') or key=='DATABASE_URL')]
    credentials = ROOT/'.runtime/database-credentials.json'
    if credentials.exists():
        secrets.extend(value for value in json.loads(credentials.read_text()).values() if isinstance(value,str) and len(value)>=24)
    problems = []
    total = 0
    for name in files:
        file = ROOT/name
        if not file.is_file():
            continue
        parts = Path(name).parts
        if name in {'.env','.env.ai'} or any(p in {'.runtime','.tools','.venv','node_modules','__pycache__'} for p in parts):
            problems.append((name,'private runtime/configuration included'))
        data = file.read_bytes()
        total += len(data)
        if len(data)>5_000_000:
            problems.append((name,'large artifact needs explicit review'))
        if any(value.encode() in data for value in secrets):
            problems.append((name,'known local credential found'))
    print(json.dumps({'files_checked':len(files),'total_bytes':total,'problems':problems,
                      'scope':'Known project credentials and bundle paths only; not a universal secret detector.'},indent=2))
    return bool(problems)


if __name__ == '__main__':
    raise SystemExit(main())
