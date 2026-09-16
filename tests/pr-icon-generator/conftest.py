"""
Load this MCP's server.py under a unique module key, then pin it as `server`.

All three MCPs ship a module literally named `server.py`. Under a single pytest
process a bare `import server` would cache whichever loads first in sys.modules and
hand the wrong module to the other two suites. Loading under a unique key and
re-pinning `server` per test keeps the three suites isolated in one run.
"""
import sys
import importlib.util
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "please-rest" / "mcps" / "pr-icon-generator"
_KEY = "server_icon_gen"

sys.path.insert(0, str(_DIR))

if _KEY not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_KEY, _DIR / "server.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_KEY] = _mod
    _spec.loader.exec_module(_mod)

_server = sys.modules[_KEY]

# pin now so this directory's test modules capture the right object at import time
sys.modules["server"] = _server


@pytest.fixture(autouse=True)
def _pin_server(request):
    # re-pin before each test so runtime patch("server.x") and the test module's
    # own `server` global both resolve to this MCP, regardless of import order
    sys.modules["server"] = _server
    if hasattr(request.module, "server"):
        request.module.server = _server
    yield
