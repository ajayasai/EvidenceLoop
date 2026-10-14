"""Build a deterministic, credential-checked local source archive. Never uploads."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from uuid import uuid4
import zipfile

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/submission-20261014/source"
MAX_FILE_BYTES = 5_000_000
PUBLIC_MEDIA_FILES = (
    "apps/web/public/demo-video.html", "apps/web/public/demo/cover.png",
    "apps/web/public/demo/EvidenceLoop-recorded-walkthrough.vtt",
    "apps/web/public/demo/EvidenceLoop-recorded-walkthrough.mp4",
)
REVIEWED_VIDEO = "apps/web/public/demo/EvidenceLoop-recorded-walkthrough.mp4"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
ROOT_FILES = (
    "README.md", "AGENTS.md", ".gitignore", ".env.example", "pyproject.toml", "requirements.lock.txt",
    "Dockerfile", ".dockerignore", "render.yaml",
    "apps/web/index.html", "apps/web/package.json", "apps/web/package-lock.json",
    "apps/web/tsconfig.json", "apps/web/vite.config.ts", "apps/web/vitest.config.ts",
    "evidence/synthetic_nonclinical.json",
)
SOURCE_TREES = {
    "services": {".py"}, "tests": {".py"}, "scripts": {".py", ".ps1", ".txt"},
    "apps/web/src": {".ts", ".tsx", ".css"}, "apps/web/public": {".svg"},
    "contracts": {".json", ".ts"}, ".github/workflows": {".yml", ".yaml"},
    "docs": {".md"}, "docs/submission": {".csv"},
    "evidence/quarantine": {".json", ".md"}, "evals/harness": {".py"},
    "evals/extraction": {".py", ".md", ".json", ".jsonl"},
    "evals/extraction-next-20261013": {".py", ".md", ".json", ".jsonl"},
}
SPONSOR_FILES = tuple("docs/sponsor-evidence/2026-10-13/" + name for name in (
    "01-source-withdrawal-request.png", "02-source-withdrawal-review.png",
    "03-transaction-test-proposal.png", "04-local-validation-review.png",
    "manifest.json", "validation.txt",
))
FROZEN_METADATA = tuple("evals/" + partition + "/" + name for partition in (
    "extraction-final-20261013", "extraction-challenge-20261013",
) for name in ("manifest.json", "offline_integrity.json"))
RESULT_ROOTS = ("evals/development", "evals/regression", "evals/validation", "evals/harness/runs")
RESULT_NAMES = {"summary.json", "score.json", "score-30s.json", "adjudicated-score.json",
                "adjudicated-score-30s.json", "manifest.json"}
FORBIDDEN_PARTS = {".git", ".runtime", ".tools", ".venv", "node_modules", "dist", "__pycache__",
                   ".pytest_cache", ".ruff_cache", "private", "test-results", "playwright-report"}
PRIVATE_NAMES = {"private-review-key.jsonl", "credentials.json", "database-credentials.json"}


class BundleError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def is_link(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def safe_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.resolve().is_relative_to(root.resolve()) is False:
        raise BundleError(f"Source path leaves project: {relative}")
    cursor = path
    while cursor != root:
        if is_link(cursor):
            raise BundleError(f"Linked source path is not allowed: {relative}")
        cursor = cursor.parent
    if not path.is_file():
        raise BundleError(f"Required source file missing: {relative}")
    parts = {part.casefold() for part in Path(relative).parts}
    if parts & FORBIDDEN_PARTS or path.name.casefold() in PRIVATE_NAMES:
        raise BundleError(f"Private path selected: {relative}")
    if path.name.casefold().startswith(".env") and relative != ".env.example":
        raise BundleError(f"Private configuration selected: {relative}")
    return path


def walk_files(root: Path, folder: str):
    start = root / folder
    if not start.exists():
        return
    if is_link(start):
        raise BundleError(f"Linked source tree is not allowed: {folder}")
    for current, directories, filenames in os.walk(start, followlinks=False):
        current_path = Path(current)
        kept = []
        for name in directories:
            child = current_path / name
            if name.casefold() in FORBIDDEN_PARTS:
                continue
            if is_link(child):
                raise BundleError(f"Linked source tree is not allowed: {child.relative_to(root).as_posix()}")
            kept.append(name)
        directories[:] = sorted(kept)
        for name in sorted(filenames):
            yield (current_path / name).relative_to(root).as_posix()


def selected_files(root: Path) -> list[str]:
    names = set(ROOT_FILES)
    for folder, extensions in SOURCE_TREES.items():
        names.update(name for name in walk_files(root, folder) if Path(name).suffix in extensions)
    names.update(name for name in SPONSOR_FILES + FROZEN_METADATA if (root / name).is_file())
    names.update(name for name in PUBLIC_MEDIA_FILES if (root / name).is_file())
    for folder in RESULT_ROOTS:
        names.update(name for name in walk_files(root, folder) if Path(name).name in RESULT_NAMES)
    for name in names:
        safe_file(root, name)
    return sorted(names)


def known_credentials(root: Path) -> list[bytes]:
    values: set[str] = set()
    for path in sorted(root.glob(".env*")):
        if not path.is_file() or path.name == ".env.example":
            continue
        for name, value in dotenv_values(path, encoding="utf-8-sig", interpolate=False).items():
            sensitive = any(marker in name.upper() for marker in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")) or name.upper().endswith("DATABASE_URL") or name.upper()=="DATABASE_ADMIN_URL"
            if sensitive and value:
                values.add(value)
    credentials = root / ".runtime/database-credentials.json"
    if credentials.is_file():
        document = json.loads(credentials.read_text(encoding="utf-8-sig"))
        values.update(value for value in document.values() if isinstance(value, str) and len(value) >= 12)
    # Match common text encodings without ever printing a value or its hash.
    return sorted({value.encode(encoding) for value in values for encoding in ("utf-8", "utf-16-le", "utf-16-be")})


def write_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp-" + uuid4().hex)
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build(root: Path = ROOT, output: Path = DEFAULT_OUTPUT) -> dict:
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root) or output == root:
        raise BundleError("Output must be a child directory within the project.")
    names = selected_files(root)
    secrets = known_credentials(root)
    payloads, records = {}, []
    for name in names:
        path = safe_file(root, name)
        maximum_bytes = 10_000_000 if name == REVIEWED_VIDEO else MAX_FILE_BYTES
        if path.stat().st_size > maximum_bytes:
            raise BundleError(f"Source file exceeds review limit: {name}")
        data = path.read_bytes()
        if any(secret in data for secret in secrets):
            raise BundleError(f"Known local credential found in selected file: {name}")
        payloads[name] = data
        records.append({"path":name,"bytes":len(data),"sha256":digest(data)})
    manifest = {
        "format":"EvidenceLoopSourceBundle/1.0", "package_date":"2026-10-14",
        "scope":"Local source archive prepared for user review; no upload, publication or submission performed.",
        "file_count":len(records), "source_bytes":sum(row["bytes"] for row in records),
        "source_tree_sha256":digest(json_bytes(records)), "files":records,
        "archive_manifest":"EvidenceLoop/BUNDLE_MANIFEST.json is metadata and is excluded from its own file list.",
        "evaluation_scope":"Included original/development and next partitions are developer-authored fictional regression material. Final/challenge inputs and gold labels, raw prediction logs and private review keys are excluded. Metadata and summary scores do not constitute clinical validation.",
        "excluded":"Private .env and runtime files, dependencies, caches, models, downloaded PDFs, generated deck/other media binaries, sealed inputs/labels and raw evaluation predictions. The explicitly selected public demo video, cover and captions are included.",
        "audit_scope":"Known local credentials and explicit paths only; not a universal secret or personal-information detector. Sponsor screenshots are the four previously reviewed captures.",
        "reproducibility":"Sorted paths, fixed ZIP timestamps and permissions; unchanged selected bytes produce the same ZIP with the same Python/zlib implementation.",
    }
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "EvidenceLoop-source.zip"
    temporary = archive.with_name(archive.name + ".tmp-" + uuid4().hex)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            entries = {"EvidenceLoop/"+name:data for name,data in payloads.items()}
            entries["EvidenceLoop/BUNDLE_MANIFEST.json"] = json_bytes(manifest)
            for name, data in sorted(entries.items()):
                info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(temporary) as bundle:
            if bundle.testzip() is not None:
                raise BundleError("Archive CRC verification failed.")
            for row in records:
                if digest(bundle.read("EvidenceLoop/"+row["path"])) != row["sha256"]:
                    raise BundleError("Archive checksum verification failed.")
        for row in records:
            if digest(safe_file(root, row["path"]).read_bytes()) != row["sha256"]:
                raise BundleError(f"Source changed during packaging; rebuild after edits finish: {row['path']}")
        if names != selected_files(root):
            raise BundleError("Source selection changed during packaging; rebuild after edits finish.")
        archive_bytes = temporary.read_bytes()
        receipt = {**manifest, "archive_file":archive.name, "archive_bytes":len(archive_bytes),
                   "archive_sha256":digest(archive_bytes), "verified_utc":datetime.now(timezone.utc).isoformat(),
                   "verification":{"crc":"passed","entry_hashes":"passed","source_unchanged":"passed","known_credentials":"not_found"}}
        os.replace(temporary, archive)
        write_atomic(output / "EvidenceLoop-source.manifest.json", json_bytes(receipt))
        write_atomic(output / "SHA256SUMS.txt", f"{receipt['archive_sha256']}  {archive.name}\n".encode("ascii"))
        return {key:receipt[key] for key in ("archive_file","archive_bytes","archive_sha256","file_count","source_bytes","source_tree_sha256","verification")}
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        print(json.dumps(build(output=args.output_dir),indent=2))
    except (BundleError, OSError, ValueError) as error:
        # Errors name files or checks, never credential values or source bytes.
        print(json.dumps({"status":"failed","error":str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
