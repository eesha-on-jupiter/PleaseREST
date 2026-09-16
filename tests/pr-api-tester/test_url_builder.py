"""
Tests for build_url() in pr-api-tester/server.py.
"""
import server


def test_build_url_no_params():
    url, err = server.build_url("https://api.example.com/v1/items", [], {})
    assert url == "https://api.example.com/v1/items"
    assert err == ""


def test_build_url_single_param_filled():
    params = [{"name": "board_id", "type": "string", "required": True}]
    seed = {"board_id": "abc123"}
    url, err = server.build_url("https://api.example.com/v2/boards/{board_id}", params, seed)
    assert url == "https://api.example.com/v2/boards/abc123"
    assert err == ""


def test_build_url_multiple_params_filled():
    params = [
        {"name": "org_id", "type": "string", "required": True},
        {"name": "item_id", "type": "string", "required": True},
    ]
    seed = {"org_id": "org1", "item_id": "item99"}
    url, err = server.build_url(
        "https://api.example.com/orgs/{org_id}/items/{item_id}", params, seed
    )
    assert url == "https://api.example.com/orgs/org1/items/item99"
    assert err == ""


def test_build_url_missing_seed_returns_error():
    params = [{"name": "board_id", "type": "string", "required": True}]
    url, err = server.build_url("https://api.example.com/v2/boards/{board_id}", params, {})
    assert err != ""
    assert "board_id" in err
    assert "Missing seed ID" in err


def test_build_url_extra_seed_ids_ignored():
    params = [{"name": "board_id", "type": "string", "required": True}]
    seed = {"board_id": "abc", "item_id": "xyz"}  # item_id not in template
    url, err = server.build_url("https://api.example.com/v2/boards/{board_id}", params, seed)
    assert url == "https://api.example.com/v2/boards/abc"
    assert err == ""


def test_build_url_integer_seed_id():
    params = [{"name": "page_id", "type": "integer", "required": True}]
    seed = {"page_id": 42}
    url, err = server.build_url("https://api.example.com/pages/{page_id}", params, seed)
    assert url == "https://api.example.com/pages/42"
    assert err == ""


def test_build_url_unfilled_placeholder_in_template_without_param_list():
    # Template has a placeholder but param_list is empty — unfilled placeholders
    url, err = server.build_url("https://api.example.com/boards/{board_id}", [], {})
    assert err != ""
    assert "Unfilled path params" in err
    assert "board_id" in err
