"""Quarantined evidence and independent review; no clinical approvals are seeded.

Identity and qualification registries are server configuration, never request-created.
Clinical packs loaded here carry an in-process capability after database verification.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from psycopg.types.json import Jsonb

from .contracts import EffectDirection, EvidenceStatus
from .domain import DomainError


REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS review_sources (
 source_version_id uuid PRIMARY KEY, source_id text NOT NULL,
 previous_version_id uuid REFERENCES review_sources(source_version_id),
 editor_identity text NOT NULL, content_hash text NOT NULL, packet_hash text NOT NULL,
 payload jsonb NOT NULL, imported_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_id,packet_hash)
);
CREATE TABLE IF NOT EXISTS review_briefs (
 brief_version_id uuid PRIMARY KEY, family_id text NOT NULL, editor_identity text NOT NULL,
 payload jsonb NOT NULL, target_hash text NOT NULL UNIQUE,
 drafted_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS review_brief_sources (
 brief_version_id uuid NOT NULL REFERENCES review_briefs(brief_version_id),
 source_version_id uuid NOT NULL REFERENCES review_sources(source_version_id),
 role text NOT NULL CHECK(role IN ('supports','limits','conflicts','context')),
 PRIMARY KEY(brief_version_id,source_version_id,role)
);
CREATE TABLE IF NOT EXISTS review_decisions (
 review_id uuid PRIMARY KEY, brief_version_id uuid NOT NULL REFERENCES review_briefs(brief_version_id),
 reviewer_identity text NOT NULL, qualification_id text NOT NULL, qualification_hash text NOT NULL,
 target_hash text NOT NULL, decision text NOT NULL CHECK(decision IN ('approved','changes_requested','rejected')),
 rationale text NOT NULL, conflict_disclosure text NOT NULL,
 reviewed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS review_publications (
 publication_id uuid PRIMARY KEY, publisher_identity text NOT NULL, qualification_id text NOT NULL,
 payload jsonb NOT NULL, payload_hash text NOT NULL, review_ids jsonb NOT NULL,
 published_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS review_publication_pointer (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 publication_id uuid REFERENCES review_publications(publication_id), revision integer NOT NULL DEFAULT 0
);
INSERT INTO review_publication_pointer(singleton,revision) VALUES(true,0) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS review_audit (
 event_id uuid PRIMARY KEY, event_kind text NOT NULL, actor_identity text NOT NULL,
 entity_id text NOT NULL, payload_hash text NOT NULL, reason text CHECK(reason IS NULL OR length(reason)<=1000),
 occurred_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE review_audit ADD COLUMN IF NOT EXISTS reason text CHECK(reason IS NULL OR length(reason)<=1000);
CREATE OR REPLACE FUNCTION review_reject_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'Evidence and review versions are immutable; create a new version'; END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS immutable_review_sources ON review_sources;
CREATE TRIGGER immutable_review_sources BEFORE UPDATE OR DELETE ON review_sources FOR EACH ROW EXECUTE FUNCTION review_reject_mutation();
DROP TRIGGER IF EXISTS immutable_review_briefs ON review_briefs;
CREATE TRIGGER immutable_review_briefs BEFORE UPDATE OR DELETE ON review_briefs FOR EACH ROW EXECUTE FUNCTION review_reject_mutation();
DROP TRIGGER IF EXISTS immutable_review_brief_sources ON review_brief_sources;
CREATE TRIGGER immutable_review_brief_sources BEFORE UPDATE OR DELETE ON review_brief_sources FOR EACH ROW EXECUTE FUNCTION review_reject_mutation();
DROP TRIGGER IF EXISTS immutable_review_decisions ON review_decisions;
CREATE TRIGGER immutable_review_decisions BEFORE UPDATE OR DELETE ON review_decisions FOR EACH ROW EXECUTE FUNCTION review_reject_mutation();
DROP TRIGGER IF EXISTS immutable_review_publications ON review_publications;
CREATE TRIGGER immutable_review_publications BEFORE UPDATE OR DELETE ON review_publications FOR EACH ROW EXECUTE FUNCTION review_reject_mutation();
DROP TRIGGER IF EXISTS immutable_review_audit ON review_audit;
CREATE TRIGGER immutable_review_audit BEFORE UPDATE OR DELETE ON review_audit FOR EACH ROW EXECUTE FUNCTION review_reject_mutation();
"""


