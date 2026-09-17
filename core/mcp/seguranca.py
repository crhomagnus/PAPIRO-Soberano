# -*- coding: utf-8 -*-
"""Ponto de entrada do servidor MCP `papiro-seguranca` (PRD §14.1 core/mcp). Implementacao: papiro_core.mcp_seguranca."""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from papiro_core.mcp_seguranca import main  # noqa: E402

if __name__ == "__main__":
    main()
