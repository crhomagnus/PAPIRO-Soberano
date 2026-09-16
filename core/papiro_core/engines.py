# -*- coding: utf-8 -*-
"""Detecta motores instalados - PRD §5 + §14. Retorna nome->versao ou None."""
from __future__ import annotations
import shutil, subprocess, importlib.metadata as md
from . import binfinder as BF

def _bin(name: str, args: list[str] | None = None) -> str | None:
    p = BF.qual(name) or shutil.which(name)
    if not p:
        return None
    try:
        r = subprocess.run([p, *(args or ["--version"])], capture_output=True,
                           text=True, timeout=10)
        out = (r.stdout + r.stderr).strip().splitlines()
        return out[0][:120] if out else p
    except Exception:
        return p

def status() -> dict:
    libs: dict[str, str | None] = {}
    for pkg in ["pymupdf", "pikepdf", "pypdf", "pdfplumber", "pillow",
                "segno", "openpyxl", "pydantic", "typer", "mcp"]:
        try:
            libs[pkg] = md.version(pkg)
        except Exception:
            libs[pkg] = None
    bins = {
        "ghostscript": _bin("gswin64c") or _bin("gs"),
        "qpdf": _bin("qpdf"),
        "typst": _bin("typst"),
        "tesseract": _bin("tesseract", ["--version"]),
        "libreoffice": _bin("soffice", ["--version"]),
        "poppler_pdffonts": _bin("pdffonts", ["-v"]),
        "verapdf": _bin("verapdf", ["--version"]),
        "java": _bin("java", ["-version"]),
        "chromium_playwright": None,  # detectado via python playwright se instalado
        "ollama": _bin("ollama", ["--version"]),
    }
    try:
        import playwright  # noqa
        bins["chromium_playwright"] = "playwright-py instalado (navegador a verificar)"
    except Exception:
        pass
    return {"libs": libs, "bins": bins}

def perfil_hardware() -> str:
    """P0 default; P1 se nvidia-smi responde."""
    if shutil.which("nvidia-smi"):
        try:
            subprocess.run(["nvidia-smi", "-L"], capture_output=True, timeout=10, check=True)
            return "P1"
        except Exception:
            pass
    return "P0"
