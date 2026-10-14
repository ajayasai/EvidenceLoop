"""Local EvidenceLoop API: ephemeral drafting, explicit consent, immutable receipts."""
from __future__ import annotations

from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit
import asyncio
from contextlib import suppress
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid

from dotenv import load_dotenv, dotenv_values
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import domain
from .storage import Store, StorageConflict, digest
from .review import EvidenceReviewStore, SourceImport, BriefDraft
from .compiler import ClaimCompiler
from .contracts import ConfirmedClaimSnapshot
from .provider import AttemptBudget

ROOT = Path(__file__).resolve().parents[3]
if os.environ.get("EVIDENCELOOP_PUBLIC_DEMO", "").lower() != "true":
    load_dotenv(ROOT / ".env")
# A separately ignored credential file can be edited without exposing database
# credentials. An explicit process key remains authoritative, including in tests.
if os.environ.get("EVIDENCELOOP_PUBLIC_DEMO", "").lower() != "true" and not os.getenv("EVIDENCELOOP_MODEL_API_KEY"):
    private_key = dotenv_values(ROOT / ".env.ai", encoding="utf-8-sig").get("EVIDENCELOOP_MODEL_API_KEY")
    if private_key:
        os.environ["EVIDENCELOOP_MODEL_API_KEY"] = private_key
    del private_key


def now():
    return datetime.now(timezone.utc).isoformat()


def ident():
    return str(uuid.uuid4())


def canonical_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InputIntent(Strict):
    action_kind: Literal["learn", "discuss", "start", "add", "replace", "stop", "delay", "change_dose", "prevent", "seek_cure", "other"] | None = None
    current_care_relationship: Literal["alongside", "instead_of", "unrelated"] | None = None
    endorsement: Literal["supports", "rejects", "uncertain", "not_stated"] | None = None
    actor: Literal["self", "another_person", "hypothetical"] | None = None
    target: str | None = Field(default=None, max_length=200)
    timing: str | None = Field(default=None, max_length=100)


class Capture(Strict):
    text: str = Field(min_length=1, max_length=6000)
    intent: InputIntent = Field(default_factory=InputIntent)
    mode: Literal["replay", "live", "manual"] = "replay"
    allow_remote_processing: bool = False


class Confirmation(Strict):
    expected_revision: int = Field(ge=1)
    selected_proposition_id: str | None = Field(default=None, max_length=100)
    edits: dict = Field(default_factory=dict, max_length=24)
    intent: InputIntent | None = None


class AssessmentRequest(Strict):
    draft_id: str = Field(max_length=100)
    expected_revision: int = Field(ge=1)


class PreviewRequest(Strict):
    receipt_id: str = Field(max_length=100)


class SaveRequest(Strict):
    preview_id: str = Field(max_length=100)
    preview_hash: str = Field(min_length=64, max_length=64)
    consent: bool


class CheckInRequest(Strict):
    expected_version: int = Field(ge=1)
    state: Literal["done_self_reported", "deferred", "abandoned", "needs_revision"]
    consent: bool
    exercise_choice: Literal["same", "different", "unknown"] | None = None
    request_reassessment: bool = False
    new_concern_text: str | None = Field(default=None, max_length=6000)


class ReviewerLogin(Strict):
    token: str = Field(min_length=1, max_length=200)


class ReviewDecision(Strict):
    expected_revision: int = Field(ge=1)
    decision: Literal["withdraw", "restore"]
    reason: str = Field(min_length=3, max_length=500)


class SourceWithdrawal(Strict):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=500)


class ClinicalLogin(ReviewerLogin):
    identity: str = Field(min_length=3, max_length=160)


class BriefDecision(Strict):
    decision: Literal["approved", "changes_requested", "rejected"]
    rationale: str = Field(min_length=10, max_length=2000)
    expected_hash: str = Field(min_length=64,max_length=64)


class PublishRequest(Strict):
    brief_version_ids: list[str] = Field(min_length=1,max_length=6)
    expected_revision: int = Field(ge=0)


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data = message.get("body", b"")
            size += len(data)
            if size > 32768:
                return await JSONResponse({"error": {"code": "input_too_large", "message": "Request exceeds 32 KiB."}}, status_code=413)(scope, receive, send)
            chunks.append(data)
            if not message.get("more_body"):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, bounded_receive, send)


