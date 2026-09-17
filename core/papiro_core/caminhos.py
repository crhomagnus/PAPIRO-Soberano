# -*- coding: utf-8 -*-
"""Confinamento de caminhos PRD §8.1: entradas so dentro da raiz ou de pastas liberadas;
escrita so em work/ e out/; saida nunca sobrescreve arquivo existente."""
from __future__ import annotations
import pathlib, re, unicodedata
from . import REPO, ROOT, WORK, OUT
from . import config
from .erros import PapiroErro


def _dentro(p: pathlib.Path, base: pathlib.Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


def raizes_entrada() -> list[pathlib.Path]:
    return list(dict.fromkeys([ROOT.resolve(), REPO.resolve(), *config.pastas_liberadas()]))


def validar_entrada(caminho: str) -> pathlib.Path:
    if not caminho or not str(caminho).strip():
        raise PapiroErro("E_ENTRADA", "caminho de entrada vazio")
    p = pathlib.Path(caminho).expanduser().resolve()
    if not any(_dentro(p, r) for r in raizes_entrada()):
        raise PapiroErro("E_ENTRADA", "caminho fora da raiz do PAPIRO e das pastas liberadas")
    if not p.is_file():
        raise PapiroErro("E_ENTRADA", "arquivo de entrada nao existe")
    return p


def validar_out_dir(out_dir: str) -> pathlib.Path:
    if not out_dir or not str(out_dir).strip():
        raise PapiroErro("E_ENTRADA", "out_dir e obrigatorio")
    o = pathlib.Path(out_dir).expanduser().resolve()
    if not (_dentro(o, WORK.resolve()) or _dentro(o, OUT.resolve())):
        raise PapiroErro("E_POLITICA", "out_dir deve ficar dentro de work/ ou out/ do PAPIRO")
    o.mkdir(parents=True, exist_ok=True)
    return o


def nome_seguro(nome: str, padrao: str = "arquivo") -> str:
    """Basename sem diretorios, sem '..', sem caracteres de controle (anexos e nomes vindos de PDF)."""
    n = unicodedata.normalize("NFC", str(nome or "")).replace("\\", "/").split("/")[-1]
    n = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "_", n).strip().strip(".")
    return n or padrao


def saida_livre(o: pathlib.Path, nome: str, protegidos: list[pathlib.Path] | None = None) -> pathlib.Path:
    """Caminho de saida em `o` que nao existe e nao coincide com nenhuma entrada."""
    nome = nome_seguro(nome, "saida.pdf")
    alvo = (o / nome).resolve()
    stem, suf = pathlib.Path(nome).stem, pathlib.Path(nome).suffix
    prot = {p.resolve() for p in (protegidos or [])}
    i = 1
    while alvo.exists() or alvo in prot:
        alvo = (o / f"{stem}-{i}{suf}").resolve()
        i += 1
    return alvo
