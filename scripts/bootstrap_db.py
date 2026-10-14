"""Provision an isolated loopback PostgreSQL instance. No Windows service or paid resource."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
URL = "https://sbp.enterprisedb.com/getfile.jsp?fileid=1260569"


def run(args, **kwargs):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{Path(str(args[0])).name} failed: {result.stderr[-1800:]}")
    return result.stdout


def main():
    RUNTIME.mkdir(exist_ok=True)
    archive = RUNTIME / "postgresql-windows.zip"
    postgres = RUNTIME / "pgsql"
    if not (postgres / "bin" / "postgres.exe").exists():
        if not archive.exists():
            print("Downloading the official EDB PostgreSQL binary archive.", flush=True)
            urllib.request.urlretrieve(URL, archive)
        print("Extracting server binaries, libraries and shared data only.", flush=True)
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                name = member.filename.replace("\\", "/")
                if name.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                    target = (RUNTIME / name).resolve()
                    if not target.is_relative_to(RUNTIME.resolve()):
                        raise RuntimeError("Invalid archive member")
                    z.extract(member, RUNTIME)
        (RUNTIME / "postgres-download.json").write_text(json.dumps({
            "source": URL, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "note": "Downloaded hash records artifact identity; not an independently signed checksum."
        }, indent=2))
    credential_file = RUNTIME / "database-credentials.json"
    if credential_file.exists():
        creds = json.loads(credential_file.read_text())
    else:
        creds = {"admin": secrets.token_urlsafe(32), "app": secrets.token_urlsafe(32),
                 "reviewer": secrets.token_urlsafe(32)}
        credential_file.write_text(json.dumps(creds))
    data = RUNTIME / "pgdata"
    password_file = RUNTIME / "init-password"
    if not (data / "PG_VERSION").exists():
        password_file.write_text(creds["admin"])
        try:
            run([postgres / "bin/initdb.exe", "-D", data, "-U", "postgres", "--encoding=UTF8",
                 "--locale=C", "--auth=scram-sha-256", "--pwfile", password_file])
        finally:
            password_file.unlink(missing_ok=True)
        with (data / "postgresql.conf").open("a") as f:
            f.write("\nlisten_addresses = '127.0.0.1'\nport = 15432\nmax_connections = 30\nshared_buffers = '64MB'\n")
    config_path = data / "postgresql.conf"
    config_path.write_text(config_path.read_text().replace("port = 55432", "port = 15432"))
    status = subprocess.run([str(postgres / "bin/pg_ctl.exe"), "-D", str(data), "status"], capture_output=True)
    if status.returncode:
        # A long-lived Windows child can retain captured pipe handles after pg_ctl exits.
        # Redirect to a file, so waiting for pg_ctl never waits for the database lifetime.
        with (RUNTIME / "pg-start.log").open("a") as output:
            started = subprocess.run([str(postgres / "bin/pg_ctl.exe"), "-D", str(data), "-l", str(RUNTIME / "postgres.log"), "-w", "start"], stdout=output, stderr=output, timeout=40)
        if started.returncode:
            raise RuntimeError("PostgreSQL startup failed; inspect .runtime/postgres.log.")
    import psycopg
    from psycopg import sql
    from services.api.app.storage import SCHEMA_SQL
    from services.api.app.review import REVIEW_SCHEMA_SQL
    admin_url = f"postgresql://postgres:{creds['admin']}@127.0.0.1:15432/postgres"
    with psycopg.connect(admin_url, autocommit=True) as con:
        if not con.execute("SELECT 1 FROM pg_roles WHERE rolname='evidenceloop_app'").fetchone():
            con.execute(sql.SQL("CREATE ROLE evidenceloop_app LOGIN PASSWORD {}").format(sql.Literal(creds["app"])))
        if not con.execute("SELECT 1 FROM pg_database WHERE datname='evidenceloop'").fetchone():
            con.execute("CREATE DATABASE evidenceloop")
    with psycopg.connect(admin_url.rsplit("/", 1)[0] + "/evidenceloop", autocommit=True) as con:
        con.execute(SCHEMA_SQL)
        con.execute(REVIEW_SCHEMA_SQL)
        con.execute("INSERT INTO schema_versions(version) VALUES(2) ON CONFLICT DO NOTHING")
        con.execute("GRANT CONNECT ON DATABASE evidenceloop TO evidenceloop_app")
        con.execute("GRANT USAGE ON SCHEMA public TO evidenceloop_app")
        con.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO evidenceloop_app")
        con.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO evidenceloop_app")
    env_file = ROOT / ".env"
    if not env_file.exists():
        env_file.write_text(
            f"DATABASE_URL=postgresql://evidenceloop_app:{creds['app']}@127.0.0.1:15432/evidenceloop\n"
            f"REVIEWER_TOKEN={creds['reviewer']}\nEVIDENCELOOP_MODE=replay\n"
        )
    if "editor" not in creds:
        creds["editor"] = secrets.token_urlsafe(32)
        credential_file.write_text(json.dumps(creds))
    if "EDITOR_TOKEN=" not in env_file.read_text():
        with env_file.open("a") as f:
            f.write(f"EDITOR_TOKEN={creds['editor']}\n")
    print("PostgreSQL ready on loopback port 15432; private configuration stored locally.")
    print(run([postgres / "bin/postgres.exe", "--version"]).strip())


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
