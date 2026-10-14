"""Exercise the container supervisor with local PostgreSQL binaries; never deploy.

This checks startup and database-role migration, not Linux image compatibility or
the 512 MB host limit. It creates only fictional ephemeral data in a temp folder.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        return endpoint.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-bin", required=True, type=Path)
    args = parser.parse_args()
    api_port, database_port = free_port(), free_port()
    if api_port == database_port:
        raise RuntimeError("Retry smoke test: temporary ports collided.")
    # Keep this generated directory for diagnostics; no arbitrary path deletion.
    temporary = Path(tempfile.mkdtemp(prefix="evidenceloop-smoke-"))
    environment = dict(os.environ, PORT=str(api_port), APP_ORIGIN="https://demo.example.org",
        EVIDENCELOOP_PUBLIC_DEMO="true", TMP=str(temporary), TEMP=str(temporary), TMPDIR=str(temporary))
    command = [sys.executable, "-c", "from scripts.deploy_entrypoint import run; import sys; raise SystemExit(run(sys.argv[1], int(sys.argv[2])))",
        str(args.postgres_bin.resolve()), str(database_port)]
    options = {"creationflags":subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
    process = subprocess.Popen(command, cwd=ROOT, env=environment, **options)
    try:
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Supervisor stopped before readiness.")
            try:
                with urlopen(f"http://127.0.0.1:{api_port}/api/health", timeout=2) as response:
                    health = json.load(response)
                if health["status"] == "ok" and health["schema_version"] == 2:
                    break
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.3)
        else:
            raise RuntimeError("Supervisor did not become ready.")
        with urlopen(f"http://127.0.0.1:{api_port}/api/session", timeout=3) as response:
            cookies = response.headers.get_all("Set-Cookie")
            session = json.load(response)
        assert session["public_demo"] and session["synthetic"] and session["storage_resets_on_restart"]
        assert not session["live_available"] and not session["alignment_available"]
        assert len(cookies) == 2 and all("Secure" in cookie and "HttpOnly" in cookie for cookie in cookies)
        print("PASS: fresh database, separate non-owner application role, schema v2, public replay, Secure cookies, no live model.")
    finally:
        if process.poll() is None:
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
            try:
                process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        print("Local smoke test finished. No container was built and no service was published.")


if __name__ == "__main__":
    main()
