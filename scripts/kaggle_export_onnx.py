"""Private bounded Kaggle CPU conversion of a pinned Apache-2.0 Qwen model.

No user data, credentials, service, tunnel, remote Python or training. Output is
model data for the independently installed Microsoft ONNX Runtime on Windows.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                "onnxruntime-genai==0.17.1", "onnx", "onnx_ir", "onnxscript",
                "transformers==5.17.0"], check=True, timeout=180)
from huggingface_hub import snapshot_download

repo = "Qwen/Qwen2.5-1.5B-Instruct"
revision = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
source = snapshot_download(repo, revision=revision, token=False, local_dir="/tmp/qwen-source",
    allow_patterns=["*.safetensors", "*.json", "*.txt", "LICENSE"])
output = Path("/kaggle/working/qwen-1.5b-onnx")
command = [sys.executable, "-m", "onnxruntime_genai.models.builder", "-i", source,
           "-o", str(output), "-p", "int4", "-e", "cpu", "--extra_options", "hf_token=false", "hf_remote=false"]
before = time.monotonic()
subprocess.run(command, check=True, timeout=600)
if (Path(source) / "LICENSE").exists():
    shutil.copyfile(Path(source) / "LICENSE", output / "LICENSE")
files = []
for path in sorted(output.rglob("*")):
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        files.append({"path": str(path.relative_to(output)), "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
manifest = {"source": repo, "source_revision": revision, "source_license": "Apache-2.0",
            "builder": "onnxruntime-genai==0.17.1", "precision": "int4", "provider": "cpu",
            "remote_code": False, "conversion_seconds": time.monotonic() - before,
            "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files}
(output / "conversion-manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps({"status": "export_complete", "files": len(files), "bytes": sum(f["bytes"] for f in files)}))
