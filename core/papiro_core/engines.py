# -*- coding: utf-8 -*-
"""Deteccao de motores e versoes - PRD §5 + §14. Resultado em cache por processo."""
from __future__ import annotations
import importlib.metadata as md
import re, shutil, subprocess
from functools import lru_cache
from . import binfinder as BF

LIBS = ["pymupdf", "pikepdf", "pypdf", "pdfplumber", "pypdfium2", "pillow", "segno", "openpyxl",
        "pydantic", "typer", "mcp", "opencv-python-headless", "numpy", "pymupdf4llm", "markdown-it-py",
        "ocrmypdf", "pyhanko", "presidio-analyzer", "spacy", "img2pdf", "structlog", "watchdog", "fonttools"]

BINS = {  # nome logico -> (executavel, argumentos de versao)
    "ghostscript": (None, ["--version"]),
    "qpdf": ("qpdf", ["--version"]),
    "pdfcpu": ("pdfcpu", ["version"]),
    "typst": ("typst", ["--version"]),
    "tesseract": ("tesseract", ["--version"]),
    "libreoffice": ("soffice", ["--version"]),
    "poppler_pdffonts": ("pdffonts", ["-v"]),
    "verapdf": ("verapdf", ["--version"]),
    "java": ("java", ["-version"]),
    "ollama": ("ollama", ["--version"]),
}


def _primeira_linha(exe: str, args: list[str]) -> str | None:
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=20)
        linhas = [x for x in (r.stdout + r.stderr).splitlines() if x.strip()]
        return linhas[0].strip()[:120] if linhas else exe
    except Exception:
        return None


@lru_cache(maxsize=None)
def versao_bin(nome: str) -> str | None:
    exe_nome, args = BINS[nome]
    exe = BF.ghostscript() if nome == "ghostscript" else BF.qual(exe_nome)
    if not exe:
        return None
    return _primeira_linha(exe, args)


@lru_cache(maxsize=None)
def versao_lib(pkg: str) -> str | None:
    try:
        return md.version(pkg)
    except Exception:
        return None


def versao(nome: str) -> str | None:
    """Versao de um motor por nome logico (lib ou binario)."""
    if nome in BINS:
        v = versao_bin(nome)
        m = re.search(r"\d+(\.\d+)+", v or "")
        return m.group(0) if m else v
    return versao_lib(nome)


def disponivel(nome: str) -> bool:
    return versao(nome) is not None


@lru_cache(maxsize=1)
def tesseract_idiomas() -> tuple[str, ...]:
    exe = BF.qual("tesseract")
    if not exe:
        return ()
    try:
        import os
        env = dict(os.environ); env.update(BF.env_extra())
        r = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20, env=env)
        return tuple(x.strip() for x in r.stdout.splitlines()[1:] if x.strip())
    except Exception:
        return ()


def status() -> dict:
    return {"libs": {p: versao_lib(p) for p in LIBS},
            "bins": {n: versao_bin(n) for n in BINS},
            "tesseract_idiomas": list(tesseract_idiomas()),
            "perfil": perfil_hardware()}


def perfil_hardware() -> str:
    """P1 se nvidia-smi responde; P2 se rocm-smi responde; senao P0 (so CPU)."""
    for exe, perfil in (("nvidia-smi", "P1"), ("rocm-smi", "P2")):
        if shutil.which(exe):
            try:
                subprocess.run([exe], capture_output=True, timeout=10, check=True)
                return perfil
            except Exception:
                pass
    return "P0"
