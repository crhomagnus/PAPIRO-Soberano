# -*- coding: utf-8 -*-
"""Roteador PRD §9.1/§9.2: pontua motores por qualidade x compatibilidade x historico - custo.

RNF-20: incluir motor novo = uma entrada em MOTORES (e o adaptador); o algoritmo nao muda."""
from __future__ import annotations
import unicodedata
from . import config, engines as ENG, jobs as JOBS

# motor -> tarefas atendidas, qualidade esperada (0-1), motores logicos exigidos, compatibilidade por perfil, custo (0-1)
MOTORES: dict[str, dict] = {
    "typst": {"tarefas": ["criacao"], "qualidade": 0.95, "requer": ["typst"], "custo": 0.1},
    "pymupdf-story": {"tarefas": ["criacao", "mala_direta"], "qualidade": 0.75, "requer": ["pymupdf"], "custo": 0.05},
    "chromium": {"tarefas": ["criacao_html"], "qualidade": 0.95, "requer": ["playwright"], "custo": 0.3},
    "libreoffice": {"tarefas": ["office"], "qualidade": 0.9, "requer": ["libreoffice"], "custo": 0.4},
    "ghostscript+verapdf": {"tarefas": ["pdfa"], "qualidade": 0.95, "requer": ["ghostscript", "verapdf"], "custo": 0.3},
    "ocrmypdf": {"tarefas": ["ocr", "pdfa"], "qualidade": 0.9, "requer": ["ocrmypdf", "tesseract", "ghostscript"], "custo": 0.5},
    "tesseract": {"tarefas": ["ocr"], "qualidade": 0.8, "requer": ["tesseract"], "custo": 0.5},
    "pymupdf4llm": {"tarefas": ["md_digital"], "qualidade": 0.85, "requer": ["pymupdf4llm"], "custo": 0.1},
    "pymupdf": {"tarefas": ["md_digital", "otimizar", "reparo", "edicao", "formulario", "inspecao"],
                "qualidade": 0.8, "requer": ["pymupdf"], "custo": 0.05},
    "ghostscript": {"tarefas": ["otimizar", "reparo", "grafica"], "qualidade": 0.9, "requer": ["ghostscript"], "custo": 0.3},
    "qpdf": {"tarefas": ["reparo", "linearizar"], "qualidade": 0.9, "requer": ["qpdf"], "custo": 0.05},
    "pikepdf": {"tarefas": ["reparo", "paginas", "linearizar", "inspecao"], "qualidade": 0.85, "requer": ["pikepdf"], "custo": 0.05},
    "pdfplumber": {"tarefas": ["tabela"], "qualidade": 0.8, "requer": ["pdfplumber"], "custo": 0.2},
    "pyhanko": {"tarefas": ["assinatura"], "qualidade": 0.95, "requer": ["pyhanko"], "custo": 0.2},
    "presidio": {"tarefas": ["pii"], "qualidade": 0.9, "requer": ["presidio-analyzer", "spacy"], "custo": 0.3},
    "regex-pii": {"tarefas": ["pii"], "qualidade": 0.7, "requer": [], "custo": 0.01},
    "difflib+opencv": {"tarefas": ["comparar"], "qualidade": 0.9, "requer": ["opencv-python-headless"], "custo": 0.2},
    "docling": {"tarefas": ["ocr_estrutural"], "qualidade": 0.9, "requer": ["docling"], "custo": 0.8},
    "paddleocr-vl": {"tarefas": ["ocr_estrutural"], "qualidade": 0.95, "requer": ["paddleocr"], "custo": 0.9,
                     "perfis": {"P0": 0.3}},
    "pdfmathtranslate+ollama": {"tarefas": ["traducao"], "qualidade": 0.9, "requer": ["pdf2zh", "ollama"], "custo": 0.9},
}

_LOGICO_LIB = {"playwright": "playwright", "docling": "docling", "paddleocr": "paddleocr", "pdf2zh": "pdf2zh"}

PALAVRAS = [
    ("assin", "assinatura"), ("tarj", "tarjamento"), ("anonim", "tarjamento"), ("ocr", "ocr"),
    ("escane", "ocr"), ("traduz", "traducao"), ("apresent", "deck"), ("slide", "deck"),
    ("formul", "formulario"), ("tabel", "tabela"), ("compar", "comparar"), ("junt", "paginas"),
    ("mescl", "paginas"), ("divid", "paginas"), ("separ", "paginas"), ("gir", "paginas"),
    ("marca d", "edicao"), ("carimb", "edicao"), ("comprim", "otimizar"), ("otimiz", "otimizar"),
    ("repar", "reparo"), ("pdf/a", "pdfa"), ("acessib", "pdfua"), ("mala direta", "mala_direta"),
    ("criar", "criacao"), ("relator", "criacao"), ("contrato", "criacao"), ("receitu", "criacao"),
    ("docx", "office"), ("planilha", "office"), ("markdown", "md_digital"), ("inspec", "inspecao"),
]


def _normalizar(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def classificar(pedido: str) -> str:
    p = _normalizar(pedido)
    for chave, tarefa in PALAVRAS:
        if chave in p:
            return tarefa
    return "inspecao"


def _disponivel(motor: str) -> bool:
    for req in MOTORES[motor]["requer"]:
        nome = _LOGICO_LIB.get(req, req)
        if not ENG.disponivel(nome):
            return False
    return True


def ranquear(tarefa: str, perfil: str | None = None, so_disponiveis: bool = True) -> list[dict]:
    perfil = perfil or config.perfil()
    lista = []
    for nome, m in MOTORES.items():
        if tarefa not in m["tarefas"]:
            continue
        disp = _disponivel(nome)
        if so_disponiveis and not disp:
            continue
        compat = m.get("perfis", {}).get(perfil, 1.0)
        taxa = JOBS.taxa_motor(tarefa, nome)
        pont = m["qualidade"] * compat * taxa - 0.1 * m["custo"]
        lista.append({"motor": nome, "pontuacao": round(pont, 4), "taxa_historica": round(taxa, 3),
                      "disponivel": disp})
    return sorted(lista, key=lambda x: -x["pontuacao"])


def escolher_motor(tarefa: str, perfil: str | None = None) -> tuple[str | None, str | None]:
    """(primario, fallback) entre os motores disponiveis."""
    r = ranquear(tarefa, perfil)
    return (r[0]["motor"] if r else None), (r[1]["motor"] if len(r) > 1 else None)