def create_app(database_url=None, review_config=None, compiler=None):
    public_demo = os.environ.get("EVIDENCELOOP_PUBLIC_DEMO", "").lower() == "true"
    additional_origin = os.environ.get("APP_ORIGIN", "").rstrip("/")
    allowed_hosts = ["127.0.0.1", "localhost", "testserver"]
    if additional_origin:
        parsed_origin = urlsplit(additional_origin)
        if (parsed_origin.scheme not in {"http", "https"} or not parsed_origin.hostname
                or parsed_origin.username or parsed_origin.password or parsed_origin.path
                or parsed_origin.query or parsed_origin.fragment
                or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed_origin.hostname)):
            raise ValueError("APP_ORIGIN must be one exact HTTP(S) origin without a path or credentials.")
        # Accessing port validates malformed/out-of-range port syntax.
        parsed_origin.port
        allowed_hosts.append(parsed_origin.hostname)
    if public_demo and (not additional_origin or parsed_origin.scheme != "https"):
        raise ValueError("The public demonstration requires an exact HTTPS APP_ORIGIN.")
    sessions = {}
    guard = RLock()
    store = Store(database_url or os.environ.get("DATABASE_URL", ""))
    pack = domain.load_pack()
    sources = {s["source_id"]: s for s in pack["sources"]}
    review_config = review_config or {}
    access_file = os.environ.get("EVIDENCELOOP_REVIEW_ACCESS_FILE")
    if public_demo:
        review_config = {}
    elif access_file and not review_config:
        review_config = json.loads(Path(access_file).read_text(encoding="utf-8"))
    qualified = review_config.get("qualified_reviewers", {})
    reviews = EvidenceReviewStore(store,qualified_reviewers=qualified,clinical_enabled=review_config.get("clinical_enabled") is True)
    compiler = compiler or ClaimCompiler()
    allowed_origins = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765", "http://localhost:8765"}
    if public_demo:
        allowed_origins = {additional_origin}
    elif additional_origin:
        allowed_origins.add(additional_origin)

    def cleanup():
        t = monotonic()
        for sid in list(sessions):
            session = sessions[sid]
            if t-session["touched"] > 1800 or t-session["created"] > 7200:
                del sessions[sid]

    @asynccontextmanager
    async def lifespan(app):
        store.ping()
        store.expire()
        store.seed_states(sources)
        async def housekeeping():
            while True:
                await asyncio.sleep(60)
                with guard:
                    cleanup()
                try:
                    await asyncio.to_thread(store.expire)
                except Exception:
                    # The next scheduled attempt retries; never log raw records or credentials.
                    app.state.retention_cleanup_available = False
                else:
                    app.state.retention_cleanup_available = True
        app.state.retention_cleanup_available = True
        maintenance = asyncio.create_task(housekeeping())
        try:
            yield
        finally:
            maintenance.cancel()
            with suppress(asyncio.CancelledError):
                await maintenance
            sessions.clear()

    app = FastAPI(title="EvidenceLoop", version="0.1.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.store = store
    app.state.sessions = sessions
    app.state.pack = pack
    app.state.reviews = reviews
    app.state.compiler = compiler
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(BodyLimitMiddleware)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default error echoes invalid input; retain field paths only.
        return JSONResponse({"error": {"code": "invalid_request", "message": "Some fields are invalid.",
            "fields": [list(e["loc"]) for e in exc.errors()]}}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_rejected", "message": str(exc.detail)}
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(domain.DomainError)
    async def domain_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status_code)

    @app.exception_handler(StorageConflict)
    async def storage_conflict(request, exc):
        return JSONResponse({"error": {"code": "version_conflict", "message": str(exc)}}, status_code=409)

    @app.middleware("http")
    async def boundaries(request, call_next):
        if public_demo and (request.url.path == "/api/review" or request.url.path.startswith("/api/review/")):
            return JSONResponse({"error": {"code": "review_disabled", "message": "Reviewer controls are unavailable in the public demonstration."}}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin is not None and origin.rstrip("/") not in allowed_origins:
                return JSONResponse({"error": {"code": "origin_rejected", "message": "Use the application from its configured address."}}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"error": {"code": "origin_rejected", "message": "Cross-site request rejected."}}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    def session_for(request, write=False, reviewer=False):
        with guard:
            cleanup()
            sid = request.cookies.get("el_session")
            session = sessions.get(sid)
            if not session:
                raise HTTPException(401, {"code": "session_expired", "message": "Your draft session expired. Reopen the app; saved steps remain available in this browser."})
            if write and not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
                raise HTTPException(403, "Refresh your session before making changes.")
            if reviewer and not session["reviewer"]:
                raise HTTPException(403, "Reviewer access is required.")
            session["touched"] = monotonic()
            if write:
                q = session["requests"]
                while q and monotonic()-q[0] > 60:
                    q.popleft()
                if len(q) >= 30:
                    raise HTTPException(429, "Too many requests. Please wait a minute.")
                q.append(monotonic())
            return session

    def draft_for(session, draft_id):
        draft = session["drafts"].get(draft_id)
        if not draft:
            raise HTTPException(404, "Draft not found in this session.")
        return draft

    def draft_view(draft):
        view = {k: v for k, v in draft.items() if k not in {"ledger", "receipt_id", "busy", "confirmed_edits", "confirmed_frames", "semantic_fingerprint"}}
        view["claim"] = copy.deepcopy(draft["claim"])
        view["claim"]["propositions"] = [copy.deepcopy(draft.get("confirmed_frames",{}).get(p["proposition_id"],p))
                                         for p in draft["claim"]["propositions"]]
        return view

    def semantic_fingerprint(result):
        def fields(value):
            return {k: {"state": v["state"], "value": v.get("value")} if isinstance(v,dict) and "state" in v else v
                    for k,v in value.items() if isinstance(v,dict) and "state" in v or k in {"speaker","speech_act","proposition_id"}}
        snapshot = result["snapshot"]
        return canonical_hash({"proposition":fields(snapshot["confirmed_proposition"]),
                               "intent":fields(result["intent"]),"safety_flags":snapshot["safety_flags"]})

    def publication_guard(receipt):
        if not receipt.get("clinical_review") or receipt.get("synthetic"):
            return None
        publication = receipt.get("publication_id") or receipt.get("reproduction",{}).get("publication_id")
        return lambda con: reviews.require_current_publication(con, publication)

    def current_claim(session, receipt):
        snapshot = receipt["snapshot"]
        related = [d for d in session["drafts"].values() if d.get("snapshot",{}).get("claim_id") == snapshot["claim_id"]]
        if any(not d["confirmed"] for d in related):
            return {"state":"needs_confirmation"}
        return {"state":"superseded" if any(d["snapshot"]["version_id"] != snapshot["version_id"] for d in related) else "current"}

    def require_current_claim(session,receipt):
        if current_claim(session,receipt)["state"] != "current":
            raise HTTPException(409, "Your interpretation changed or needs confirmation. Confirm and assess the current meaning before saving or checking in.")

    def current_comparison(receipt):
        # Persisted verdict/eligibility flags are historical, not authority to
        # bypass a newer comparison boundary after process/session restart.
        try:
            snapshot = ConfirmedClaimSnapshot.model_validate(receipt.get("snapshot")).model_dump(mode="json")
            qualified = domain.has_authored_comparison(snapshot)
        except ValidationError:
            qualified = False
        return {"state":"current" if qualified else "unqualified",
                "reason_codes":[] if qualified else ["exact_claim_comparison_unqualified"],
                "message":"The authored comparison remains eligible under the current checks." if qualified else
                    "This receipt's claim comparison is not qualified under the current checks. Start a new assessment before saving or recording a check-in."}

    def require_current_comparison(receipt):
        comparison = current_comparison(receipt)
        if comparison["state"] != "current":
            raise HTTPException(409, comparison["message"])

    def current_trust(receipt):
        deps = receipt.get("source_ids", [])
        states = store.trust(deps)
        affected = [sid for sid in deps if sid not in states or states[sid]["state"] != "current" or states[sid]["revision"] != receipt.get("trust_revisions", {}).get(sid)]
        state = "current" if not affected else "withdrawn" if any(states.get(sid, {}).get("state") == "withdrawn" for sid in affected) else "under_review"
        if receipt.get("clinical_review") and not receipt.get("synthetic"):
            try:
                active = reviews.load_current_pack()
                publication = receipt.get("publication_id") or receipt.get("reproduction", {}).get("publication_id")
                if not active or active.get("publication_id") != publication:
                    state = "under_review"
                    affected.append(publication or "clinical_publication")
            except domain.DomainError:
                state = "under_review"
                affected.append("clinical_review_record")
        if receipt.get("system_status") == "evidence_integrity_error":
            state = "integrity_error"
        elif receipt.get("system_status") == "evidence_under_review":
            state = "under_review"
        return {"state": state, "checked_at": now(), "affected_dependency_ids": affected}

    def envelope(session, receipt_id):
        receipt = session["receipts"].get(receipt_id)
        persisted = store.receipt(session["owner_id"], receipt_id)
        if persisted:
            receipt = persisted["receipt"]
        if not receipt:
            raise HTTPException(404, "Receipt not found.")
        return {"receipt_id": receipt_id, "receipt": receipt, "persistence": "saved" if persisted else "ephemeral", "current_trust": current_trust(receipt),
                "current_claim":current_claim(session,receipt),"current_comparison":current_comparison(receipt),
                "consent_id": persisted["consent_id"] if persisted else None, "retention_expires_at": persisted["expires_at"] if persisted else None}

    def step_view(step,session=None):
        result = dict(step)
        result["current_trust"] = current_trust(step["receipt"])
        result["current_comparison"] = current_comparison(step["receipt"])
        if session is not None:
            result["current_claim"] = current_claim(session,step["receipt"])
        return result

    def library_status():
        if public_demo:
            return {"synthetic":True,"clinical_review":"not_performed","publication_id":None,"library_status":"current"}
        try:
            current = reviews.load_current_pack()
            return {"synthetic":current is None, "clinical_review":"verified_publication" if current else "not_performed",
                    "publication_id":current.get("publication_id") if current else None,"library_status":"current"}
        except domain.DomainError:
            return {"synthetic":True,"clinical_review":"unavailable","publication_id":None,"library_status":"under_review"}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "database": "postgresql", "schema_version": store.ping(), "mode": "replay", "additional_spend": 0,
                "retention_cleanup_available":getattr(app.state,"retention_cleanup_available",False)}

    @app.get("/api/session")
    def get_session(request: Request, response: Response):
        with guard:
            cleanup()
            sid = request.cookies.get("el_session")
            session = sessions.get(sid)
            if not session:
                if len(sessions) >= (32 if public_demo else 128):
                    raise HTTPException(503, "Demo capacity reached. Try again later.")
                owner_token = request.cookies.get("el_owner") or secrets.token_urlsafe(32)
                owner = store.owner_for_token(owner_token) or ident()
                sid = secrets.token_urlsafe(32)
                session = {"csrf": secrets.token_urlsafe(32), "owner_id": owner, "owner_token": owner_token,
                           "created": monotonic(), "touched": monotonic(), "reviewer": False, "editor": False, "clinical_identity": None,
                           "drafts": {}, "receipts": {}, "previews": {}, "requests": deque(), "login_attempts": 0}
                sessions[sid] = session
            secure = public_demo or request.url.scheme == "https"
            response.set_cookie("el_session", sid, httponly=True, secure=secure, samesite="strict", max_age=7200)
            response.set_cookie("el_owner", session["owner_token"], httponly=True, secure=secure, samesite="strict", max_age=30*86400)
            return {"csrf_token": session["csrf"], "mode": "replay", "reviewer": session["reviewer"], "live_available": compiler.available and not public_demo,
                    "extraction_available":compiler.available and not public_demo,"alignment_available":compiler.alignment_available and not public_demo,
                    "preferred_mode":"live" if compiler.available and not public_demo else "replay","extraction_scope":None if public_demo else compiler.extraction_scope,
                    "public_demo":public_demo,"storage_resets_on_restart":public_demo,
                    "retention_days": 30, **library_status(), "editor": session["editor"], "clinical_reviewer": session["clinical_identity"] is not None}

    @app.get("/api/examples")
    def examples():
        return domain.fixture_catalog()

    @app.post("/api/claims")
    async def capture(body: Capture, request: Request):
        session = session_for(request, write=True)
        if public_demo and (body.mode != "replay" or body.text not in {item["text"] for item in domain.fixture_catalog()}):
            raise HTTPException(422, "This guided public demo accepts only the included fictional examples in replay mode.")
        if len(body.text.encode("utf-8")) > 24576:
            raise HTTPException(413, "Text exceeds the UTF-8 input budget.")
        if len(session["drafts"]) >= 10:
            raise HTTPException(429, "This session has ten drafts. Start a fresh session to continue.")
        ledger = AttemptBudget()
        with ledger.meter():
            if body.mode == "live":
                if not compiler.available:
                    raise HTTPException(503, {"code": "live_unavailable", "message": "A verified free runtime has not been enabled. Choose a labeled example or use manual confirmation."})
                if compiler.extraction_scope == "remote" and not body.allow_remote_processing:
                    raise HTTPException(422, {"code":"remote_processing_not_confirmed", "message":"Review the remote AI disclosure before sending this fictional or public claim."})
                result = await compiler.extract(body.text,body.intent.model_dump(exclude_none=True),ledger)
            else:
                result = domain.interpret(body.text, body.intent.model_dump(exclude_none=True), mode=body.mode)
        draft = {**result, "draft_id": ident(), "revision": 1, "confirmed": False, "ledger": ledger, "busy": False,
                 "attempt_id":ident(), "parent_attempt_id":None, "confirmed_edits":{}, "confirmed_frames":{}}
        session["drafts"][draft["draft_id"]] = draft
        return draft_view(draft)

    @app.post("/api/claims/{draft_id}/confirm")
    def confirm(draft_id: str, body: Confirmation, request: Request):
        session = session_for(request, write=True)
        with guard:
            draft = draft_for(session, draft_id)
            if draft.get("busy"):
                raise HTTPException(409, "This assessment is running. Wait before editing.")
            if body.expected_revision != draft["revision"]:
                raise HTTPException(409, "The draft changed. Confirm its current version.")
            intent = copy.deepcopy(draft["intent"])
            if body.intent is not None:
                # Domain confirms these explicit user edits, not a generated personal inference.
                for field, value in body.intent.model_dump(exclude_unset=True).items():
                    intent[field] = {"state": "unknown" if value is None else "stated", "value": value, "provenance": []}
            selected = body.selected_proposition_id or draft.get("snapshot",{}).get("selected_proposition_id")
            selected = selected or (draft["claim"]["propositions"][0]["proposition_id"] if len(draft["claim"]["propositions"]) == 1 else None)
            edits = {**draft["confirmed_edits"].get(selected,{}), **body.edits}
            try:
                result = domain.confirm(draft["claim"], intent, selected, edits)
            except domain.DomainError:
                draft["confirmed"] = False
                raise
            fingerprint = semantic_fingerprint(result)
            if draft.get("semantic_fingerprint") == fingerprint:
                draft["confirmed"] = True
                return draft_view(draft)
            if draft.get("snapshot"):
                result["snapshot"]["parent_version_id"] = draft["snapshot"]["version_id"]
                previous_receipt = session["receipts"].get(draft.get("receipt_id"))
                if previous_receipt:
                    draft["supersedes_receipt_version_id"] = previous_receipt["receipt_version_id"]
                draft["parent_attempt_id"] = draft["attempt_id"]
                draft["attempt_id"] = ident()
                draft["ledger"] = AttemptBudget()
            draft["confirmed_edits"][selected] = edits
            draft["confirmed_frames"][selected] = copy.deepcopy(result["snapshot"]["confirmed_proposition"])
            draft["semantic_fingerprint"] = fingerprint
            draft.update(result)
            draft["revision"] += 1
            draft["confirmed"] = True
            draft.pop("receipt_id", None)
            return draft_view(draft)

    @app.post("/api/assessments")
    async def assess(body: AssessmentRequest, request: Request):
        session = session_for(request, write=True)
        with guard:
            draft = draft_for(session, body.draft_id)
            if not draft["confirmed"] or body.expected_revision != draft["revision"]:
                raise HTTPException(409, "Confirm the current claim and intention first.")
            if "receipt_id" in draft:
                return envelope(session, draft["receipt_id"])
            if draft.get("busy"):
                raise HTTPException(409, "This assessment is already running.")
            draft["busy"] = True
        try:
            trusted_pack = copy.deepcopy(pack) if public_demo else reviews.load_current_pack() or copy.deepcopy(pack)
            states = store.trust([s["source_id"] for s in trusted_pack["sources"]])
            trusted_pack["trust_states"] = states
            with draft["ledger"].meter():
                if draft.get("mode") == "live":
                    result = await compiler.assess(draft["snapshot"],draft["intent"],trusted_pack,draft["ledger"])
                else:
                    result = domain.assess(draft["snapshot"], draft["intent"], trusted_pack, mode=draft.get("mode", "replay"))
            source_versions = {s["source_version_id"]:s["source_id"] for s in trusted_pack["sources"]}
            required_versions = {d["id"] for d in result.get("dependencies",[]) if d.get("kind") == "source_version"}
            if required_versions - source_versions.keys():
                raise HTTPException(409, "A required evidence dependency cannot be verified.")
            deps = sorted({e["source_id"] for e in result.get("evidence", []) if e.get("source_id")} |
                          {source_versions[v] for v in required_versions})
            latest = store.trust(deps)
            if any(sid not in latest or latest[sid]["state"] != "current" or latest[sid]["revision"] != states.get(sid,{}).get("revision") for sid in deps):
                raise HTTPException(409, "A required source is under review. No current receipt can be issued.")
            receipt_id = ident()
            receipt = {**result, "receipt_id": receipt_id, "receipt_version_id": ident(), "assessment_id": ident(), "assessed_at": now(),
                       "snapshot": draft["snapshot"], "intent": draft["intent"], "source_ids": deps,
                       "trust_revisions": {sid: states[sid]["revision"] for sid in deps}, "mode": draft.get("mode", "replay"),
                       "extraction_mode":draft.get("mode", "replay"),
                       "alignment_mode":result.get("alignment_mode", "deterministic_library_rules"),
                       "extraction_model_metadata":draft.get("model_metadata"),
                       "attempt_id": draft["attempt_id"], "parent_attempt_id": draft["parent_attempt_id"],
                       "supersedes_receipt_version_id":draft.get("supersedes_receipt_version_id"),
                       "synthetic": result.get("synthetic", not bool(result.get("clinical_review"))), "clinical_review": result.get("clinical_review", False)}
            receipt["content_hash"] = canonical_hash(receipt)
            session["receipts"][receipt_id] = receipt
            draft["receipt_id"] = receipt_id
            return envelope(session, receipt_id)
        finally:
            draft["busy"] = False

    @app.get("/api/receipts/{receipt_id}")
    def read_receipt(receipt_id: uuid.UUID, request: Request):
        return envelope(session_for(request), str(receipt_id))

    @app.post("/api/next-steps/preview")
    def preview(body: PreviewRequest, request: Request):
        session = session_for(request, write=True)
        receipt_env = envelope(session, body.receipt_id)
        receipt = receipt_env["receipt"]
        require_current_claim(session,receipt)
        require_current_comparison(receipt)
        if receipt_env["current_trust"]["state"] != "current":
            raise HTTPException(409, "Evidence changed. Reassess before saving a question.")
        if not receipt.get("save_eligible") or receipt.get("route") in {"urgent_escalation", "clarify"} or receipt.get("system_status") != "ok":
            raise HTTPException(409, "Resolve this assessment's limitation before creating a next step.")
        question = "What does this source establish, what remains uncertain, and what additional evidence would be needed for the intended action?"
        if receipt.get("next_step", {}).get("text"):
            question = receipt["next_step"]["text"]
        preview_id = ident()
        value = {"preview_id": preview_id, "receipt_id": body.receipt_id, "text": question, "expires_at": (datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()}
        value["preview_hash"] = canonical_hash(value)
        session["previews"][preview_id] = value
        return value

    @app.post("/api/next-steps")
    def save(body: SaveRequest, request: Request):
        session = session_for(request, write=True)
        key = request.headers.get("idempotency-key", "")
        if not key or len(key) > 100:
            raise HTTPException(422, "An idempotency key of at most 100 characters is required.")
        if not body.consent:
            raise HTTPException(422, "Explicit permission to save this receipt and question is required.")
        with guard:
            preview = session["previews"].get(body.preview_id)
            if not preview or datetime.fromisoformat(preview["expires_at"]) <= datetime.now(timezone.utc):
                raise HTTPException(409, "Preview expired. Review a new preview before saving.")
            if not hmac.compare_digest(body.preview_hash, preview["preview_hash"]):
                raise HTTPException(409, "The approved preview changed.")
            env = envelope(session, preview["receipt_id"])
            if env["current_trust"]["state"] != "current":
                raise HTTPException(409, "Evidence changed. Reassess before saving.")
            receipt = env["receipt"]
            require_current_claim(session,receipt)
            require_current_comparison(receipt)
            if not receipt.get("save_eligible") or receipt.get("route") in {"urgent_escalation", "clarify"}:
                raise HTTPException(409, "This assessment cannot be saved as an actionable next step.")
            step = store.save(session["owner_id"],session["owner_token"],key,canonical_hash(body.model_dump()),receipt,preview["text"],receipt["source_ids"],receipt["trust_revisions"],publication_guard(receipt))
            return step_view(step,session)

    @app.get("/api/next-steps")
    def list_steps(request: Request):
        session = session_for(request)
        store.expire()
        return {"items": [step_view(s,session) for s in store.list_steps(session["owner_id"])]}

    @app.post("/api/next-steps/{step_id}/check-ins")
    def check_in(step_id: uuid.UUID, body: CheckInRequest, request: Request):
        session = session_for(request, write=True)
        step = store.get_step(session["owner_id"], str(step_id))
        if not step:
            raise HTTPException(404, "Next step not found.")
        if not body.consent:
            raise HTTPException(422, "Consent to save this self-report is required.")
        policy = domain.screen_safety(body.new_concern_text or "")
        if policy.get("route") == "urgent_escalation":
            return {"step": step_view(step,session), "route": "urgent_escalation", "saved": False,
                    "feedback": "This check-in cannot assess an urgent concern. Seek appropriate urgent professional help.", "reassessment_required": True}
        if body.new_concern_text or body.request_reassessment:
            return {"step": step_view(step,session), "route": "clarify", "saved": False,
                    "feedback": "Your context changed. Start a new assessment and confirm it before saving completion.", "reassessment_required": True}
        receipt = step["receipt"]
        with guard:
            require_current_claim(session,receipt)
            require_current_comparison(receipt)
            if current_trust(receipt)["state"] != "current":
                raise HTTPException(409, "Evidence changed. Reassess before checking in.")
            updated = store.check_in(session["owner_id"],str(step_id),body.expected_version,body.state,body.exercise_choice,receipt["source_ids"],receipt["trust_revisions"],publication_guard(receipt))
        feedback = "Saved as your self-report; this does not verify an outcome."
        if body.exercise_choice:
            feedback += " A change from a measured outcome to a different claimed outcome requires its own supporting evidence."
        return {"step": step_view(updated,session), "route": "education", "saved": True, "feedback": feedback,
                "exercise": {"question": "If a source measures one outcome, does it automatically support a different outcome?", "choices": ["same", "different", "unknown"]}}

    @app.delete("/api/account/data")
    def delete_data(request: Request, response: Response):
        session = session_for(request, write=True)
        with guard:
            owner = session["owner_id"]
            store.delete_owner(owner)
            for sid in list(sessions):
                if sessions[sid]["owner_id"] == owner:
                    del sessions[sid]
            response.delete_cookie("el_session")
            response.delete_cookie("el_owner")
            return {"deleted": True, "scope": "saved_receipts_questions_checkins_and_drafts", "backup_policy": "No application backups are configured; database storage reclamation follows PostgreSQL behavior."}

    @app.post("/api/review/login")
    def reviewer_login(body: ReviewerLogin, request: Request):
        session = session_for(request, write=True)
        session["login_attempts"] += 1
        if session["login_attempts"] > 5:
            raise HTTPException(429, "Reviewer sign-in attempt limit reached for this session.")
        token = os.environ.get("REVIEWER_TOKEN", "")
        if not token or not hmac.compare_digest(body.token, token):
            raise HTTPException(403, "Reviewer credential rejected.")
        session["reviewer"] = True
        return {"reviewer": True, "scope": "synthetic_evidence_trust_controls", "clinical_approval": False}

    @app.post("/api/review/editor-login")
    def editor_login(body: ReviewerLogin, request: Request):
        session = session_for(request, write=True)
        session["login_attempts"] += 1
        expected = os.environ.get("EDITOR_TOKEN", "")
        if session["login_attempts"] > 5:
            raise HTTPException(429, "Sign-in attempt limit reached for this session.")
        if not expected or not hmac.compare_digest(body.token, expected):
            raise HTTPException(403, "Editor credential rejected.")
        session["editor"] = True
        return {"editor": True, "scope": "quarantined_evidence_only", "clinical_approval": False}

    @app.post("/api/review/clinical-login")
    def clinical_login(body: ClinicalLogin, request: Request):
        session = session_for(request, write=True)
        session["login_attempts"] += 1
        if session["login_attempts"] > 5:
            raise HTTPException(429, "Sign-in attempt limit reached for this session.")
        record = qualified.get(body.identity, {})
        token_hash = review_config.get("token_hashes", {}).get(body.identity, "")
        if not token_hash or not hmac.compare_digest(digest(body.token), token_hash):
            raise HTTPException(403, "Configured clinical reviewer access is required.")
        reviews._qualified(body.identity, record.get("qualification_id"))
        session["clinical_identity"] = body.identity
        return {"clinical_reviewer": True, "identity": body.identity}

    def clinical_actor(session):
        identity = session["clinical_identity"]
        if not identity:
            raise HTTPException(403, "This action requires a separately configured qualified human reviewer.")
        return identity, qualified[identity]["qualification_id"]

    @app.get("/api/review/queue")
    def review_queue(request: Request):
        session = session_for(request)
        if not (session["editor"] or session["clinical_identity"]):
            raise HTTPException(403, "Editor or clinical reviewer access is required.")
        return reviews.list_queue()

    @app.post("/api/review/sources")
    def import_source(body: SourceImport, request: Request):
        session = session_for(request, write=True)
        if not session["editor"]:
            raise HTTPException(403, "Editor access is required.")
        return reviews.import_source("local-evidence-editor", body.model_dump(mode="json"))

    @app.post("/api/review/briefs")
    def draft_brief(body: BriefDraft, request: Request):
        session = session_for(request, write=True)
        if not session["editor"]:
            raise HTTPException(403, "Editor access is required.")
        return reviews.draft_brief("local-evidence-editor", body.model_dump(mode="json"))

    @app.post("/api/review/sources/{source_id}/withdrawal")
    def withdraw_source(source_id: str, body: SourceWithdrawal, request: Request):
        session = session_for(request, write=True)
        if not session["editor"]:
            raise HTTPException(403, "Editor access is required for an operational withdrawal.")
        return reviews.withdraw_source("local-evidence-editor",source_id,body.expected_revision,body.reason)

    @app.post("/api/review/briefs/{brief_id}/decisions")
    def clinical_decision(brief_id: uuid.UUID, body: BriefDecision, request: Request):
        identity, qualification = clinical_actor(session_for(request, write=True))
        return reviews.review_decision(identity,qualification,str(brief_id),body.decision,body.rationale,body.expected_hash)

    @app.post("/api/review/publications")
    def publish(body: PublishRequest, request: Request):
        identity, qualification = clinical_actor(session_for(request, write=True))
        return reviews.publish(identity,qualification,body.brief_version_ids,body.expected_revision)

    @app.get("/api/review/sources")
    def review_sources(request: Request):
        session_for(request, reviewer=True)
        states = store.trust(sources)
        return {"items": [{**source, **states[sid]} for sid,source in sources.items()], "synthetic": True, "clinical_approval": False}

    @app.post("/api/review/sources/{source_id}/decision")
    def review_decision(source_id: str, body: ReviewDecision, request: Request):
        session_for(request, write=True, reviewer=True)
        if source_id not in sources:
            raise HTTPException(404, "Source not found.")
        with guard:
            result = store.change_trust(source_id,body.expected_revision,"withdrawn" if body.decision == "withdraw" else "current")
            return {**result, "synthetic": True, "clinical_approval": False}

    dist = ROOT / "apps/web/dist"
    if (dist / "demo").is_dir():
        app.mount("/demo", StaticFiles(directory=dist / "demo"), name="demo-media")
    if (dist / "demo-video.html").is_file():
        @app.get("/demo-video.html", include_in_schema=False)
        def demo_video():
            return FileResponse(dist / "demo-video.html", media_type="text/html")
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "API route not found.")
        if not (dist / "index.html").exists():
            return {"status": "API ready", "frontend": "Run npm run build in apps/web, then restart the server."}
        return FileResponse(dist / "index.html")

    return app


app = create_app()
