"""Versioned domain contracts. Original spans exist only in ephemeral ClaimIR."""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Generic, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field as PydanticField, model_serializer, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class CaseState(StrEnum):
    captured = "captured"
    needs_confirmation = "needs_confirmation"
    ready = "ready"
    assessing = "assessing"
    assessed = "assessed"
    cannot_assess = "cannot_assess"


class Route(StrEnum):
    education = "education"
    clarify = "clarify"
    professional_review_recommended = "professional_review_recommended"
    urgent_escalation = "urgent_escalation"


class Coverage(StrEnum):
    matched = "matched"
    no_matching_approved_evidence = "no_matching_approved_evidence"
    blocked = "blocked"


class EvidenceStatus(StrEnum):
    supports_within_scope = "supports_within_scope"
    contradicts_within_scope = "contradicts_within_scope"
    insufficient = "insufficient"
    conflicting = "conflicting"
    not_assessable = "not_assessable"


class EffectDirection(StrEnum):
    benefit = "benefit"
    no_effect = "no_effect"
    harm = "harm"
    mixed = "mixed"
    undetermined = "undetermined"


class Applicability(StrEnum):
    scenario_aligned = "scenario_aligned"
    scope_mismatch = "scope_mismatch"
    unknown = "unknown"


class SystemStatus(StrEnum):
    ok = "ok"
    model_error = "model_error"
    evidence_integrity_error = "evidence_integrity_error"
    evidence_under_review = "evidence_under_review"
    unavailable = "unavailable"


class OperatorState(StrEnum):
    established = "established"
    not_detected = "not_detected"
    unknown = "unknown"
    not_applicable = "not_applicable"


