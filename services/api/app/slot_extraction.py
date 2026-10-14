"""Required nullable extraction slots, expanded into the existing ephemeral IR.

The wire format makes every field an explicit decision without requiring the
model to invent a value. Quote existence establishes provenance, not correctness
of the model's semantic classification or role assignment.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal
import unicodedata

from pydantic import Field, ValidationError

from . import domain
from .contracts import BoundedText, StrictModel


SLOT_FIELDS = (
    "population", "condition_context", "intervention", "comparator",
    "measured_outcome", "claimed_clinical_outcome", "mechanism", "safety_outcome",
    "formulation", "dose", "route", "co_intervention", "relation", "polarity",
    "certainty", "generalization", "attribution_text",
)

_REFERENCE_GUARD_FIELDS = {"population", "intervention", "measured_outcome"}
_UNRESOLVED_REFERENCE = re.compile(
    r"(?:it|its|itself|they|them|theirs|themselves|"
    r"he|him|his|himself|she|her|hers|herself|"
    r"this|that|these|those|"
    r"(?:this|that)\s+(?:one|thing)|(?:these|those)\s+(?:ones|things)|"
    r"(?:(?:some|any|every)(?:one|body|thing)|nobody|nothing)(?:\s+else)?|"
    r"no\s+one(?:\s+else)?|none)",
    re.IGNORECASE,
)


def _unresolved_reference(quote: str) -> bool:
    """Recognize only whole pronominal references, never infer an antecedent.

    This deliberately conservative admission guard is not a measure of model
    extraction quality. It neither searches within named noun phrases nor treats
    broad nouns such as "objects" or "things" as pronouns. Raw model candidates
    must be retained separately by any evaluation that measures this behavior.
    """
    return _UNRESOLVED_REFERENCE.fullmatch(unicodedata.normalize("NFC", quote.strip())) is not None


def _hangul_kind(char: str) -> str:
    code = ord(char)
    if 0x1100 <= code <= 0x115F or 0xA960 <= code <= 0xA97C:
        return "L"
    if 0x1160 <= code <= 0x11A7 or 0xD7B0 <= code <= 0xD7C6:
        return "V"
    if 0x11A8 <= code <= 0x11FF or 0xD7CB <= code <= 0xD7FB:
        return "T"
    if 0xAC00 <= code <= 0xD7A3:
        return "LVT" if (code - 0xAC00) % 28 else "LV"
    return ""


def _nfc_span_index(text: str) -> tuple[str, dict[int, int]]:
    """Map only conservative normalization-unit edges to original offsets.

    This is not a full UAX29 grapheme segmenter. Marks, format/joiner characters,
    emoji modifiers, RI runs and Hangul sequences stay together. Boundaries next
    to other script letters/unclassified characters are withheld, so unsupported
    script interiors fail closed rather than acquiring guessed grapheme edges.
    Unlike the display normalizer, this never folds CRLF or other whitespace.
    """
    categories = [unicodedata.category(char) for char in text]
    hangul = [_hangul_kind(char) for char in text]
    known = []
    for index, (char, category) in enumerate(zip(text, categories, strict=True)):
        normalized_char = unicodedata.normalize("NFC", char)
        latin = len(normalized_char) == 1 and unicodedata.name(normalized_char, "").startswith("LATIN ")
        known.append(ord(char) < 128 or bool(hangul[index]) or category[0] in "MZPS" or latin)
    edges = [0]
    for index in range(1, len(text)):
        previous, current = text[index - 1], text[index]
        before, after = categories[index - 1], categories[index]
        left, right = hangul[index - 1], hangul[index]
        if previous == "\r" and current == "\n":
            continue
        if before == "Cc" or after == "Cc":
            edges.append(index)
            continue
        if (after[0] == "M" or before == "Cf" or after == "Cf"
                or 0x1F3FB <= ord(current) <= 0x1F3FF
                or (0x1F1E6 <= ord(previous) <= 0x1F1FF and 0x1F1E6 <= ord(current) <= 0x1F1FF)
                or (left == "L" and right in {"L", "V", "LV", "LVT"})
                or (left in {"LV", "V"} and right in {"V", "T"})
                or (left in {"LVT", "T"} and right == "T")
                or not known[index - 1] or not known[index]):
            continue
        edges.append(index)
    edges.append(len(text))
    chunks, mapping, offset = [], {0: 0}, 0
    for start, end in zip(edges, edges[1:]):
        chunk = unicodedata.normalize("NFC", text[start:end])
        chunks.append(chunk)
        offset += len(chunk)
        mapping[offset] = end
    normalized = "".join(chunks)
    # Never assume that independently normalized segments compose safely.
    if normalized != unicodedata.normalize("NFC", text):
        raise domain.DomainError("quote_missing_or_ambiguous")
    return normalized, mapping


class _QuoteResolver:
    """Per-input bounded cache; exact occurrences always take precedence.

    Input is already limited to 6000 code points/24 KiB and each quote to 600
    code points. Build the NFC map once, normalize each disjoint unit once, and
    scan at most the 51 supplied slot quotes. Do not enumerate substrings or
    repeatedly normalize growing prefixes. Occurrences use the existing
    non-overlapping, left-to-right convention within the chosen match set.
    """
    def __init__(self, text: str):
        self.text = text
        self.nfc_index: tuple[str, dict[int, int]] | None = None
        self.matches: dict[str, list[tuple[int, int]]] = {}

    def resolve(self, quote: str, occurrence: int | None) -> tuple[int, int]:
        if quote not in self.matches:
            matches = [(match.start(), match.end()) for match in re.finditer(re.escape(quote), self.text)]
            if not matches:
                if self.nfc_index is None:
                    self.nfc_index = _nfc_span_index(self.text)
                normalized, edges = self.nfc_index
                wanted = unicodedata.normalize("NFC", quote)
                cursor = 0
                while (found := normalized.find(wanted, cursor)) != -1:
                    finish = found + len(wanted)
                    # Ineligible partial-unit matches must not hide a later
                    # overlapping, valid span and falsely establish uniqueness.
                    cursor = found + 1
                    if found in edges and finish in edges:
                        start, end = edges[found], edges[finish]
                        if unicodedata.normalize("NFC", self.text[start:end]) == wanted:
                            matches.append((start, end))
                            cursor = finish
            self.matches[quote] = matches
        matches = self.matches[quote]
        if not matches or (len(matches) > 1 and occurrence is None):
            raise domain.DomainError("quote_missing_or_ambiguous")
        selected = occurrence if occurrence is not None else 0
        if selected >= len(matches):
            raise domain.DomainError("invalid_quote_occurrence")
        return matches[selected]


class SlotQuote(StrictModel):
    quote: BoundedText
    occurrence: Annotated[int, Field(strict=True, ge=0, le=99)] | None


class RelationQuote(SlotQuote):
    value: Literal["causal", "associative", "descriptive"]


class PolarityQuote(SlotQuote):
    value: Literal["affirmed", "negated"]


class CertaintyQuote(SlotQuote):
    value: Literal["possible", "probable", "asserted", "guaranteed"]


class GeneralizationQuote(SlotQuote):
    value: Literal["subgroup", "scoped_population", "universal"]


class SlotProposition(StrictModel):
    speaker: Literal["quoted_source", "user", "unknown"]
    speech_act: Literal["assertion", "question", "reported_assertion"]
    population: SlotQuote | None
    condition_context: SlotQuote | None
    intervention: SlotQuote | None
    comparator: SlotQuote | None
    measured_outcome: SlotQuote | None
    claimed_clinical_outcome: SlotQuote | None
    mechanism: SlotQuote | None
    safety_outcome: SlotQuote | None
    formulation: SlotQuote | None
    dose: SlotQuote | None
    route: SlotQuote | None
    co_intervention: SlotQuote | None
    relation: RelationQuote | None
    polarity: PolarityQuote | None
    certainty: CertaintyQuote | None
    generalization: GeneralizationQuote | None
    attribution_text: SlotQuote | None


class SlotExtractionCandidate(StrictModel):
    propositions: list[SlotProposition] = Field(min_length=1, max_length=3)


def expand_slot_claim(text: str, payload: dict, intent: dict | None = None) -> dict:
    """Validate literal references and preserve null slots as unknown IR fields.

    Original literal matches are preferred. Only absent literal quotes may use
    NFC-equivalent, whole-unit original spans. Exact matching is unchanged; the
    conservative boundary restrictions apply only to NFC fallback. Stored
    quotes, offsets and hashes always refer to original text. Raw candidates are
    never mutated, so evaluation can distinguish normalization from model output.
    Missing occurrence is never guessed for a repeated quote. IDs and unresolved
    field names are computed here rather than supplied by the model.
    """
    domain._bounded_text(text)
    try:
        candidate = SlotExtractionCandidate.model_validate(payload)
    except ValidationError as exc:
        raise domain.DomainError("invalid_slot_extraction") from exc

    input_hash = domain._hash(text)
    quotes = _QuoteResolver(text)
    propositions = []
    unresolved = []
    for index, slots in enumerate(candidate.propositions, start=1):
        if ((slots.attribution_text is not None and slots.speaker != "quoted_source")
                or (slots.speech_act == "reported_assertion" and slots.speaker == "user")):
            raise domain.DomainError("inconsistent_claim_attribution")
        proposition = {
            "proposition_id": f"p{index}",
            "speaker": slots.speaker,
            "speech_act": slots.speech_act,
        }
        for name in SLOT_FIELDS:
            slot = getattr(slots, name)
            if slot is None:
                # Proposition's existing defaults create full unknown wrappers.
                if name not in unresolved:
                    unresolved.append(name)
                continue
            start, end = quotes.resolve(slot.quote, slot.occurrence)
            original_quote = text[start:end]
            provenance = [{
                "kind": "input_span", "input_hash": input_hash,
                "start": start, "end": end, "quote": original_quote,
            }]
            # Validate the literal origin first: this guard must never turn an
            # invented or ambiguous quote occurrence into an admitted field.
            if name in _REFERENCE_GUARD_FIELDS and _unresolved_reference(original_quote):
                proposition[name] = {
                    "state": "ambiguous", "value": None,
                    "reason_code": "unresolved_reference", "provenance": provenance,
                }
                if name not in unresolved:
                    unresolved.append(name)
                continue
            value = getattr(slot, "value", original_quote)
            proposition[name] = {
                "state": "stated",
                "value": domain._edited_value(name, value),
                "provenance": provenance,
            }
        propositions.append(proposition)

    return domain.validate_live_claim(
        text, {"propositions": propositions, "unresolved_fields": unresolved}, intent,
    )
