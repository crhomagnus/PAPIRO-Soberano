# -*- coding: utf-8 -*-
"""Launcher MCP papiro (opencode local + claude stdio)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "core"))
from papiro_core.mcp_server import main
main()
