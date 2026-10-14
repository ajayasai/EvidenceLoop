from copy import deepcopy

from jsonschema import Draft202012Validator, ValidationError
import pytest

from app.gemini_schema import project_gemini_schema


def test_projection_inlines_reused_refs_without_mutation_and_retains_local_bounds():
    schema = {
        "$defs": {"name": {"type": "string", "minLength": 2, "maxLength": 4, "pattern": "^[A-Z]+$"}},
        "type": "object", "additionalProperties": False,
        "properties": {
            "names": {"type": "array", "items": {"$ref": "#/$defs/name"}, "minItems": 1, "maxItems": 2},
            "alias": {"$ref": "#/$defs/name"},
            "count": {"type": "integer", "minimum": 1, "maximum": 2},
        },
        "required": ["names", "alias", "count"],
    }
    original = deepcopy(schema)
    projected = project_gemini_schema(schema)
    assert projected == {
        "type": "object", "additionalProperties": False,
        "properties": {"names": {"type": "array", "items": {"type": "string"}},
                       "alias": {"type": "string"}, "count": {"type": "integer"}},
        "required": ["names", "alias", "count"],
    }
    assert schema == original
    valid = {"names": ["AB"], "alias": "CD", "count": 1}
    Draft202012Validator(schema).validate(valid)
    for invalid in (valid | {"names": []}, valid | {"alias": "x"}, valid | {"count": 3}):
        Draft202012Validator(projected).validate(invalid)
        with pytest.raises(ValidationError):
            Draft202012Validator(schema).validate(invalid)
    projected["properties"]["alias"]["type"] = "number"
    assert projected["properties"]["names"]["items"] == {"type": "string"}
    assert schema == original


def test_keyword_shaped_property_names_and_opaque_literals_are_preserved():
    literal = {"$defs": {"x": {"$ref": "https://example.invalid/private"}},
               "minimum": 7, "pattern": "not a schema"}
    schema = {"type": "object", "properties": {
        "$defs": {"enum": [literal]}, "minLength": {"const": literal},
        "$ref": {"type": "string", "minLength": 1},
    }, "default": literal, "examples": [literal], "x-extension": literal}
    original = deepcopy(schema)
    projected = project_gemini_schema(schema)
    expected = deepcopy(schema)
    del expected["properties"]["$ref"]["minLength"]
    assert projected == expected and schema == original
    projected["properties"]["$defs"]["enum"][0]["minimum"] = 99
    assert schema == original


@pytest.mark.parametrize("reference", ["#/$defs/a~1b~0c", "#/$defs/a%7E1b%7E0c"])
def test_json_pointer_escaped_slash_tilde_and_percent_encoding(reference):
    schema = {"$defs": {"a/b~c": {"type": "string", "maxLength": 3}}, "$ref": reference}
    assert project_gemini_schema(schema) == {"type": "string"}


def test_json_pointer_escape_order_and_list_target():
    schema = {"$defs": {"~1": {"type": "boolean"}}, "$ref": "#/$defs/~01"}
    assert project_gemini_schema(schema) == {"type": "boolean"}
    assert project_gemini_schema({"allOf": [{"type": "integer"}], "$ref": "#/allOf/0"}) == {
        "allOf": [{"type": "integer"}, {"allOf": [{"type": "integer"}]}]}


@pytest.mark.parametrize("reference", ["https://example.invalid/schema", "other.json#/$defs/x",
    "#/$defs/missing", "#anchor", "#/$defs/~2", "#/%GG", "#/$defs/x/type"])
def test_external_unresolved_or_invalid_references_fail_closed(reference):
    with pytest.raises(ValueError):
        project_gemini_schema({"$defs": {"x": {"type": "string"}}, "$ref": reference})


@pytest.mark.parametrize("schema", [
    {"$ref": "#"},
    {"$defs": {"a": {"$ref": "#/$defs/b"}, "b": {"$ref": "#/$defs/a"}}, "$ref": "#/$defs/a"},
    {"$defs": {"unused": {"$ref": "#/$defs/unused"}}, "type": "string"},
])
def test_cyclic_references_fail_closed(schema):
    with pytest.raises(ValueError, match="gemini_schema_reference_cycle"):
        project_gemini_schema(schema)


