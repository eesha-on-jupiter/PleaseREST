"""
Tests for extract_from_openapi() in pr-api-extractor/server.py.
Uses inline spec dicts — no network calls.
"""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import server


# ── Inline spec helpers ────────────────────────────────────────────────────────

def _petstore_spec():
    """Minimal inline OpenAPI 3.0 spec with two endpoints."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Mini Petstore", "version": "1.0.0"},
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "parameters": [
                        {"name": "limit", "in": "query", "required": False,
                         "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "List of pets",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Pet"}
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "operationId": "createPet",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        }
                    },
                    "responses": {"201": {"description": "Created"}}
                }
            },
            "/pets/{petId}": {
                "get": {
                    "operationId": "showPetById",
                    "parameters": [
                        {"name": "petId", "in": "path", "required": True,
                         "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "A pet",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {
                        "id":   {"type": "integer"},
                        "name": {"type": "string"},
                        "tag":  {"type": "string"}
                    }
                }
            }
        }
    }


def _run_extract(spec_dict, component_list, tmp_path=None):
    """Write spec to a temp file and call extract_from_openapi."""
    import tempfile, json
    spec_text = json.dumps(spec_dict)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False, encoding="utf-8") as f:
        f.write(spec_text)
        spec_path = f.name
    out = str(tmp_path / "call-library.json") if tmp_path else None
    return asyncio.run(server.extract_from_openapi(spec_path, component_list, out))


# ── Extraction results ─────────────────────────────────────────────────────────

def test_extract_known_get_endpoint_extracted(tmp_path):
    spec = _petstore_spec()
    component_list = [
        {"endpoint_id": "list_pets", "component": "ListPetsComponent",
         "method": "GET", "path": "/pets"}
    ]
    raw = _run_extract(spec, component_list, tmp_path)
    entries = json.loads(raw.split("\n\nRestling")[0])
    assert len(entries) == 1
    assert entries[0]["status"] == "EXTRACTED"
    assert entries[0]["endpoint_id"] == "list_pets"


def test_extract_query_params_populated(tmp_path):
    spec = _petstore_spec()
    component_list = [
        {"endpoint_id": "list_pets", "component": "ListPetsComponent",
         "method": "GET", "path": "/pets"}
    ]
    raw = _run_extract(spec, component_list, tmp_path)
    entries = json.loads(raw.split("\n\nRestling")[0])
    query_names = [p["name"] for p in entries[0]["query_params"]]
    assert "limit" in query_names


def test_extract_path_params_populated(tmp_path):
    spec = _petstore_spec()
    component_list = [
        {"endpoint_id": "get_pet", "component": "GetPetComponent",
         "method": "GET", "path": "/pets/{petId}"}
    ]
    raw = _run_extract(spec, component_list, tmp_path)
    entries = json.loads(raw.split("\n\nRestling")[0])
    path_names = [p["name"] for p in entries[0]["path_params"]]
    assert "petId" in path_names


def test_extract_response_schema_resolved(tmp_path):
    spec = _petstore_spec()
    component_list = [
        {"endpoint_id": "get_pet", "component": "GetPetComponent",
         "method": "GET", "path": "/pets/{petId}"}
    ]
    raw = _run_extract(spec, component_list, tmp_path)
    entries = json.loads(raw.split("\n\nRestling")[0])
    rs = entries[0]["response_schema"]
    assert rs is not None
    assert "id" in rs or "name" in rs  # Pet schema fields present


def test_extract_missing_path_marked_missing(tmp_path):
    spec = _petstore_spec()
    component_list = [
        {"endpoint_id": "delete_pet", "component": "DeletePetComponent",
         "method": "DELETE", "path": "/pets/{petId}/nonexistent"}
    ]
    raw = _run_extract(spec, component_list, tmp_path)
    entries = json.loads(raw.split("\n\nRestling")[0])
    assert entries[0]["status"] == "MISSING"


def test_extract_wrong_method_marked_missing(tmp_path):
    spec = _petstore_spec()
    component_list = [
        {"endpoint_id": "put_pets", "component": "PutPetsComponent",
         "method": "PUT", "path": "/pets"}
    ]
    raw = _run_extract(spec, component_list, tmp_path)
    entries = json.loads(raw.split("\n\nRestling")[0])
    assert entries[0]["status"] == "MISSING"


def test_extract_writes_output_file(tmp_path):
    spec = _petstore_spec()
    component_list = [
        {"endpoint_id": "list_pets", "component": "ListPetsComponent",
         "method": "GET", "path": "/pets"}
    ]
    out = tmp_path / "call-library.json"
    _run_extract(spec, component_list, tmp_path)
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 1
    assert data[0]["endpoint_id"] == "list_pets"


def test_extract_yaml_spec(tmp_path):
    import tempfile
    import yaml as _yaml
    spec = _petstore_spec()
    yaml_text = _yaml.dump(spec)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                     delete=False, encoding="utf-8") as f:
        f.write(yaml_text)
        spec_path = f.name

    component_list = [
        {"endpoint_id": "list_pets", "component": "ListPetsComponent",
         "method": "GET", "path": "/pets"}
    ]
    result = asyncio.run(server.extract_from_openapi(spec_path, component_list))
    entries = json.loads(result.split("\n\nRestling")[0])
    assert entries[0]["status"] == "EXTRACTED"


def test_extract_pagination_noted(tmp_path):
    """Query param named 'cursor' should trigger a pagination note."""
    spec = _petstore_spec()
    # Add cursor param to /pets
    spec["paths"]["/pets"]["get"]["parameters"].append(
        {"name": "cursor", "in": "query", "required": False, "schema": {"type": "string"}}
    )
    component_list = [
        {"endpoint_id": "list_pets", "component": "ListPetsComponent",
         "method": "GET", "path": "/pets"}
    ]
    raw = _run_extract(spec, component_list, tmp_path)
    entries = json.loads(raw.split("\n\nRestling")[0])
    assert "cursor" in entries[0]["notes"] or "Paginated" in entries[0]["notes"]
