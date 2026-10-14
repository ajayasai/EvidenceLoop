"""Bounded projection of validation schemas for Gemini's request schema.

This deliberately removes some constraints from the wire schema. Callers must
still validate every response against the original, unprojected schema.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote


MAX_SCHEMA_DEPTH = 64
MAX_EXPANDED_NODES = 20_000
MAX_EXPANDED_BYTES = 64 * 1024

_OMITTED = {"minLength", "maxLength", "pattern", "minItems", "maxItems", "minimum", "maximum"}
_SCHEMA_MAPS = {"properties", "patternProperties", "dependentSchemas", "definitions"}
_SCHEMA_ARRAYS = {"allOf", "anyOf", "oneOf", "prefixItems"}
_SCHEMA_VALUES = {
    "additionalProperties", "unevaluatedProperties", "contains", "not", "if", "then", "else",
    "propertyNames", "unevaluatedItems", "additionalItems", "contentSchema",
}


def project_gemini_schema(schema: dict[str, Any] | bool) -> dict[str, Any] | bool:
    """Inline local JSON Pointers and omit only the known wire constraints.

    Schema-bearing keywords are traversed explicitly so property names and
    literal values (including enum/const objects) retain their meaning. Invalid
    references, cycles, non-JSON values and oversized expansion fail closed.
    """
    nodes = string_bytes = 0

    def account(value: Any, depth: int) -> None:
        nonlocal nodes, string_bytes
        nodes += 1
        if depth > MAX_SCHEMA_DEPTH or nodes > MAX_EXPANDED_NODES:
            raise ValueError("gemini_schema_expansion_limit")
        if isinstance(value, str):
            if len(value) > MAX_EXPANDED_BYTES:
                raise ValueError("gemini_schema_expansion_limit")
            string_bytes += len(value.encode("utf-8"))
            if string_bytes > MAX_EXPANDED_BYTES:
                raise ValueError("gemini_schema_expansion_limit")

    def literal(value: Any, depth: int) -> Any:
        account(value, depth)
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError("gemini_schema_invalid")
                account(key, depth + 1)
                result[key] = literal(child, depth + 1)
            return result
        if isinstance(value, list):
            return [literal(child, depth + 1) for child in value]
        if value is None or type(value) in {str, bool, int, float}:
            return value
        raise ValueError("gemini_schema_invalid")

    def resolve(reference: Any) -> tuple[tuple[str, ...], dict | bool]:
        if not isinstance(reference, str) or not reference.startswith("#"):
            raise ValueError("gemini_schema_reference_invalid")
        fragment = reference[1:]
        if re.search(r"%(?![0-9a-fA-F]{2})", fragment):
            raise ValueError("gemini_schema_reference_invalid")
        fragment = unquote(fragment, errors="strict")
        if fragment and not fragment.startswith("/"):
            raise ValueError("gemini_schema_reference_invalid")
        tokens = fragment[1:].split("/") if fragment else []
        if any(re.search(r"~(?![01])", token) for token in tokens):
            raise ValueError("gemini_schema_reference_invalid")
        path = tuple(token.replace("~1", "/").replace("~0", "~") for token in tokens)
        target = schema
        for token in path:
            if isinstance(target, dict) and token in target:
                target = target[token]
            elif isinstance(target, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
                if len(token) > 10 or int(token) >= len(target):
                    raise ValueError("gemini_schema_reference_invalid")
                target = target[int(token)]
            else:
                raise ValueError("gemini_schema_reference_invalid")
        if not isinstance(target, (dict, bool)):
            raise ValueError("gemini_schema_reference_invalid")
        return path, target

    def project(value: Any, depth: int, active: frozenset[tuple[str, ...]]) -> Any:
        account(value, depth)
        if isinstance(value, bool):
            return value
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise ValueError("gemini_schema_invalid")
        if "$dynamicRef" in value or "$id" in value:
            raise ValueError("gemini_schema_reference_invalid")
        expanded = None
        has_reference = "$ref" in value
        if has_reference:
            account(value["$ref"], depth + 1)
            path, target = resolve(value["$ref"])
            if path in active:
                raise ValueError("gemini_schema_reference_cycle")
            expanded = project(target, depth + 1, active | {path})
        result = {}
        for key, child in value.items():
            if key == "$ref" or key in _OMITTED:
                continue
            if key == "$defs":
                # Also validate unused definitions before discarding them.
                if not isinstance(child, dict):
                    raise ValueError("gemini_schema_invalid")
                for definition in child.values():
                    project(definition, depth + 1, active)
                continue
            account(key, depth + 1)
            if key in _SCHEMA_MAPS or key == "dependencies":
                if not isinstance(child, dict):
                    raise ValueError("gemini_schema_invalid")
                account(child, depth + 1)
                entries = {}
                for name, entry in child.items():
                    if not isinstance(name, str):
                        raise ValueError("gemini_schema_invalid")
                    account(name, depth + 2)
                    entries[name] = (literal(entry, depth + 2)
                        if key == "dependencies" and isinstance(entry, list)
                        else project(entry, depth + 2, active))
                result[key] = entries
            elif key in _SCHEMA_ARRAYS or (key == "items" and isinstance(child, list)):
                if not isinstance(child, list):
                    raise ValueError("gemini_schema_invalid")
                account(child, depth + 1)
                result[key] = [project(entry, depth + 2, active) for entry in child]
            elif key in _SCHEMA_VALUES or key == "items":
                result[key] = project(child, depth + 1, active)
            else:
                result[key] = literal(child, depth + 1)
        if not has_reference:
            return result
        # $ref siblings constrain the target too; merging dictionaries can
        # silently replace a target's type, properties or required fields.
        return {"allOf": [expanded, result]} if result else expanded

    try:
        projected = project(schema, 0, frozenset())
        # Reference siblings synthesize allOf containers; check the actual
        # output too, since those containers add depth beyond the input walk.
        pending = [(projected, 0)]
        expanded_nodes = 0
        while pending:
            value, depth = pending.pop()
            expanded_nodes += 1
            if depth > MAX_SCHEMA_DEPTH or expanded_nodes > MAX_EXPANDED_NODES:
                raise ValueError("gemini_schema_expansion_limit")
            if isinstance(value, dict):
                for key, child in value.items():
                    pending.extend(((key, depth + 1), (child, depth + 1)))
            elif isinstance(value, list):
                pending.extend((child, depth + 1) for child in value)
        encoded = json.dumps(projected, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
    except (RecursionError, UnicodeError, OverflowError):
        raise ValueError("gemini_schema_invalid") from None
    if len(encoded) > MAX_EXPANDED_BYTES:
        raise ValueError("gemini_schema_expansion_limit")
    return projected
