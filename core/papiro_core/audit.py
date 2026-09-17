# -*- coding: utf-8 -*-
"""Trilha de auditoria JSONL (RNF-13). PRD §12.5: so hashes e metadados tecnicos, nunca conteudo
nem caminho/nome de arquivo (nomes podem conter dado pessoal)."""
from __future__ import annotations
import json, pathlib, uuid
from . import LOGS, sha256_file, utcnow_iso
from .erros import err  # noqa: F401  (reexportado para compatibilidade)

AUDIT = LOGS / "audit.jsonl"


def registrar(entrada: dict) -> str:
    aid = uuid.uuid4().hex[:12]
    linha = {"audit_id": aid, "ts": utcnow_iso(), **entrada}
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return aid


def paginas_pdf(p: pathlib.Path) -> int:
    if p.suffix.lower() != ".pdf":
        return 0
    try:
        import fitz
        with fitz.open(p) as d:
            return d.page_count
    except Exception:
        return 0


def descrever(p: pathlib.Path) -> dict:
    """Entrada de `outputs` do envelope (§8.1)."""
    return {"path": str(p), "sha256": sha256_file(p), "pages": paginas_pdf(p), "bytes": p.stat().st_size}


def para_log(descricoes: list[dict]) -> list[dict]:
    return [{"sha256": d["sha256"], "pages": d["pages"], "bytes": d["bytes"],
             "ext": pathlib.Path(d["path"]).suffix.lower()} for d in descricoes]
