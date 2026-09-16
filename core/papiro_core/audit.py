# -*- coding: utf-8 -*-
"""Auditoria JSONL + envelope padrao PRD §8.1/§8.2."""
from __future__ import annotations
import json, time, uuid, pathlib
from typing import Any
from . import LOGS, sha256_file, utcnow_iso

AUDIT = LOGS / "audit.jsonl"

ERRORS = {
    "E_ENTRADA": "Arquivo ausente ou caminho fora da raiz",
    "E_SENHA": "PDF criptografado sem senha informada",
    "E_CORROMPIDO": "Nenhum parser abriu o arquivo",
    "E_MOTOR": "Motor falhou",
    "E_TEMPO": "Timeout",
    "E_CONFORMIDADE": "Validador reprovou",
    "E_POLITICA": "Hook ou regra bloqueou",
    "E_SEM_SUPORTE": "Recurso impossivel no motor",
}

def audit(entry: dict) -> str:
    aid = uuid.uuid4().hex[:12]
    entry = {"audit_id": aid, "ts": utcnow_iso(), **entry}
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return aid

def envelope(job_id: str, outputs: list[dict], engine: dict, seconds: float,
             warnings: list[str] | None = None, qa: dict | None = None,
             error: dict | None = None) -> dict:
    return {
        "ok": error is None,
        "job_id": job_id,
        "outputs": outputs,
        "engine": engine,
        "metrics": {"seconds": round(seconds, 3)},
        "warnings": warnings or [],
        "qa": qa or {},
        "audit_id": audit({"job_id": job_id, "engine": engine, "outputs": outputs,
                           "warnings": warnings or [], "error": error}),
        **({"error": error} if error else {}),
    }

def err(code: str, message: str = "") -> dict:
    base = ERRORS.get(code, message)
    return {"code": code, "message": message or base}

def out_entry(path: pathlib.Path, pages: int = 0) -> dict:
    return {"path": str(path), "sha256": sha256_file(path),
            "pages": pages, "bytes": path.stat().st_size}