def _hash(value) -> str:
    text = value if isinstance(value,str) else json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _now():
    return datetime.now(timezone.utc)


def _parse(model,payload,code):
    try:
        return model.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError(code) from exc


def _uuid(value):
    try:
        return str(UUID(value))
    except (TypeError,ValueError,AttributeError) as exc:
        raise DomainError("invalid_version_id") from exc


def _time(text):
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00"))
        if dt.tzinfo is None:
            raise ValueError()
        return dt
    except (ValueError,AttributeError) as exc:
        raise DomainError("invalid_review_timestamp") from exc


class Strict(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)


class AnchorImport(Strict):
    anchor_id:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.:-]+$")
    start:int=Field(ge=0)
    end:int=Field(gt=0)
    quote:str=Field(min_length=1,max_length=3000)
    section:str=Field(min_length=1,max_length=200)
    original_locator:str=Field(min_length=1,max_length=300)


class SourceImport(Strict):
    source_id:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.:-]+$")
    previous_version_id:str|None=None
    title:str=Field(min_length=1,max_length=300)
    publisher:str=Field(min_length=1,max_length=200)
    canonical_url:str=Field(min_length=8,max_length=1000)
    source_date:str|None=Field(default=None,max_length=40)
    source_type:Literal["guideline","systematic_review","trial","observational","official_information"]
    language:Literal["en"]="en"
    text:str=Field(min_length=1,max_length=16000)
    licensing_note:str=Field(min_length=10,max_length=1000)
    storage_permission:Literal["permission_granted","public_domain","licensed_short_excerpt"]
    permission_reference:str=Field(min_length=5,max_length=1000)
    permission_attested:Literal[True]
    snapshot_complete:bool
    origin_group_ids:list[str]=Field(min_length=1,max_length=12)
    anchors:list[AnchorImport]=Field(min_length=1,max_length=24)

    @model_validator(mode="after")
    def source_valid(self):
        import unicodedata
        url=urlsplit(self.canonical_url)
        if self.source_id.upper().startswith(("SYN-","SYNTH-")):
            raise ValueError("Synthetic demonstration source IDs are reserved")
        if url.scheme!="https" or not url.hostname or url.username or url.password:
            raise ValueError("Source URL must be an HTTPS reference without credentials; it will not be fetched")
        if unicodedata.normalize("NFC",self.text)!=self.text or "\r" in self.text or "\x00" in self.text:
            raise ValueError("Source packet must use NFC Unicode and LF line endings before anchors are entered")
        ids=set()
        for a in self.anchors:
            if a.anchor_id in ids or a.start>=a.end or a.end>len(self.text) or self.text[a.start:a.end]!=a.quote:
                raise ValueError("Anchor offsets must identify its exact quote in the source packet")
            ids.add(a.anchor_id)
        return self


PredicatePath=Literal["population","condition_context","intervention","comparator","measured_outcome","claimed_clinical_outcome","formulation","dose","route","co_intervention","relation","polarity","certainty","generalization","intent.action_kind","intent.current_care_relationship"]


class ReviewedPredicate(Strict):
    field_path:PredicatePath
    allowed_values:list[str]=Field(min_length=1,max_length=12)


class ReviewedOperator(Strict):
    operator_id:Literal["L03","L04","L05","L07","L08","L09","L11","L15"]
    predicates:list[ReviewedPredicate]=Field(min_length=1,max_length=15)
    reason_code:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.:-]+$")
    explanation:str=Field(min_length=10,max_length=600)
    anchor_ids:list[str]=Field(min_length=1,max_length=12)


class ReviewedAdmission(Strict):
    rule_id:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.:-]+$")
    relation:Literal["supports_within_scope","contradicts_within_scope","insufficient"]
    predicates:list[ReviewedPredicate]=Field(min_length=5,max_length=18)

    @model_validator(mode="after")
    def required_scope(self):
        paths=[p.field_path for p in self.predicates]
        if len(paths)!=len(set(paths)) or not {"population","intervention","measured_outcome","relation","polarity"}.issubset(paths):
            raise ValueError("Admission must bind population, intervention, outcome, relation and polarity without duplicate fields")
        return self