BoundedText = Annotated[str, PydanticField(min_length=1, max_length=600)]
ShortText = Annotated[str, PydanticField(min_length=1, max_length=160)]
Identifier = Annotated[str, PydanticField(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")]
Hash = Annotated[str, PydanticField(pattern=r"^[a-f0-9]{64}$")]


class Provenance(StrictModel):
    kind: Literal["input_span", "user_confirmation", "saved_ref"]
    input_hash: Hash | None = None
    start: int | None = PydanticField(default=None, ge=0)
    end: int | None = PydanticField(default=None, ge=0)
    quote: BoundedText | None = None
    confirmation_event_id: Identifier | None = None
    ref_id: Identifier | None = None

    @model_validator(mode="after")
    def valid_origin(self):
        if self.kind == "input_span":
            if self.input_hash is None or self.start is None or self.end is None or self.quote is None:
                raise ValueError("input_span needs a hash, exact quote and offsets")
            if self.end <= self.start:
                raise ValueError("input span must be nonempty and half-open")
        elif self.kind == "user_confirmation" and not self.confirmation_event_id:
            raise ValueError("confirmation provenance needs an event ID")
        elif self.kind == "saved_ref" and not self.ref_id:
            raise ValueError("saved provenance needs a reference ID")
        if self.kind != "input_span" and self.quote is not None:
            raise ValueError("only ephemeral input provenance can contain quotations")
        return self

    @model_serializer(mode="plain")
    def serialize_origin(self):
        if self.kind == "saved_ref":
            return {"kind": self.kind, "ref_id": self.ref_id}
        if self.kind == "user_confirmation":
            return {"kind": self.kind, "confirmation_event_id": self.confirmation_event_id}
        return {"kind": self.kind, "input_hash": self.input_hash, "start": self.start,
                "end": self.end, "quote": self.quote}


T = TypeVar("T")


class SemanticField(StrictModel, Generic[T]):
    state: Literal["stated", "unknown", "ambiguous", "not_applicable"] = "unknown"
    value: T | None = None
    provenance: list[Provenance] = PydanticField(default_factory=list, max_length=6)
    reason_code: Identifier | None = None

    @model_validator(mode="after")
    def state_value(self):
        if self.state == "stated":
            if self.value is None or (isinstance(self.value, str) and not self.value.strip()):
                raise ValueError("stated fields need a nonempty value")
            if not self.provenance:
                raise ValueError("stated fields need provenance")
        elif self.value is not None:
            raise ValueError("unknown/ambiguous/not_applicable fields require null values")
        if self.state == "not_applicable" and not self.reason_code:
            raise ValueError("not_applicable requires a field-specific reason")
        return self


class Concept(StrictModel):
    surface: ShortText
    concept_id: Identifier | None = None


class Magnitude(StrictModel):
    value: float
    unit: ShortText
    basis: Literal["absolute", "relative", "unspecified"]


class Timeframe(StrictModel):
    value: float = PydanticField(gt=0, le=100000)
    unit: ShortText


class Assumption(StrictModel):
    code: Identifier
    affected_edge_id: Identifier
    required_field_paths: list[ShortText] = PydanticField(max_length=8)


class Proposition(StrictModel):
    proposition_id: Identifier
    speaker: Literal["quoted_source", "user", "unknown"] = "unknown"
    speech_act: Literal["assertion", "question", "reported_assertion"] = "assertion"
    attribution_text: SemanticField[BoundedText] = PydanticField(default_factory=SemanticField)
    population: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    condition_context: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    intervention: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    comparator: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    formulation: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    dose: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    route: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    co_intervention: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    measured_outcome: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    claimed_clinical_outcome: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    mechanism: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    safety_outcome: SemanticField[Concept] = PydanticField(default_factory=SemanticField)
    magnitude: SemanticField[Magnitude] = PydanticField(default_factory=SemanticField)
    timeframe: SemanticField[Timeframe] = PydanticField(default_factory=SemanticField)
    generalization: SemanticField[Literal["subgroup", "scoped_population", "universal"]] = PydanticField(default_factory=SemanticField)
    relation: SemanticField[Literal["causal", "associative", "descriptive"]] = PydanticField(default_factory=SemanticField)
    certainty: SemanticField[Literal["possible", "probable", "asserted", "guaranteed"]] = PydanticField(default_factory=SemanticField)
    polarity: SemanticField[Literal["affirmed", "negated"]] = PydanticField(default_factory=SemanticField)
    negation_scope: SemanticField[list[ShortText]] = PydanticField(default_factory=SemanticField)
    claimed_evidence_type: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    claimed_source_type: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    missing_assumptions: list[Assumption] = PydanticField(default_factory=list, max_length=8)


ActionKind = Literal["learn", "discuss", "start", "add", "replace", "stop", "delay", "change_dose", "prevent", "seek_cure", "other"]


class IntentIR(StrictModel):
    schema_version: Literal["IntentIR/1.0"] = "IntentIR/1.0"
    intent_id: Identifier
    version_id: Identifier
    claim_version_id: Identifier
    confirmation_event_id: Identifier | None = None
    confirmed_at: str | None = None
    action_kind: SemanticField[ActionKind] = PydanticField(default_factory=SemanticField)
    target: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    current_care_relationship: SemanticField[Literal["alongside", "instead_of", "unrelated"]] = PydanticField(default_factory=SemanticField)
    timing: SemanticField[ShortText] = PydanticField(default_factory=SemanticField)
    actor: SemanticField[Literal["self", "another_person", "hypothetical"]] = PydanticField(default_factory=SemanticField)
    endorsement: SemanticField[Literal["supports", "rejects", "uncertain", "not_stated"]] = PydanticField(default_factory=SemanticField)


class ClaimIR(StrictModel):
    schema_version: Literal["ClaimIR/1.0"] = "ClaimIR/1.0"
    claim_id: Identifier
    version_id: Identifier
    parent_version_id: Identifier | None = None
    input_hash: Hash
    original_text: str = PydanticField(max_length=6000)
    normalized_text: str = PydanticField(max_length=6000)
    normalization_map: list[list[int]] = PydanticField(max_length=6001)
    propositions: list[Proposition] = PydanticField(min_length=1, max_length=3)
    selected_proposition_id: Identifier | None = None
    unresolved_fields: list[ShortText] = PydanticField(default_factory=list, max_length=100)
    confirmed_at: str | None = None
    confirmation_event_id: Identifier | None = None
    extraction_run_id: Identifier
    prompt_version: str = "fixture-v1"
    mode: Literal["replay", "manual", "live"] = "replay"
    safety_flags: list[Identifier] = PydanticField(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_selection(self):
        ids = [p.proposition_id for p in self.propositions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate proposition IDs")
        if self.selected_proposition_id is not None and self.selected_proposition_id not in ids:
            raise ValueError("selection must reference an extracted proposition")
        return self


class ExtractionCandidate(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    propositions: list[Proposition] = PydanticField(min_length=1, max_length=3)
    intent_candidate: dict[str, Any] | None = None
    unresolved_fields: list[ShortText] = PydanticField(default_factory=list, max_length=100)


class CompactExtractedField(StrictModel):
    name: Literal["population", "condition_context", "intervention", "comparator", "measured_outcome", "claimed_clinical_outcome", "mechanism", "safety_outcome", "formulation", "dose", "route", "co_intervention", "relation", "polarity", "certainty", "generalization", "attribution_text"]
    value: ShortText
    quote: BoundedText
    occurrence: int | None = PydanticField(default=None,ge=0,le=99)


class CompactProposition(StrictModel):
    proposition_id: Identifier
    speaker: Literal["quoted_source", "user", "unknown"]
    speech_act: Literal["assertion", "question", "reported_assertion"]
    fields: list[CompactExtractedField] = PydanticField(min_length=1,max_length=17)


class CompactExtractionCandidate(StrictModel):
    propositions: list[CompactProposition] = PydanticField(min_length=1,max_length=3)
    unresolved_fields: list[ShortText] = PydanticField(default_factory=list,max_length=40)


class ProvenanceReference(StrictModel):
    ref_id: Identifier
    field_path: ShortText
    input_hash: Hash | None = None
    start: int | None = PydanticField(default=None, ge=0)
    end: int | None = PydanticField(default=None, ge=0)
    confirmation_event_id: Identifier | None = None


class ConfirmedClaimSnapshot(StrictModel):
    schema_version: Literal["ConfirmedClaimSnapshot/1.0"] = "ConfirmedClaimSnapshot/1.0"
    claim_id: Identifier
    version_id: Identifier
    parent_version_id: Identifier | None = None
    selected_proposition_id: Identifier
    confirmed_proposition: Proposition
    confirmed_at: str
    confirmation_event_id: Identifier
    origin_claim_ir_version: Identifier
    provenance_refs: list[ProvenanceReference] = PydanticField(max_length=250)
    safety_flags: list[Identifier] = PydanticField(default_factory=list, max_length=30)
    mode: Literal["replay", "manual", "live"]

    @model_validator(mode="after")
    def no_raw_provenance(self):
        if self.selected_proposition_id != self.confirmed_proposition.proposition_id:
            raise ValueError("snapshot selection mismatch")
        ids = {r.ref_id for r in self.provenance_refs}
        for value in self.confirmed_proposition.model_dump().values():
            if isinstance(value, dict) and "provenance" in value:
                for ref in value["provenance"]:
                    if ref["kind"] != "saved_ref" or ref.get("quote") is not None or ref["ref_id"] not in ids:
                        raise ValueError("saved fields must reference minimized provenance")
        return self


class FieldMatch(StrictModel):
    claim_path: ShortText
    brief_path: ShortText
    match: Literal["aligned", "differs", "unknown"]


class OperatorCandidate(StrictModel):
    operator_id: Literal["L03", "L04", "L05", "L07", "L08", "L09", "L11", "L15"]
    claim_paths: list[ShortText] = PydanticField(max_length=8)
    conclusion_ids: list[Identifier] = PydanticField(min_length=1, max_length=8)
    anchor_ids: list[Identifier] = PydanticField(min_length=1, max_length=8)
    reason_code: Identifier


class Alignment(StrictModel):
    proposition_id: Identifier
    conclusion_id: Identifier
    relation_candidate: EvidenceStatus
    field_matches: list[FieldMatch] = PydanticField(max_length=20)
    operator_candidates: list[OperatorCandidate] = PydanticField(default_factory=list, max_length=8)


class AlignmentCandidate(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    alignments: list[Alignment] = PydanticField(max_length=8)
