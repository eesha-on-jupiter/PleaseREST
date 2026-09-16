"""
Tests for spec-format handling added to pr-api-extractor/server.py: securitySchemes → auth_in,
Google Discovery servicePath, Swagger 2.0, OpenAPI `examples`, server variables, non-dict
specs, body_required, external $ref, tolerant resolve_refs.
"""
import asyncio
import json

import pytest

import server


def _run(spec, components, tmp_path):
    f = tmp_path / "spec.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    out = asyncio.run(server.extract_from_openapi(str(f), components))
    body = out[: out.rfind("]") + 1]
    return json.loads(body)


BASE_OAS3 = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://{region}.api.example.com/{ver}",
                 "variables": {"region": {"default": "eu"}, "ver": {"default": "v2"}}}],
    "paths": {
        "/items": {
            "post": {
                "requestBody": {"content": {"application/json": {
                    "schema": {"type": "object", "required": ["name"],
                               "properties": {"name": {"type": "string"}, "size": {"type": "integer"}}},
                    "examples": {"basic": {"value": {"name": "n", "size": 1}}},
                }}},
                "responses": {"200": {"content": {"application/json": {
                    "schema": {"type": "object", "properties": {"id": {"type": "string"}},
                               "example": {"id": "abc"}}}}}},
            },
            "get": {"parameters": [{"name": "pageToken", "in": "query", "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "ok"}}},
        }
    },
}


# ── server variables / examples / body_required / pagination ──────────────────

def test_server_variables_substituted(tmp_path):
    entries = _run(BASE_OAS3, [{"endpoint_id": "create_item", "component": "C", "method": "POST", "path": "/items"}], tmp_path)
    assert entries[0]["base_url"] == "https://eu.api.example.com/v2"


def test_examples_plural_and_schema_example_used(tmp_path):
    entries = _run(BASE_OAS3, [{"endpoint_id": "create_item", "component": "C", "method": "POST", "path": "/items"}], tmp_path)
    e = entries[0]
    assert e["example_request"] == {"name": "n", "size": 1}
    assert e["example_response"] == {"id": "abc"}
    assert e["status"] == "EXTRACTED"


def test_body_required_recorded_and_body_schema_shape_unchanged(tmp_path):
    entries = _run(BASE_OAS3, [{"endpoint_id": "create_item", "component": "C", "method": "POST", "path": "/items"}], tmp_path)
    e = entries[0]
    assert e["body_required"] == ["name"]
    assert e["body_schema"] == {"name": "string", "size": "integer"}
    assert e["content_type"] == "application/json"


def test_pagination_detects_pageToken(tmp_path):
    entries = _run(BASE_OAS3, [{"endpoint_id": "list_items", "component": "C", "method": "GET", "path": "/items"}], tmp_path)
    assert "pageToken" in entries[0]["notes"]


def test_relative_server_url_noted(tmp_path):
    spec = dict(BASE_OAS3, servers=[{"url": "/api/v3"}])
    entries = _run(spec, [{"endpoint_id": "list_items", "component": "C", "method": "GET", "path": "/items"}], tmp_path)
    assert entries[0]["base_url"] == "/api/v3"
    assert "relative server URL" in entries[0]["notes"]


# ── securitySchemes → auth_in ─────────────────────────────────────────────────

def _with_security(schemes, security=None, op_security=None):
    spec = json.loads(json.dumps(BASE_OAS3))
    spec["components"] = {"securitySchemes": schemes}
    if security is not None:
        spec["security"] = security
    if op_security is not None:
        spec["paths"]["/items"]["get"]["security"] = op_security
    return spec


def test_auth_in_api_key_header(tmp_path):
    spec = _with_security({"ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}, [{"ApiKey": []}])
    e = _run(spec, [{"endpoint_id": "list_items", "component": "C", "method": "GET", "path": "/items"}], tmp_path)[0]
    assert e["auth_in"] == "header:X-API-Key"
    assert e["headers"] == {"X-API-Key": "{token}"}


def test_auth_in_api_key_query(tmp_path):
    spec = _with_security({"Key": {"type": "apiKey", "in": "query", "name": "key"}})
    e = _run(spec, [{"endpoint_id": "list_items", "component": "C", "method": "GET", "path": "/items"}], tmp_path)[0]
    assert e["auth_in"] == "query:key"
    assert "Authorization" not in e["headers"]


def test_auth_in_bearer_and_oauth_are_header(tmp_path):
    spec = _with_security({"B": {"type": "http", "scheme": "bearer"}}, [{"B": []}])
    e = _run(spec, [{"endpoint_id": "list_items", "component": "C", "method": "GET", "path": "/items"}], tmp_path)[0]
    assert e["auth_in"] == "header" and e["headers"] == {"Authorization": "Bearer {token}"}
    spec = _with_security({"O": {"type": "oauth2", "flows": {}}}, [{"O": ["scope"]}])
    e = _run(spec, [{"endpoint_id": "list_items", "component": "C", "method": "GET", "path": "/items"}], tmp_path)[0]
    assert e["auth_in"] == "header"


def test_operation_security_overrides_global(tmp_path):
    spec = _with_security({"B": {"type": "http", "scheme": "bearer"},
                           "K": {"type": "apiKey", "in": "header", "name": "X-Key"}},
                          [{"B": []}], op_security=[{"K": []}])
    e = _run(spec, [{"endpoint_id": "list_items", "component": "C", "method": "GET", "path": "/items"}], tmp_path)[0]
    assert e["auth_in"] == "header:X-Key"


def test_auth_in_from_spec_defaults_without_schemes():
    assert server.auth_in_from_spec({}) == "header"


# ── Google Discovery servicePath ──────────────────────────────────────────────

DRIVE = {
    "discoveryVersion": "v1", "rootUrl": "https://www.googleapis.com/", "servicePath": "drive/v3/",
    "schemas": {"File": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}},
    "resources": {"files": {"methods": {
        "get": {"path": "files/{fileId}", "httpMethod": "GET",
                "parameters": {"fileId": {"type": "string", "location": "path", "required": True}},
                "response": {"$ref": "File"}},
        "create": {"path": "files", "httpMethod": "POST", "request": {"$ref": "File"}, "response": {"$ref": "File"}},
    }}},
}
SLIDES = {"discoveryVersion": "v1", "rootUrl": "https://slides.googleapis.com/", "servicePath": "",
          "resources": {"presentations": {"methods": {"get": {"path": "v1/presentations/{presentationId}", "httpMethod": "GET"}}}}}


def test_discovery_base_url_includes_service_path(tmp_path):
    e = _run(DRIVE, [{"endpoint_id": "get_file", "component": "C", "method": "GET", "path": "/files/{fileId}"}], tmp_path)[0]
    assert e["base_url"] == "https://www.googleapis.com/drive/v3"
    assert e["status"] == "EXTRACTED"


def test_discovery_empty_service_path_is_origin(tmp_path):
    e = _run(SLIDES, [{"endpoint_id": "get_presentation", "component": "C", "method": "GET",
                       "path": "/v1/presentations/{presentationId}"}], tmp_path)[0]
    assert e["base_url"] == "https://slides.googleapis.com"


def test_discovery_body_required(tmp_path):
    e = _run(DRIVE, [{"endpoint_id": "create_file", "component": "C", "method": "POST", "path": "/files"}], tmp_path)[0]
    assert e["body_required"] == ["name"]
    assert e["body_schema"] == {"name": "string"}


# ── Swagger 2.0 ───────────────────────────────────────────────────────────────

SWAGGER2 = {
    "swagger": "2.0", "host": "petstore.swagger.io", "basePath": "/v2", "schemes": ["https", "http"],
    "securityDefinitions": {"api_key": {"type": "apiKey", "in": "header", "name": "api_key"}},
    "security": [{"api_key": []}],
    "definitions": {"Pet": {"type": "object", "required": ["name"],
                            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}},
    "paths": {"/pet": {"post": {
        "consumes": ["application/json"],
        "parameters": [{"in": "body", "name": "body", "required": True, "schema": {"$ref": "#/definitions/Pet"}}],
        "responses": {"200": {"description": "ok", "schema": {"$ref": "#/definitions/Pet"},
                              "examples": {"application/json": {"id": 1, "name": "rex"}}}},
    }}},
}


def test_swagger2_minimal(tmp_path):
    e = _run(SWAGGER2, [{"endpoint_id": "create_pet", "component": "C", "method": "POST", "path": "/pet"}], tmp_path)[0]
    assert e["base_url"] == "https://petstore.swagger.io/v2"
    assert e["body_schema"] == {"id": "integer", "name": "string"}
    assert e["body_required"] == ["name"]
    assert e["response_schema"] == {"id": "integer", "name": "string"}
    assert e["example_response"] == {"id": 1, "name": "rex"}
    assert e["auth_in"] == "header:api_key"
    assert e["status"] == "EXTRACTED"


# ── robustness ────────────────────────────────────────────────────────────────

def test_non_dict_spec_returns_clear_error(tmp_path):
    f = tmp_path / "spec.json"
    f.write_text('"<html>oops</html>"', encoding="utf-8")
    out = asyncio.run(server.extract_from_openapi(str(f), [{"endpoint_id": "x", "component": "C", "method": "GET", "path": "/x"}]))
    assert out.startswith("Restling failed") and "not a JSON/YAML object" in out


def test_resolve_refs_tolerates_list_traversal_and_escapes():
    root = {"a": [{"b": {"type": "string"}}], "x/y": {"type": "integer"}}
    assert server.resolve_refs({"$ref": "#/a/0/b"}, root) == {"type": "string"}
    assert server.resolve_refs({"$ref": "#/a/9/b"}, root) == {}
    assert server.resolve_refs({"$ref": "#/x~1y"}, root) == {"type": "integer"}


def test_external_ref_marks_write_entry_partial(tmp_path):
    spec = json.loads(json.dumps(BASE_OAS3))
    spec["paths"]["/items"]["post"]["requestBody"]["content"]["application/json"] = {
        "schema": {"$ref": "common.yaml#/Item"}}
    e = _run(spec, [{"endpoint_id": "create_item", "component": "C", "method": "POST", "path": "/items"}], tmp_path)[0]
    assert e["status"] == "PARTIAL"
    assert "external $ref" in e["notes"]


def test_all_of_merged_not_flattened_to_object():
    schema = {"allOf": [{"properties": {"id": {"type": "string"}}},
                        {"properties": {"name": {"type": "string"}}, "required": ["name"]}]}
    assert server.simplify_schema(schema) == {"id": "string", "name": "string"}
    assert server.schema_required(schema) == ["name"]


def test_append_or_write_entry_backs_up_non_list(tmp_path):
    path = tmp_path / "call-library.json"
    path.write_text('{"not": "a list"}', encoding="utf-8")
    server._append_or_write_entry({"endpoint_id": "x"}, str(path))
    assert json.loads(path.read_text()) == [{"endpoint_id": "x"}]
    assert (tmp_path / "call-library.json.bak").exists()


def test_form_content_type_noted(tmp_path):
    spec = json.loads(json.dumps(BASE_OAS3))
    spec["paths"]["/items"]["post"]["requestBody"]["content"] = {
        "multipart/form-data": {"schema": {"type": "object", "properties": {"file": {"type": "string"}}}}}
    e = _run(spec, [{"endpoint_id": "upload", "component": "C", "method": "POST", "path": "/items"}], tmp_path)[0]
    assert e["content_type"] == "multipart/form-data"
    assert "content type multipart/form-data" in e["notes"]
