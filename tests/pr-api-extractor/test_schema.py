"""
Tests for extract_params() and the body/response schema helpers in pr-api-extractor/server.py.
"""
import server


# ── extract_params ─────────────────────────────────────────────────────────────

def test_extract_params_empty_list():
    path, query = server.extract_params([], {})
    assert path == []
    assert query == []


def test_extract_params_path_param():
    params = [{"name": "board_id", "in": "path", "schema": {"type": "string"}}]
    path, query = server.extract_params(params, {})
    assert len(path) == 1
    assert path[0]["name"] == "board_id"
    assert path[0]["required"] is True  # path params are always required


def test_extract_params_query_param():
    params = [{"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}}]
    path, query = server.extract_params(params, {})
    assert len(query) == 1
    assert query[0]["name"] == "limit"
    assert query[0]["type"] == "integer"
    assert query[0]["required"] is False


def test_extract_params_mixed():
    params = [
        {"name": "board_id", "in": "path",  "schema": {"type": "string"}},
        {"name": "fields",   "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "cursor",   "in": "query", "required": False, "schema": {"type": "string"}},
    ]
    path, query = server.extract_params(params, {})
    assert len(path) == 1
    assert len(query) == 2


def test_extract_params_resolves_ref():
    root = {
        "components": {
            "parameters": {
                "BoardId": {"name": "board_id", "in": "path", "schema": {"type": "string"}}
            }
        }
    }
    params = [{"$ref": "#/components/parameters/BoardId"}]
    path, query = server.extract_params(params, root)
    assert len(path) == 1
    assert path[0]["name"] == "board_id"


def test_extract_params_unknown_in_skipped():
    params = [{"name": "x-header", "in": "header", "schema": {"type": "string"}}]
    path, query = server.extract_params(params, {})
    # header params are not path or query — should not appear in either
    assert path == []
    assert query == []


# ── blank_entry defaults ───────────────────────────────────────────────────────

def test_blank_entry_has_required_keys():
    entry = server.blank_entry("get_board", "GetBoardComponent", "GET", "/v2/boards/{board_id}")
    for key in ("endpoint_id", "component", "method", "url_template",
                "path_params", "query_params", "headers", "body_schema",
                "response_schema", "example_request", "example_response",
                "notes", "status"):
        assert key in entry, f"blank_entry missing key: {key}"


def test_blank_entry_status_is_extracted():
    entry = server.blank_entry("get_board", "GetBoardComponent", "GET", "/v2/boards/{board_id}")
    assert entry["status"] == "EXTRACTED"


def test_blank_entry_method_uppercased():
    entry = server.blank_entry("get_board", "GetBoardComponent", "get", "/v2/boards/{board_id}")
    assert entry["method"] == "GET"


def test_blank_entry_has_auth_header():
    entry = server.blank_entry("get_board", "GetBoardComponent", "GET", "/v2/boards/{board_id}")
    assert "Authorization" in entry["headers"]
    assert "Bearer" in entry["headers"]["Authorization"]
