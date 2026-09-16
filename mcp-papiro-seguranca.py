# -*- coding: utf-8 -*-
"""Launcher MCP papiro-seguranca (isolado, so pdf-seguranca)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "core"))
from papiro_core.mcp_seguranca import main
main()