class ReviewedConclusion(Strict):
    conclusion_id:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.:-]+$")
    statement:str=Field(min_length=10,max_length=1000)
    outcome_id:str=Field(min_length=1,max_length=100)
    effect_direction:Literal["benefit","no_effect","harm","mixed","undetermined"]
    anchor_ids:list[str]=Field(min_length=1,max_length=16)
    limitations:list[str]=Field(min_length=1,max_length=15)
    admissions:list[ReviewedAdmission]=Field(min_length=1,max_length=10)
    operator_mappings:list[ReviewedOperator]=Field(default_factory=list,max_length=8)
    no_effect_rationale:str|None=Field(default=None,min_length=10,max_length=1000)

    @model_validator(mode="after")
    def equivalence_explicit(self):
        if self.effect_direction=="no_effect" and not self.no_effect_rationale:
            raise ValueError("A no-effect conclusion needs explicit reviewer rationale beyond nonsignificance")
        return self


class SourceDependency(Strict):
    source_version_id:str=Field(min_length=36,max_length=36)
    role:Literal["supports","limits","conflicts","context"]


class ConflictGroup(Strict):
    conflict_id:str=Field(min_length=1,max_length=100)
    conclusion_ids:list[str]=Field(min_length=2,max_length=8)
    rationale:str=Field(min_length=20,max_length=1000)


class BriefDraft(Strict):
    family_id:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_.:-]+$")
    name:str=Field(min_length=1,max_length=200)
    intended_population:Literal["adults_with_type_2_diabetes"]
    language:Literal["en"]="en"
    intervention_aliases:list[str]=Field(min_length=1,max_length=12)
    source_dependencies:list[SourceDependency]=Field(min_length=1,max_length=8)
    conclusions:list[ReviewedConclusion]=Field(min_length=1,max_length=8)
    conflicts:list[ConflictGroup]=Field(default_factory=list,max_length=4)
    review_due_at:str=Field(min_length=20,max_length=40)
    quality_appraisal_label:str=Field(min_length=5,max_length=300)
    quality_appraisal_method:str=Field(min_length=10,max_length=1000)
    professional_question:str=Field(min_length=10,max_length=600)
    scope_note:str=Field(min_length=20,max_length=1500)

    @model_validator(mode="after")
    def bounded_brief(self):
        ids=[c.conclusion_id for c in self.conclusions]
        if len(ids)!=len(set(ids)):
            raise ValueError("Conclusion IDs must be unique")
        for conflict in self.conflicts:
            if not set(conflict.conclusion_ids).issubset(ids) or len(set(conflict.conclusion_ids))<2:
                raise ValueError("Conflict groups must reference distinct included conclusions")
        if _time(self.review_due_at)<=_now():
            raise ValueError("Review due date must be in the future")
        return self


_PACK_CAPABILITY=object()


class VerifiedClinicalPack(dict):
    """A process-local marker; JSON import cannot create publication authority."""
    def __init__(self,payload,capability=None):
        if capability is not _PACK_CAPABILITY:
            raise DomainError("publication_verification_required")
        super().__init__(payload)
        self._capability=capability
        self._verified_hash=_hash(payload)

    @property
    def publication_verified(self):
        # Runtime trust overlay is mutable; immutable publication material is not.
        payload={k:v for k,v in self.items() if k!="trust_states"}
        return self._capability is _PACK_CAPABILITY and _hash(payload)==self._verified_hash

    def __deepcopy__(self,memo):
        from copy import deepcopy
        if not self.publication_verified:
            raise DomainError("publication_integrity_error")
        copied=VerifiedClinicalPack(deepcopy({k:v for k,v in self.items() if k!="trust_states"},memo),_PACK_CAPABILITY)
        if "trust_states" in self:
            copied["trust_states"]=deepcopy(self["trust_states"],memo)
        return copied


def is_verified_clinical_pack(pack):
    return isinstance(pack,VerifiedClinicalPack) and pack.publication_verified


