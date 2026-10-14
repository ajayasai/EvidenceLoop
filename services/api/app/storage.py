"""PostgreSQL persistence. User content is written only by the explicit save transaction."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_versions (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
INSERT INTO schema_versions(version) VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS owners (
 id uuid PRIMARY KEY, auth_hash text UNIQUE NOT NULL, expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS next_steps (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
 case_id uuid NOT NULL, receipt_id uuid NOT NULL, question text NOT NULL,
 state text NOT NULL CHECK(state IN ('planned','done_self_reported','deferred','abandoned','needs_revision')),
 version integer NOT NULL DEFAULT 1, receipt jsonb NOT NULL,
 consent_id uuid NOT NULL, consent_scope text NOT NULL, consent_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 check_ins jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS next_steps_owner ON next_steps(owner_id,created_at DESC);
CREATE TABLE IF NOT EXISTS idempotency (
 owner_id uuid NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
 key text NOT NULL, payload_hash text NOT NULL,
 step_id uuid NOT NULL REFERENCES next_steps(id) ON DELETE CASCADE,
 PRIMARY KEY(owner_id,key)
);
CREATE TABLE IF NOT EXISTS evidence_state (
 source_id text PRIMARY KEY, state text NOT NULL CHECK(state IN ('current','withdrawn','under_review')),
 revision integer NOT NULL DEFAULT 1, changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 event_kind text NOT NULL, entity_id text NOT NULL, revision integer, occurred_at timestamptz NOT NULL DEFAULT now()
);
"""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class StorageConflict(Exception):
    pass


