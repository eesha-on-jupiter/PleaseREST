"""
Tests for resolve_refs() and simplify_schema() in pr-api-extractor/server.py.
"""
import pytest
import server


# ── resolve_refs ───────────────────────────────────────────────────────────────

def test_resolve_refs_flat_dict_passthrough():
    obj = {"type": "string"}
    assert server.resolve_refs(obj, {}) == {"type": "string"}


def test_resolve_refs_resolves_local_ref():
    root = {
        "components": {
            "schemas": {
                "Board": {"type": "object", "properties": {"id": {"type": "string"}}}
            }
        }
    }
    obj = {"$ref": "#/components/schemas/Board"}
    result = server.resolve_refs(obj, root)
    assert result["type"] == "object"
    assert "id" in result["properties"]


def test_resolve_refs_nested_ref():
    root = {
        "components": {
            "schemas": {
                "Item":  {"type": "object", "properties": {"name": {"type": "string"}}},
                "Outer": {"properties": {"item": {"$ref": "#/components/schemas/Item"}}}
            }
        }
    }
    obj = {"$ref": "#/components/schemas/Outer"}
    result = server.resolve_refs(obj, root)
    assert result["properties"]["item"]["properties"]["name"]["type"] == "string"


def test_resolve_refs_circular_returns_placeholder():
    root = {
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "child": {"$ref": "#/components/schemas/Node"}
                    }
                }
            }
        }
    }
    obj = {"$ref": "#/components/schemas/Node"}
    result = server.resolve_refs(obj, root)
    # Should not raise; circular ref placeholder present somewhere in tree
    child = result["properties"]["child"]
    assert "circular ref" in child.get("description", "")


def test_resolve_refs_list_of_refs():
    root = {
        "components": {"schemas": {"Tag": {"type": "string"}}}
    }
    obj = [{"$ref": "#/components/schemas/Tag"}, {"type": "integer"}]
    result = server.resolve_refs(obj, root)
    assert result[0] == {"type": "string"}
    assert result[1] == {"type": "integer"}


def test_resolve_refs_missing_ref_returns_empty():
    root = {}
    obj = {"$ref": "#/components/schemas/Missing"}
    result = server.resolve_refs(obj, root)
    assert result == {}


def test_resolve_refs_primitive_passthrough():
    assert server.resolve_refs("hello", {}) == "hello"
    assert server.resolve_refs(42, {}) == 42
    assert server.resolve_refs(None, {}) is None


# ── simplify_schema ────────────────────────────────────────────────────────────

def test_simplify_schema_none_returns_none():
    assert server.simplify_schema(None) is None


def test_simplify_schema_empty_dict_returns_type_object():
    result = server.simplify_schema({})
    assert result == {"type": "object"}


def test_simplify_schema_flat_properties():
    schema = {
        "type": "object",
        "properties": {
            "id":    {"type": "string"},
            "count": {"type": "integer"}
        }
    }
    result = server.simplify_schema(schema)
    assert result == {"id": "string", "count": "integer"}


def test_simplify_schema_oneof_returns_ambiguous():
    schema = {
        "oneOf": [
            {"type": "string"},
            {"type": "integer"}
        ]
    }
    result = server.simplify_schema(schema)
    assert result["__ambiguous__"] == "oneOf"
    assert len(result["variants"]) == 2


def test_simplify_schema_anyof_returns_ambiguous():
    schema = {"anyOf": [{"type": "string"}, {"type": "boolean"}]}
    result = server.simplify_schema(schema)
    assert result["__ambiguous__"] == "anyOf"


def test_simplify_schema_array_type():
    schema = {"type": "array", "items": {"type": "string"}}
    result = server.simplify_schema(schema)
    assert "__array__" in result
    assert result["__array__"] == {"type": "string"}


def test_simplify_schema_ref_in_property():
    schema = {
        "type": "object",
        "properties": {
            "board": {"$ref": "#/components/schemas/Board"},
            "name":  {"type": "string"}
        }
    }
    result = server.simplify_schema(schema)
    assert result["board"] == "#/components/schemas/Board"
    assert result["name"] == "string"