class EvidenceReviewStore:
    def __init__(self,store,qualified_reviewers=None,clinical_enabled=False):
        self.store=store
        self.qualified_reviewers=qualified_reviewers or {}
        self.clinical_enabled=clinical_enabled

    def _qualified(self,identity,record):
        if not self.clinical_enabled:
            raise DomainError("clinical_review_disabled", "Clinical approval needs a separately configured qualified human reviewer.",403)
        registered=self.qualified_reviewers.get(identity)
        if not registered or identity.startswith("synthetic") or identity.startswith("local-demo"):
            raise DomainError("qualified_reviewer_required",status_code=403)
        required={"qualification_id","credential_reference","verified_by","verified_at","expires_at","scope","conflict_disclosure"}
        if not isinstance(registered,dict) or not required.issubset(registered) or registered.get("scope")!="adult_type_2_diabetes_evidence":
            raise DomainError("invalid_qualification_record",status_code=403)
        if any(not isinstance(registered[k],str) or not registered[k].strip() for k in required):
            raise DomainError("invalid_qualification_record",status_code=403)
        if _time(registered["expires_at"])<=_now() or _time(registered["verified_at"])>_now():
            raise DomainError("qualification_expired",status_code=403)
        supplied=record if isinstance(record,str) else record.get("qualification_id") if isinstance(record,dict) else None
        if supplied!=registered["qualification_id"]:
            raise DomainError("qualification_record_mismatch",status_code=403)
        return registered

    @staticmethod
    def _identity(identity):
        if not isinstance(identity,str) or not 3<=len(identity)<=160:
            raise DomainError("authenticated_editor_required",status_code=403)

    @staticmethod
    def _audit(con,kind,identity,entity,content_hash,reason=None):
        con.execute("INSERT INTO review_audit(event_id,event_kind,actor_identity,entity_id,payload_hash,reason) VALUES(%s,%s,%s,%s,%s,%s)",
                    (str(uuid4()),kind,identity,entity,content_hash,reason))

    def import_source(self,editor_identity,payload):
        self._identity(editor_identity)
        source=_parse(SourceImport,payload,"invalid_source_packet")
        if source["previous_version_id"]:
            source["previous_version_id"]=_uuid(source["previous_version_id"])
        packet_hash=_hash(source)
        version_id=str(uuid4())
        with self.store.connect() as con:
            reserved=con.execute("SELECT 1 FROM evidence_state e WHERE e.source_id=%s AND NOT EXISTS(SELECT 1 FROM review_sources r WHERE r.source_id=e.source_id)",(source["source_id"],)).fetchone()
            if reserved:
                raise DomainError("reserved_source_identity")
            prior=con.execute("SELECT source_version_id,packet_hash FROM review_sources WHERE source_id=%s AND packet_hash=%s",(source["source_id"],packet_hash)).fetchone()
            if prior:
                return {"source_version_id":str(prior["source_version_id"]),"packet_hash":packet_hash,"state":"quarantined","duplicate":True}
            if source["previous_version_id"]:
                previous=con.execute("SELECT source_id FROM review_sources WHERE source_version_id=%s",(source["previous_version_id"],)).fetchone()
                if not previous or previous["source_id"]!=source["source_id"]:
                    raise DomainError("source_version_lineage_mismatch")
            con.execute("INSERT INTO review_sources(source_version_id,source_id,previous_version_id,editor_identity,content_hash,packet_hash,payload) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (version_id,source["source_id"],source["previous_version_id"],editor_identity,_hash(source["text"]),packet_hash,Jsonb(source)))
            con.execute("INSERT INTO evidence_state(source_id,state) VALUES(%s,'under_review') ON CONFLICT(source_id) DO UPDATE SET state='under_review',revision=evidence_state.revision+1,changed_at=now()",(source["source_id"],))
            self._audit(con,"source_quarantined",editor_identity,version_id,packet_hash)
        return {"source_version_id":version_id,"packet_hash":packet_hash,"content_hash":_hash(source["text"]),"state":"quarantined","duplicate":False}

    def withdraw_source(self,editor_identity,source_id,expected_revision,reason):
        """Operational withdrawal removes authority; it can never grant approval."""
        self._identity(editor_identity)
        import re
        if not isinstance(source_id,str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}",source_id):
            raise DomainError("invalid_source_id")
        if type(expected_revision) is not int or expected_revision<1:
            raise DomainError("invalid_trust_revision")
        if not isinstance(reason,str) or not 3<=len(reason.strip())<=1000:
            raise DomainError("invalid_withdrawal_reason")
        reason=reason.strip()
        with self.store.connect() as con:
            # Same lock order as publication, review decisions and receipt writes.
            pointer=con.execute("SELECT revision FROM review_publication_pointer WHERE singleton=true FOR UPDATE").fetchone()
            if not pointer:
                raise DomainError("review_store_unavailable",status_code=503)
            if not con.execute("SELECT 1 FROM review_sources WHERE source_id=%s LIMIT 1",(source_id,)).fetchone():
                raise DomainError("unknown_review_source",status_code=404)
            state=con.execute("SELECT source_id,state,revision FROM evidence_state WHERE source_id=%s FOR UPDATE",(source_id,)).fetchone()
            if not state or state["revision"]!=expected_revision:
                raise DomainError("source_revision_changed",status_code=409)
            changed=con.execute("UPDATE evidence_state SET state='withdrawn',revision=revision+1,changed_at=now() WHERE source_id=%s RETURNING source_id,state,revision",(source_id,)).fetchone()
            self._audit(con,"source_withdrawn",editor_identity,source_id,_hash({"source_id":source_id,"revision":changed["revision"],"reason":reason}),reason)
            return dict(changed)

    @staticmethod
    def _sources(con,version_ids):
        version_ids={_uuid(v) for v in version_ids}
        rows=con.execute("SELECT * FROM review_sources WHERE source_version_id=ANY(%s::uuid[]) ORDER BY source_version_id",(list(version_ids),)).fetchall()
        if len(rows)!=len(set(version_ids)):
            raise DomainError("unknown_source_version")
        for row in rows:
            source=_parse(SourceImport,row["payload"],"invalid_stored_source")
            if row["packet_hash"]!=_hash(source) or row["content_hash"]!=_hash(source["text"]):
                raise DomainError("source_packet_integrity_error")
        return rows

    @staticmethod
    def _target_hash(brief,sources):
        return _hash({"brief":brief,"source_packets":sorted((str(s["source_version_id"]),s["packet_hash"]) for s in sources)})

    def draft_brief(self,editor_identity,payload):
        self._identity(editor_identity)
        brief=_parse(BriefDraft,payload,"invalid_brief")
        with self.store.connect() as con:
            sources=self._sources(con,{d["source_version_id"] for d in brief["source_dependencies"]})
            anchors={}
            for source in sources:
                for anchor in source["payload"]["anchors"]:
                    if anchor["anchor_id"] in anchors:
                        raise DomainError("ambiguous_global_anchor_id")
                    anchors[anchor["anchor_id"]]=anchor
            for conclusion in brief["conclusions"]:
                if not set(conclusion["anchor_ids"]).issubset(anchors):
                    raise DomainError("unresolved_conclusion_anchor")
                for operator in conclusion["operator_mappings"]:
                    if not set(operator["anchor_ids"]).issubset(conclusion["anchor_ids"]):
                        raise DomainError("operator_anchor_outside_conclusion")
            target_hash=self._target_hash(brief,sources)
            prior=con.execute("SELECT brief_version_id FROM review_briefs WHERE target_hash=%s",(target_hash,)).fetchone()
            if prior:
                return {"brief_version_id":str(prior["brief_version_id"]),"target_hash":target_hash,"state":"draft","duplicate":True}
            version_id=str(uuid4())
            con.execute("INSERT INTO review_briefs(brief_version_id,family_id,editor_identity,payload,target_hash) VALUES(%s,%s,%s,%s,%s)",
                        (version_id,brief["family_id"],editor_identity,Jsonb(brief),target_hash))
            for dependency in brief["source_dependencies"]:
                con.execute("INSERT INTO review_brief_sources(brief_version_id,source_version_id,role) VALUES(%s,%s,%s)",
                            (version_id,dependency["source_version_id"],dependency["role"]))
            self._audit(con,"brief_drafted",editor_identity,version_id,target_hash)
        return {"brief_version_id":version_id,"target_hash":target_hash,"state":"draft","duplicate":False}

    def review_decision(self,reviewer_identity,qualification_record,brief_version_id,decision,rationale,expected_hash):
        qualification=self._qualified(reviewer_identity,qualification_record)
        brief_version_id=_uuid(brief_version_id)
        if decision not in {"approved","changes_requested","rejected"} or not isinstance(rationale,str) or not 20<=len(rationale)<=2000:
            raise DomainError("invalid_review_decision")
        with self.store.connect() as con:
            # Serialize review invalidation with receipt save/check-in publication guards.
            con.execute("SELECT revision FROM review_publication_pointer WHERE singleton=true FOR UPDATE").fetchone()
            row=con.execute("SELECT * FROM review_briefs WHERE brief_version_id=%s FOR UPDATE",(brief_version_id,)).fetchone()
            if not row:
                raise DomainError("unknown_brief")
            brief=_parse(BriefDraft,row["payload"],"invalid_or_overdue_brief")
            sources=self._sources(con,{d["source_version_id"] for d in brief["source_dependencies"]})
            if reviewer_identity==row["editor_identity"] or any(reviewer_identity==s["editor_identity"] for s in sources):
                raise DomainError("independent_reviewer_required",status_code=403)
            target=self._target_hash(brief,sources)
            if expected_hash!=target or row["target_hash"]!=target:
                raise DomainError("review_target_changed",status_code=409)
            review_id=str(uuid4())
            con.execute("INSERT INTO review_decisions(review_id,brief_version_id,reviewer_identity,qualification_id,qualification_hash,target_hash,decision,rationale,conflict_disclosure) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (review_id,brief_version_id,reviewer_identity,qualification["qualification_id"],_hash(qualification),target,decision,rationale,qualification["conflict_disclosure"]))
            self._audit(con,"review_"+decision,reviewer_identity,brief_version_id,target)
            if decision!="approved":
                for source in sources:
                    con.execute("UPDATE evidence_state SET state='under_review',revision=revision+1,changed_at=now() WHERE source_id=%s",(source["source_id"],))
        return {"review_id":review_id,"brief_version_id":brief_version_id,"decision":decision,"target_hash":target}

    def _approved(self,con,brief_version_ids):
        brief_version_ids={_uuid(v) for v in brief_version_ids}
        rows=con.execute("SELECT * FROM review_briefs WHERE brief_version_id=ANY(%s::uuid[]) ORDER BY family_id,brief_version_id FOR UPDATE",(list(brief_version_ids),)).fetchall()
        if len(rows)!=len(set(brief_version_ids)):
            raise DomainError("unknown_brief")
        material=[]
        for row in rows:
            brief=_parse(BriefDraft,row["payload"],"invalid_or_overdue_brief")
            sources=self._sources(con,{d["source_version_id"] for d in brief["source_dependencies"]})
            review=con.execute("SELECT * FROM review_decisions WHERE brief_version_id=%s ORDER BY reviewed_at DESC,review_id DESC LIMIT 1",(row["brief_version_id"],)).fetchone()
            if not review or review["decision"]!="approved" or review["target_hash"]!=row["target_hash"] or row["target_hash"]!=self._target_hash(brief,sources):
                raise DomainError("brief_not_approved",status_code=409)
            registered=self._qualified(review["reviewer_identity"],review["qualification_id"])
            if _hash(registered)!=review["qualification_hash"]:
                raise DomainError("reviewer_qualification_changed",status_code=409)
            material.append((row,sources,review))
        return material

    @staticmethod
    def _pack(publication_id,material):
        pack={"schema_version":"EvidencePack/1.0","publication_id":publication_id,"label":"Reviewed evidence library — personal suitability is not assessed",
              "domain":"clinical_reviewed","clinical_review":True,"trust_state":"current","sources":[],"families":[],"conclusions":[],"review_records":[]}
        source_ids,anchor_ids,conclusion_ids,family_ids=set(),set(),set(),set()
        logical_sources={}
        for row,sources,review in material:
            brief=row["payload"]
            if brief["family_id"] in family_ids:
                raise DomainError("duplicate_publication_family")
            family_ids.add(brief["family_id"])
            pack["families"].append({**brief,"brief_version_id":str(row["brief_version_id"]),"conclusion_ids":[c["conclusion_id"] for c in brief["conclusions"]],
                                     "trust_state":"current","review_id":str(review["review_id"]),
                                     "enabled_operators":sorted({m["operator_id"] for c in brief["conclusions"] for m in c["operator_mappings"]})})
            for source in sources:
                sid=str(source["source_version_id"])
                if sid in source_ids:
                    continue
                source_ids.add(sid)
                data=source["payload"]
                if data["source_id"] in logical_sources and logical_sources[data["source_id"]]!=sid:
                    raise DomainError("mixed_source_versions")
                logical_sources[data["source_id"]]=sid
                anchors=[]
                for anchor in data["anchors"]:
                    if anchor["anchor_id"] in anchor_ids:
                        raise DomainError("duplicate_publication_anchor")
                    anchor_ids.add(anchor["anchor_id"])
                    anchors.append({**anchor,"source_version_id":sid,"quote_hash":_hash(anchor["quote"])})
                pack["sources"].append({**data,"source_version_id":sid,"content_hash":source["content_hash"],"packet_hash":source["packet_hash"],
                                        "synthetic":False,"trust_state":"current","anchors":anchors})
            for conclusion in brief["conclusions"]:
                if conclusion["conclusion_id"] in conclusion_ids:
                    raise DomainError("duplicate_publication_conclusion")
                conclusion_ids.add(conclusion["conclusion_id"])
                deps=[s["source_version_id"] for s in pack["sources"] if any(a["anchor_id"] in conclusion["anchor_ids"] for a in s["anchors"])]
                pack["conclusions"].append({**conclusion,"family_id":brief["family_id"],"brief_version_id":str(row["brief_version_id"]),
                    "source_version_ids":deps,"source_version_id":deps[0],"review_id":str(review["review_id"]),"review_status":"qualified_evidence_review",
                    "allowed_relations":sorted({a["relation"] for a in conclusion["admissions"]}|{"insufficient"}|({"conflicting"} if any(conclusion["conclusion_id"] in c["conclusion_ids"] for c in brief["conflicts"]) else set()))})
            pack["review_records"].append({"review_id":str(review["review_id"]),"reviewer_identity":review["reviewer_identity"],"qualification_id":review["qualification_id"],
                "reviewed_at":review["reviewed_at"].isoformat(),"target_hash":review["target_hash"],"decision":"approved","conflict_disclosure":review["conflict_disclosure"]})
        return pack

    def publish(self,reviewer_identity,qualification_record,brief_version_ids,expected_revision):
        qualification=self._qualified(reviewer_identity,qualification_record)
        if not isinstance(brief_version_ids,list) or not 1<=len(brief_version_ids)<=6 or len(set(brief_version_ids))!=len(brief_version_ids):
            raise DomainError("publication_bounds")
        with self.store.connect() as con:
            pointer=con.execute("SELECT * FROM review_publication_pointer WHERE singleton=true FOR UPDATE").fetchone()
            if not pointer or pointer["revision"]!=expected_revision:
                raise DomainError("publication_revision_changed",status_code=409)
            material=self._approved(con,brief_version_ids)
            publication_id=str(uuid4())
            pack=self._pack(publication_id,material)
            source_ids=sorted({s["source_id"] for s in pack["sources"]})
            trust=self.store.trust(source_ids,con,lock=True)
            if any(sid not in trust or trust[sid]["state"]=="withdrawn" for sid in source_ids):
                raise DomainError("source_withdrawn",status_code=409)
            for _,sources,_ in material:
                for source in sources:
                    latest=con.execute("SELECT source_version_id FROM review_sources WHERE source_id=%s ORDER BY imported_at DESC,source_version_id DESC LIMIT 1",(source["source_id"],)).fetchone()
                    if str(latest["source_version_id"])!=str(source["source_version_id"]):
                        raise DomainError("newer_source_requires_review",status_code=409)
            con.execute("INSERT INTO review_publications(publication_id,publisher_identity,qualification_id,payload,payload_hash,review_ids) VALUES(%s,%s,%s,%s,%s,%s)",
                        (publication_id,reviewer_identity,qualification["qualification_id"],Jsonb(pack),_hash(pack),Jsonb([str(m[2]["review_id"]) for m in material])))
            con.execute("UPDATE review_publication_pointer SET publication_id=%s,revision=revision+1 WHERE singleton=true",(publication_id,))
            for sid in source_ids:
                con.execute("UPDATE evidence_state SET state='current',revision=revision+1,changed_at=now() WHERE source_id=%s",(sid,))
            self._audit(con,"publication_committed",reviewer_identity,publication_id,_hash(pack))
        return {"publication_id":publication_id,"revision":expected_revision+1,"source_ids":source_ids,"pack_hash":_hash(pack)}

    def load_current_pack(self):
        with self.store.connect() as con:
            row=con.execute("SELECT p.*,r.revision FROM review_publication_pointer r JOIN review_publications p ON p.publication_id=r.publication_id WHERE r.singleton=true").fetchone()
            if not row:
                return None
            payload=row["payload"]
            if _hash(payload)!=row["payload_hash"]:
                raise DomainError("publication_integrity_error",status_code=503)
            material=self._approved(con,[f["brief_version_id"] for f in payload["families"]])
            rebuilt=self._pack(str(row["publication_id"]),material)
            if _hash(rebuilt)!=row["payload_hash"]:
                raise DomainError("publication_review_changed",status_code=503)
            pack=VerifiedClinicalPack(payload,_PACK_CAPABILITY)
            pack["trust_states"]=self.store.trust({s["source_id"] for s in payload["sources"]},con)
            return pack

    def require_current_publication(self,con,publication_id):
        """Call inside the caller's write transaction BEFORE locking source rows."""
        publication_id=_uuid(publication_id)
        pointer=con.execute("SELECT publication_id,revision FROM review_publication_pointer WHERE singleton=true FOR UPDATE").fetchone()
        if not pointer or str(pointer["publication_id"])!=publication_id:
            raise DomainError("publication_revision_changed",status_code=409)
        row=con.execute("SELECT payload,payload_hash FROM review_publications WHERE publication_id=%s",(publication_id,)).fetchone()
        if not row or _hash(row["payload"])!=row["payload_hash"]:
            raise DomainError("publication_integrity_error",status_code=409)
        try:
            material=self._approved(con,[f["brief_version_id"] for f in row["payload"]["families"]])
        except DomainError as exc:
            raise DomainError(exc.code,status_code=409) from exc
        if _hash(self._pack(publication_id,material))!=row["payload_hash"]:
            raise DomainError("publication_review_changed",status_code=409)
        return {"publication_id":publication_id,"revision":pointer["revision"]}

    def list_queue(self):
        with self.store.connect() as con:
            sources=con.execute("""SELECT r.source_version_id,r.source_id,r.editor_identity,r.content_hash,r.packet_hash,r.payload,r.imported_at,e.state,e.revision
                FROM review_sources r LEFT JOIN evidence_state e ON e.source_id=r.source_id ORDER BY r.imported_at DESC LIMIT 100""").fetchall()
            briefs=con.execute("""SELECT b.*, (SELECT decision FROM review_decisions d WHERE d.brief_version_id=b.brief_version_id ORDER BY reviewed_at DESC,review_id DESC LIMIT 1) AS latest_decision
                FROM review_briefs b ORDER BY drafted_at DESC LIMIT 100""").fetchall()
            pointer=con.execute("SELECT publication_id,revision FROM review_publication_pointer WHERE singleton=true").fetchone()
            def output(row):
                return {k:v.isoformat() if isinstance(v,datetime) else str(v) if k.endswith("_id") and v is not None else v for k,v in row.items()}
            return {"sources":[output(s) for s in sources],"briefs":[output(b) for b in briefs],"publication":output(pointer),
                    "clinical_enabled":self.clinical_enabled,"qualified_reviewer_count":len(self.qualified_reviewers)}
