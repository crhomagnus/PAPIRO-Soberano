# -*- coding: utf-8 -*-
"""PAPIRO SOBERANO core - raiz, pastas, hash e relogio.

Duas raizes: REPO (codigo e ativos versionados: fontes, bin, modelos, receitas) e ROOT (dados de
execucao: work, out, logs, kb), que vem de PAPIRO_HOME e, sem ela, e o proprio repositorio
(C:\\PAPIRO no Windows, ~/PAPIRO-Soberano no Linux). Mesmo codigo nos dois sistemas (RNF-17)."""
from __future__ import annotations
import datetime, hashlib, os, pathlib


REPO = pathlib.Path(__file__).resolve().parents[2]


def _raiz() -> pathlib.Path:
    env = os.environ.get("PAPIRO_HOME")
    return pathlib.Path(env).expanduser().resolve() if env else REPO


ROOT = _raiz()
WORK = ROOT / "work"
OUT = ROOT / "out"
LOGS = ROOT / "logs"
KB = ROOT / "kb"
FONTS = REPO / "fonts"
MODELS = REPO / "models"
RECIPES = REPO / "recipes"
BIN = REPO / "bin"

for _d in (WORK, OUT, LOGS, KB):
    _d.mkdir(parents=True, exist_ok=True)


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")
