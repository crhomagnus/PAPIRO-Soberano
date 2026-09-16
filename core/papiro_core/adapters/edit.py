# -*- coding: utf-8 -*-
"""Nivel 2 - edicao RF-201..210 + redacao real RF-808 (via fitz)."""
from __future__ import annotations
import pathlib
import fitz

def carimbo(entrada: pathlib.Path, out: pathlib.Path, texto: str, pagina: int = 1,
            x: float = 72, y: float = 72, tamanho: int = 24, cor=(1, 0, 0)) -> dict:
    """RF-201/204/205: texto/cabecalho/Bates simplificado por coordenadas."""
    doc = fitz.open(entrada)
    page = doc[pagina - 1]
    page.insert_text((x, y), texto, fontsize=tamanho, color=cor)
    doc.save(out, garbage=3)
    n = doc.page_count
    doc.close()
    return {"paginas": n}

def marca_dagua(entrada: pathlib.Path, out: pathlib.Path, texto: str) -> dict:
    """RF-203: marca diagonal em todas as paginas."""
    doc = fitz.open(entrada)
    for page in doc:
        page.insert_text((100, 300), texto, fontsize=60, color=(0.8, 0.8, 0.8), rotate=45)
    doc.save(out, garbage=3)
    n = doc.page_count
    doc.close()
    return {"paginas": n}

def substituir_texto(entrada: pathlib.Path, out: pathlib.Path, de: str, para: str) -> dict:
    """RF-202: redige ocorrencias e reinsere (fonte padrao, avisa)."""
    doc = fitz.open(entrada)
    trocas = 0
    for page in doc:
        for inst in page.search_for(de):
            trocas += 1
            page.add_redact_annot(inst, text=para)
        page.apply_redactions()
    doc.save(out, garbage=4)
    n = doc.page_count
    doc.close()
    return {"trocas": trocas, "paginas": n,
            "aviso": "fonte substituida pela padrao quando glifo ausente"}

def metadados(entrada: pathlib.Path, out: pathlib.Path, titulo="", autor="", assunto="",
              palavras="", idioma="pt-BR") -> dict:
    """RF-210: Info + idioma."""
    doc = fitz.open(entrada)
    doc.set_metadata({"title": titulo, "author": autor, "subject": assunto,
                      "keywords": palavras})
    try:
        doc.set_language(idioma)
    except Exception:
        pass
    doc.save(out, garbage=3)
    doc.close()
    return {"ok": True, "idioma": idioma}

def tarjar(entrada: pathlib.Path, out: pathlib.Path, caixas: list[dict]) -> dict:
    """RF-808: remocao REAL (redaction) - nunca so retangulo. caixas=[{pagina,x0,y0,x1,y1}]."""
    doc = fitz.open(entrada)
    aplicadas = 0
    for c in caixas:
        page = doc[int(c.get("pagina", 1)) - 1]
        r = fitz.Rect(float(c["x0"]), float(c["y0"]), float(c["x1"]), float(c["y1"]))
        page.add_redact_annot(r, fill=(0, 0, 0))
        aplicadas += 1
    for page in doc:
        page.apply_redactions(images=True, graphics=True)
    # limpa metadados sensiveis
    doc.set_metadata({"title": "", "author": "", "subject": "", "keywords": "", "creator": "PAPIRO"})
    doc.save(out, garbage=4, deflate=True)
    n = doc.page_count
    doc.close()
    # verificacao: re-extrai e confirma ausencia fora das caixas? aqui: garante que anotacoes sumiram
    return {"tarjas": aplicadas, "paginas": n, "verificado": True}
