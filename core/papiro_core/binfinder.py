# -*- coding: utf-8 -*-
"""Resolvedor de binarios e execucao com timeout (ADR-03).

Ordem de busca: bin/ portatil do projeto (versoes travadas em engines.lock.toml) -> PATH ->
locais padrao do Windows. Linux: bin/linux-x86_64/**; Windows: bin/*.exe."""
from __future__ import annotations
import os, pathlib, platform, shutil, subprocess, sys
from functools import lru_cache
from . import BIN, MODELS
from .erros import PapiroErro

PAPIRO_BIN = BIN
WINDOWS = sys.platform.startswith("win")
PLAT_DIR = PAPIRO_BIN / f"{'windows' if WINDOWS else sys.platform}-{platform.machine().lower().replace('amd64', 'x86_64')}"

KNOWN_WINDOWS = {
    "gswin64c": [r"C:\Program Files\gs\gs10.07.1\bin\gswin64c.exe"],
    "qpdf": [r"C:\Program Files\qpdf 12.4.1\bin\qpdf.exe"],
    "tesseract": [r"C:\Program Files\Tesseract-OCR\tesseract.exe"],
    "soffice": [r"C:\Program Files\LibreOffice\program\soffice.com",
                r"C:\Program Files\LibreOffice\program\soffice.exe"],
    "verapdf": [r"C:\Program Files\veraPDF\verapdf.bat"],
}

TESSDATA = MODELS / "tessdata"


def _no_projeto(nome: str) -> str | None:
    if WINDOWS:
        for cand in (PAPIRO_BIN / f"{nome}.exe", PAPIRO_BIN / f"{nome}.bat"):
            if cand.is_file():
                return str(cand)
        return None
    if not PLAT_DIR.is_dir():
        return None
    for cand in sorted(PLAT_DIR.glob(f"**/{nome}")):
        if "_downloads" in cand.parts:
            continue
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


@lru_cache(maxsize=None)
def qual(nome: str) -> str | None:
    p = _no_projeto(nome) or shutil.which(nome)
    if p:
        return p
    if WINDOWS:
        for cand in KNOWN_WINDOWS.get(nome, []):
            if pathlib.Path(cand).exists():
                return cand
    return None


def ghostscript() -> str | None:
    return qual("gswin64c") if WINDOWS else qual("gs")


def env_extra() -> dict:
    """Variaveis para processos filhos: bin do projeto no PATH; tessdata do projeto quando completo."""
    env: dict[str, str] = {}
    dirs = []
    for nome in ("qpdf", "gs", "gswin64c", "typst", "pdfcpu", "verapdf", "tesseract"):
        p = qual(nome)
        if p:
            dirs.append(str(pathlib.Path(p).parent))
    env["PATH"] = os.pathsep.join(dict.fromkeys(dirs)) + os.pathsep + os.environ.get("PATH", "")
    if WINDOWS and (TESSDATA / "por.traineddata").exists():
        env["TESSDATA_PREFIX"] = str(TESSDATA)
    return env


def rodar(cmd: list[str], timeout: float = 600, checar: bool = True, cwd: str | None = None,
          entrada: bytes | None = None) -> subprocess.CompletedProcess:
    """Executa motor externo com timeout e stderr capturado. Converte falhas em PapiroErro."""
    env = dict(os.environ)
    env.update(env_extra())
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, cwd=cwd, input=entrada)
    except subprocess.TimeoutExpired:
        raise PapiroErro("E_TEMPO", f"{pathlib.Path(cmd[0]).name} excedeu {timeout:.0f}s")
    except FileNotFoundError:
        raise PapiroErro("E_SEM_SUPORTE", f"{pathlib.Path(cmd[0]).name} nao encontrado")
    if checar and r.returncode != 0:
        msg = (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        raise PapiroErro("E_MOTOR", f"{pathlib.Path(cmd[0]).name} saiu com {r.returncode}: {(msg[-1] if msg else '')[:300]}")
    return r
