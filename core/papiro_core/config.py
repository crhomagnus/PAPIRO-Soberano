# -*- coding: utf-8 -*-
"""Leitura de papiro.toml (perfil, pastas liberadas, limiares de QA)."""
from __future__ import annotations
import os, pathlib, tomllib
from functools import lru_cache
from . import REPO, ROOT

PADRAO = {
    "perfil": {"ativo": "P0"},
    "caminhos": {"liberadas": []},
    "qa": {
        "limiar_ssim": 0.95,
        "margem_minima_pt": 8.5,
        "ssim_otimizar": {"tela": 0.85, "email": 0.90, "impressao": 0.95, "arquivo": 0.99},
    },
    "jobs": {"manter_work": False, "timeout_motor_s": 600},
}


def _mesclar(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        out[k] = _mesclar(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@lru_cache(maxsize=1)
def carregar() -> dict:
    arq = ROOT / "papiro.toml"
    if not arq.exists():
        arq = REPO / "papiro.toml"
    dados = {}
    if arq.exists():
        with open(arq, "rb") as f:
            dados = tomllib.load(f)
    return _mesclar(PADRAO, dados)


def perfil() -> str:
    return os.environ.get("PAPIRO_PERFIL") or carregar()["perfil"].get("ativo", "P0")


def pastas_liberadas() -> list[pathlib.Path]:
    nomes = list(carregar()["caminhos"].get("liberadas", []))
    nomes += [x for x in os.environ.get("PAPIRO_PASTAS_LIBERADAS", "").split(os.pathsep) if x]
    return [pathlib.Path(n).expanduser().resolve() for n in nomes]


def qa(chave: str):
    return carregar()["qa"][chave]


def jobs(chave: str):
    return carregar()["jobs"][chave]
