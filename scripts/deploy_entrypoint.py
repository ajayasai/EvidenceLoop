"""Start a disposable PostgreSQL database and the guided public demonstration.

No external database, provider key, reviewer credential, model download, or paid
resource is used. All runtime records disappear on process/container restart.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

import psycopg
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.migrate_db import migrate


def deployment_settings(environment):
    origin = environment.get("APP_ORIGIN") or environment.get("RENDER_EXTERNAL_URL", "")
    origin = origin.rstrip("/")
    try:
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment
                or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname)):
            raise ValueError
        parsed.port
        port = int(environment.get("PORT", "7860"))
        if not 1024 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ValueError("Set one exact HTTPS APP_ORIGIN and a PORT between 1024 and 65535.") from None
    return origin, port


def runtime_environment(environment, database_url, origin):
    # Platform settings cannot accidentally enable provider calls/reviewer roles.
    blocked = {"DATABASE_URL", "DATABASE_ADMIN_URL", "REVIEWER_TOKEN", "EDITOR_TOKEN", "APP_ORIGIN"}
    result = {key:value for key,value in environment.items()
              if key not in blocked and not key.startswith("EVIDENCELOOP_")}
    result.update({"DATABASE_URL":database_url, "APP_ORIGIN":origin,
        "EVIDENCELOOP_PUBLIC_DEMO":"true", "EVIDENCELOOP_LIVE_ENABLED":"false",
        "EVIDENCELOOP_ALIGNMENT_ENABLED":"false", "EVIDENCELOOP_MODEL_API_KEY":"",
        "EVIDENCELOOP_MODEL_MAX_REQUESTS":"0", "EVIDENCELOOP_REVIEW_ACCESS_FILE":"",
        "REVIEWER_TOKEN":"", "EDITOR_TOKEN":"", "PYTHONDONTWRITEBYTECODE":"1"})
    return result


def postgres_arguments(binary, data, port):
    return [str(binary), "-D", str(data), "-p", str(port),
        "-c", "listen_addresses=127.0.0.1", "-c", "unix_socket_directories=",
        "-c", "max_connections=20", "-c", "shared_buffers=16MB",
        "-c", "work_mem=1MB", "-c", "maintenance_work_mem=16MB", "-c", "temp_buffers=1MB",
        "-c", "max_worker_processes=0", "-c", "autovacuum_max_workers=1",
        "-c", "log_statement=none", "-c", "log_min_error_statement=panic"]


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run(postgres_bin=None, database_port=15432):
    origin, port = deployment_settings(os.environ)
    binaries = Path(postgres_bin) if postgres_bin else Path("/usr/lib/postgresql/15/bin")
    suffix = ".exe" if os.name == "nt" else ""
    # A fresh path on every launch also prevents accidental reuse of old receipts.
    runtime = Path(tempfile.mkdtemp(prefix="evidenceloop-demo-"))
    runtime.chmod(0o700)
    password_file = runtime / "bootstrap-password"
    admin_password = secrets.token_urlsafe(36)
    app_password = secrets.token_urlsafe(36)
    password_file.write_text(admin_password, encoding="utf-8")
    password_file.chmod(0o600)
    data = runtime / "postgres"
    database_process = api_process = None

    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, terminate)
    try:
        try:
            subprocess.run([str(binaries / ("initdb" + suffix)), "-D", str(data), "-U", "el_admin",
                "--auth-local=reject", "--auth-host=scram-sha-256", "--encoding=UTF8", "--locale=C",
                "--pwfile=" + str(password_file), "--no-instructions"],
                check=True, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            password_file.unlink(missing_ok=True)
        database_process = subprocess.Popen(postgres_arguments(binaries / ("postgres" + suffix), data, database_port),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        bootstrap = make_conninfo(host="127.0.0.1", port=database_port, dbname="postgres", user="el_admin", password=admin_password)
        deadline = time.monotonic() + 40
        while True:
            if database_process.poll() is not None:
                raise RuntimeError("Database process stopped.")
            try:
                with psycopg.connect(bootstrap, autocommit=True, connect_timeout=2) as connection:
                    connection.execute("CREATE DATABASE evidenceloop")
                break
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Database readiness timeout.") from None
                time.sleep(0.2)
        admin_url = make_conninfo(host="127.0.0.1", port=database_port, dbname="evidenceloop", user="el_admin", password=admin_password)
        app_url = make_conninfo(host="127.0.0.1", port=database_port, dbname="evidenceloop", user="el_app", password=app_password)
        with psycopg.connect(admin_url) as connection:
            connection.execute("REVOKE ALL ON DATABASE evidenceloop FROM PUBLIC")
            connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        migrate(admin_url, app_url, create_role=True)
        environment = runtime_environment(os.environ, app_url, origin)
        del admin_password, app_password, bootstrap, admin_url
        api_process = subprocess.Popen([sys.executable, "-m", "uvicorn", "services.api.app.main:app",
            "--host", "0.0.0.0", "--port", str(port), "--workers", "1", "--no-access-log",
            "--no-proxy-headers", "--limit-concurrency", "24", "--timeout-keep-alive", "5"],
            cwd=ROOT, env=environment)
        print("Guided fictional demo readying. Live AI and reviewer access are disabled; storage is temporary.", flush=True)
        while api_process.poll() is None and database_process.poll() is None:
            time.sleep(0.5)
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Subprocess/configuration errors may include credentials: never print them.
        print("Public demo startup failed. Check image dependencies, HTTPS origin, port and resource limits.", file=sys.stderr, flush=True)
        return 1
    finally:
        stop_process(api_process)
        stop_process(database_process)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except ValueError:
        print("Set a valid HTTPS APP_ORIGIN (or RENDER_EXTERNAL_URL) and PORT before startup.", file=sys.stderr)
        raise SystemExit(1)