class Store:
    def __init__(self, url: str):
        self.url = url

    def connect(self):
        return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=5)

    def ping(self):
        with self.connect() as con:
            return con.execute("SELECT version FROM schema_versions ORDER BY version DESC LIMIT 1").fetchone()["version"]

    def expire(self):
        with self.connect() as con:
            con.execute("DELETE FROM next_steps WHERE expires_at <= now()")
            con.execute("DELETE FROM owners WHERE expires_at <= now()")
            con.execute("DELETE FROM audit_events WHERE occurred_at < now() - interval '7 days'")

    def owner_for_token(self, token: str):
        with self.connect() as con:
            row = con.execute("SELECT id FROM owners WHERE auth_hash=%s AND expires_at>now()", (digest(token),)).fetchone()
            return str(row["id"]) if row else None

    def seed_states(self, source_ids):
        with self.connect() as con:
            for sid in source_ids:
                con.execute("INSERT INTO evidence_state(source_id,state) VALUES(%s,'current') ON CONFLICT DO NOTHING", (sid,))

    def trust(self, source_ids=None, con=None, lock=False):
        if con is None:
            with self.connect() as conn:
                return self.trust(source_ids, conn, lock)
        query = "SELECT source_id,state,revision FROM evidence_state"
        params = ()
        if source_ids is not None:
            query += " WHERE source_id=ANY(%s)"
            params = (list(source_ids),)
        query += " ORDER BY source_id"
        if lock:
            query += " FOR UPDATE"
        return {r["source_id"]: dict(r) for r in con.execute(query, params).fetchall()}

    def change_trust(self, source_id: str, revision: int, state: str):
        with self.connect() as con:
            row = con.execute("UPDATE evidence_state SET state=%s,revision=revision+1,changed_at=now() WHERE source_id=%s AND revision=%s RETURNING source_id,state,revision", (state, source_id, revision)).fetchone()
            if not row:
                raise StorageConflict("Evidence changed; reload the current version.")
            con.execute("INSERT INTO audit_events(event_kind,entity_id,revision) VALUES(%s,%s,%s)", ("synthetic_trust_" + state, source_id, row["revision"]))
            return row

    @staticmethod
    def as_step(row):
        if not row:
            return None
        return {k: (str(v) if isinstance(v, uuid.UUID) else v.isoformat() if isinstance(v, datetime) else v)
                for k, v in row.items() if k != "owner_id"}

    def save(self, owner_id, owner_token, key, payload_hash, receipt, question, dependencies, trust_revisions, publication_guard=None):
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        with self.connect() as con:
            if publication_guard:
                publication_guard(con)
            # Share the evidence row locks with reviewer changes before persisting anything.
            current = self.trust(dependencies, con, lock=True)
            if any(sid not in current or current[sid]["state"] != "current" or current[sid]["revision"] != trust_revisions.get(sid) for sid in dependencies):
                raise StorageConflict("Evidence changed. Reassess before saving.")
            con.execute("INSERT INTO owners(id,auth_hash,expires_at) VALUES(%s,%s,%s) ON CONFLICT(id) DO UPDATE SET expires_at=EXCLUDED.expires_at", (owner_id, digest(owner_token), expires))
            prior = con.execute("SELECT payload_hash,step_id FROM idempotency WHERE owner_id=%s AND key=%s", (owner_id, key)).fetchone()
            if prior:
                if prior["payload_hash"] != payload_hash:
                    raise StorageConflict("Idempotency key already used for a different request.")
                row = con.execute("SELECT * FROM next_steps WHERE id=%s AND owner_id=%s", (prior["step_id"], owner_id)).fetchone()
                return self.as_step(row)
            step_id, case_id, consent_id = (str(uuid.uuid4()) for _ in range(3))
            row = con.execute("""INSERT INTO next_steps(id,owner_id,case_id,receipt_id,question,state,receipt,consent_id,consent_scope,expires_at)
                VALUES(%s,%s,%s,%s,%s,'planned',%s,%s,'save_receipt_and_question',%s) RETURNING *""",
                (step_id, owner_id, case_id, receipt["receipt_id"], question, Jsonb(receipt), consent_id, expires)).fetchone()
            con.execute("INSERT INTO idempotency(owner_id,key,payload_hash,step_id) VALUES(%s,%s,%s,%s)", (owner_id,key,payload_hash,step_id))
            return self.as_step(row)

    def list_steps(self, owner_id):
        with self.connect() as con:
            rows = con.execute("SELECT * FROM next_steps WHERE owner_id=%s AND expires_at>now() ORDER BY created_at DESC LIMIT 100", (owner_id,)).fetchall()
            if rows:
                expires = datetime.now(timezone.utc) + timedelta(days=30)
                con.execute("UPDATE next_steps SET expires_at=%s WHERE owner_id=%s AND id=ANY(%s)", (expires,owner_id,[r["id"] for r in rows]))
                con.execute("UPDATE owners SET expires_at=%s WHERE id=%s", (expires,owner_id))
                for row in rows:
                    row["expires_at"] = expires
            return [self.as_step(r) for r in rows]

    def get_step(self, owner_id, step_id):
        with self.connect() as con:
            return self.as_step(con.execute("SELECT * FROM next_steps WHERE owner_id=%s AND id=%s AND expires_at>now()", (owner_id,step_id)).fetchone())

    def receipt(self, owner_id, receipt_id):
        with self.connect() as con:
            row = con.execute("SELECT receipt,consent_id,expires_at FROM next_steps WHERE owner_id=%s AND receipt_id=%s AND expires_at>now() LIMIT 1", (owner_id,receipt_id)).fetchone()
            if row:
                expires = datetime.now(timezone.utc) + timedelta(days=30)
                con.execute("UPDATE next_steps SET expires_at=%s WHERE owner_id=%s AND receipt_id=%s AND expires_at>now()", (expires,owner_id,receipt_id))
                con.execute("UPDATE owners SET expires_at=%s WHERE id=%s", (expires,owner_id))
                row["expires_at"] = expires
            return self.as_step(row)

    def check_in(self, owner_id, step_id, version, state, exercise_choice, dependencies, trust_revisions, publication_guard=None):
        with self.connect() as con:
            if publication_guard:
                publication_guard(con)
            current = self.trust(dependencies, con, lock=True)
            if any(sid not in current or current[sid]["state"] != "current" or current[sid]["revision"] != trust_revisions.get(sid) for sid in dependencies):
                raise StorageConflict("Evidence changed. Reassess before checking in.")
            event = {"id": str(uuid.uuid4()), "state": state, "at": datetime.now(timezone.utc).isoformat(), "exercise_choice": exercise_choice, "self_reported": True}
            row = con.execute("""UPDATE next_steps SET state=%s,version=version+1,check_ins=check_ins || %s::jsonb,expires_at=now()+interval '30 days'
                WHERE owner_id=%s AND id=%s AND version=%s AND expires_at>now() RETURNING *""", (state,Jsonb([event]),owner_id,step_id,version)).fetchone()
            if not row:
                raise StorageConflict("This step changed. Reload before checking in.")
            con.execute("UPDATE owners SET expires_at=now()+interval '30 days' WHERE id=%s", (owner_id,))
            return self.as_step(row)

    def delete_owner(self, owner_id):
        with self.connect() as con:
            con.execute("DELETE FROM owners WHERE id=%s", (owner_id,))
