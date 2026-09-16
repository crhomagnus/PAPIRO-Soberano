# -*- coding: utf-8 -*-
"""Resolvedor central de binarios (PRD §3.2: nomes proprios do Windows).
Procura em: PATH -> C:\\PAPIRO\\bin -> locais padrao de instalacao."""
from __future__ import annotations
import os, shutil, pathlib

PAPIRO_BIN = pathlib.Path(r"C:\PAPIRO\bin")

KNOWN = {
    "gswin64c": [
        PAPIRO_BIN / "gswin64c.exe",
        pathlib.Path(r"C:\Program Files\gs\gs10.07.1\bin\gswin64c.exe"),
    ],
    "qpdf": [
        PAPIRO_BIN / "qpdf.exe",
        pathlib.Path(r"C:\Program Files\qpdf 12.4.1\bin\qpdf.exe"),
    ],
    "typst": [
        PAPIRO_BIN / "typst.exe",
    ],
    "tesseract": [
        pathlib.Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    ],
    "soffice": [
        pathlib.Path(r"C:\Program Files\LibreOffice\program\soffice.com"),
        pathlib.Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    ],
    "verapdf": [
        pathlib.Path(r"C:\Program Files\veraPDF\verapdf.bat"),
    ],
}

TESSDATA = pathlib.Path(r"C:\PAPIRO\models\tessdata")

def qual(nome: str) -> str | None:
    p = shutil.which(nome)
    if p:
        return p
    for cand in KNOWN.get(nome, []):
        if cand.exists():
            return str(cand)
    return None

def env_extra() -> dict:
    env: dict[str, str] = {}
    if TESSDATA.exists():
        env["TESSDATA_PREFIX"] = str(TESSDATA)
    # garante C:\PAPIRO\bin no PATH do filho
    env["PATH"] = str(PAPIRO_BIN) + os.pathsep + os.environ.get("PATH", "")
    return env