def test_reference_siblings_retain_conjunction_instead_of_overwriting_target():
    schema = {"$defs": {"base": {"type": "string"}}, "$ref": "#/$defs/base", "type": "integer"}
    projected = project_gemini_schema(schema)
    assert projected == {"allOf": [{"type": "string"}, {"type": "integer"}]}
    for value in (1, "one"):
        assert not Draft202012Validator(projected).is_valid(value)


def test_generated_reference_sibling_wrappers_obey_actual_output_depth(monkeypatch):
    monkeypatch.setattr("app.gemini_schema.MAX_SCHEMA_DEPTH", 8)
    definitions = {"d0": {"type": "string"}}
    for index in range(1, 5):
        definitions[f"d{index}"] = {"$ref": f"#/$defs/d{index - 1}", "description": "x"}
    # Three generated allOf wrappers fit; four reach output depth nine even
    # though the reference-expansion input walk remains below depth eight.
    within_limit = {"$defs": {key: value for key, value in definitions.items() if key != "d4"},
                    "$ref": "#/$defs/d3"}
    Draft202012Validator(project_gemini_schema(within_limit)).validate("example")
    with pytest.raises(ValueError, match="gemini_schema_expansion_limit"):
        project_gemini_schema({"$defs": definitions, "$ref": "#/$defs/d4"})


@pytest.mark.parametrize("keyword", ["items", "additionalProperties", "unevaluatedProperties", "contains",
    "not", "if", "then", "else", "propertyNames", "unevaluatedItems", "additionalItems", "contentSchema"])
def test_single_schema_keywords_are_projected(keyword):
    assert project_gemini_schema({keyword: {"type": "integer", "minimum": 1}}) == {keyword: {"type": "integer"}}


@pytest.mark.parametrize("keyword", ["allOf", "anyOf", "oneOf", "prefixItems", "items"])
def test_schema_array_keywords_are_projected(keyword):
    assert project_gemini_schema({keyword: [{"type": "integer", "maximum": 2}, False]}) == {
        keyword: [{"type": "integer"}, False]}


def test_schema_maps_and_legacy_dependencies_preserve_names():
    for keyword in ("properties", "patternProperties", "dependentSchemas", "definitions", "dependencies"):
        assert project_gemini_schema({keyword: {"minimum": {"type": "number", "maximum": 2}}}) == {
            keyword: {"minimum": {"type": "number"}}}
    assert project_gemini_schema({"dependencies": {"x": ["minimum", "$defs"]}}) == {
        "dependencies": {"x": ["minimum", "$defs"]}}


def test_expansion_depth_node_and_byte_limits_are_enforced(monkeypatch):
    deep = {"type": "string"}
    for _ in range(66):
        deep = {"items": deep}
    with pytest.raises(ValueError, match="expansion_limit"):
        project_gemini_schema(deep)
    monkeypatch.setattr("app.gemini_schema.MAX_EXPANDED_NODES", 40)
    schema = {"$defs": {"x": {"enum": ["A", "B", "C"]}},
              "allOf": [{"$ref": "#/$defs/x"} for _ in range(20)]}
    with pytest.raises(ValueError, match="expansion_limit"):
        project_gemini_schema(schema)
    monkeypatch.setattr("app.gemini_schema.MAX_EXPANDED_NODES", 20_000)
    monkeypatch.setattr("app.gemini_schema.MAX_EXPANDED_BYTES", 80)
    with pytest.raises(ValueError, match="expansion_limit"):
        project_gemini_schema({"$defs": {"x": {"enum": ["a" * 25]}},
                               "allOf": [{"$ref": "#/$defs/x"} for _ in range(4)]})
    # JSON escaping/punctuation is included in the final byte bound too.
    with pytest.raises(ValueError, match="expansion_limit"):
        project_gemini_schema({"enum": ["\x00" * 20]})


@pytest.mark.parametrize("schema", [None, [], {"enum": [float("nan")]}, {"enum": [object()]},
    {"properties": {1: {}}}, {"$dynamicRef": "#"}, {"$id": "https://example.invalid/schema"}])
def test_non_json_and_unsupported_schema_values_fail_closed(schema):
    with pytest.raises(ValueError):
        project_gemini_schema(schema)
