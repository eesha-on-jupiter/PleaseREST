"""
Shared fixtures and path helpers for PleaseREST MCP tests.
Each MCP subfolder has its own conftest.py that adds the server to sys.path.
"""
from pathlib import Path

# Root of the repo: tests/../
REPO_ROOT = Path(__file__).parent.parent

# Convenience paths to each MCP server directory
MCP_ROOT         = REPO_ROOT / "please-rest" / "mcps"
ICON_GEN_DIR     = MCP_ROOT / "pr-icon-generator"
API_EXTRACTOR_DIR = MCP_ROOT / "pr-api-extractor"
API_TESTER_DIR   = MCP_ROOT / "pr-api-tester"
