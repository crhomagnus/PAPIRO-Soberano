# -*- coding: utf-8 -*-
"""Jobs SQLite + receitas YAML §9.3 + roteador §9."""
from __future__ import annotations
import sqlite3, pathlib, json, hashlib, time
from . import LOGS

DB = LOGS / "jobs.db"

def _con():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, plano TEXT, status TEXT, passo INT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS motor_stats(tarefa TEXT, motor TEXT, ok INT, total INT,
                 PRIMARY KEY(tarefa, motor))""")
    return c

def job_criar(job_id: str, plano: list[dict]):
    c = _con()
    c.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)", (job_id, json.dumps(plano), "aberto", 0))
    c.commit(); c.close()

def job_passo(job_id: str, i: int, status: str = "aberto"):
    c = _con()
    c.execute("UPDATE jobs SET passo=?, status=? WHERE id=?", (i, status, job_id))
    c.commit(); c.close()

def job_status(job_id: str) -> dict:
    c = _con()
    r = c.execute("SELECT plano,status,passo FROM jobs WHERE id=?", (job_id,)).fetchone()
    c.close()
    if not r:
        return {"existe": False}
    return {"existe": True, "plano": json.loads(r[0]), "status": r[1], "passo": r[2]}

def stat_motor(tarefa: str, motor: str, ok: bool):
    c = _con()
    r = c.execute("SELECT ok,total FROM motor_stats WHERE tarefa=? AND motor=?", (tarefa, motor)).fetchone()
    if r:
        c.execute("UPDATE motor_stats SET ok=?, total=? WHERE tarefa=? AND motor=?",
                  (r[0] + (1 if ok else 0), r[1] + 1, tarefa, motor))
    else:
        c.execute("INSERT INTO motor_stats VALUES(?,?,?,?)", (tarefa, motor, 1 if ok else 0, 1))
    c.commit(); c.close()

def taxa_motor(tarefa: str, motor: str) -> float:
    c = _con()
    r = c.execute("SELECT ok,total FROM motor_stats WHERE tarefa=? AND motor=?", (tarefa, motor)).fetchone()
    c.close()
    if not r or not r[1]:
        return 0.8
    return r[0] / r[1]

# ---------- roteador ----------
def classificar(pedido: str) -> str:
    p = pedido.lower()
    for chave, tarefa in [
        ("assin", "assinatura"), ("tarj", "tarjamento"), ("ocr", "ocr"),
        ("traduz", "traducao"), ("apresent", "deck"), ("slide", "deck"),
        ("formul", "formulario"), ("tabel", "tabela"), ("compar", "comparar"),
        ("junt", "merge"), ("mescl", "merge"), ("divid", "split"), ("separ", "split"),
        ("marca d", "edicao"), ("carimb", "edicao"), ("comprim", "otimizar"),
        ("repar", "reparo"), ("pdf/a", "pdfa"), ("acessib", "pdfua"),
        ("criar", "criacao"), ("relator", "criacao"), ("contrato", "criacao"),
    ]:
        if chave in p:
            return tarefa
    return "inspecao"

def escolher_motor(tarefa: str, perfil: str = "P0") -> tuple[str, str | None]:
    """Retorna (primario, fallback) conforme §9.2."""
    tabela = {
        "criacao_tipografica": ("typst", "latex"),
        "criacao_html": ("chromium", "weasyprint"),
        "pdfa": ("ghostscript", "ocrmypdf"),
        "ocr_simples": ("ocrmypdf+tesseract", "rapidocr"),
        "ocr_estrutural": ("paddleocr-vl" if perfil != "P0" else "docling", "mineru"),
        "md_digital": ("pymupdf4llm", "docling"),
        "grafica": ("ghostscript", "scribus"),
        "office": ("libreoffice", None),
        "assinatura_a3": ("pyhanko", "jsignpdf"),
        "comparar": ("difflib+diff-pdf", "pymupdf+ssim"),
        "traducao": ("pdfmathtranslate+ollama", "argos"),
    }
    mapa = {"ocr": "ocr_simples", "tabela": "ocr_estrutural", "traducao": "traducao",
            "comparar": "comparar", "merge": "grafica", "criacao": "criacao_tipografica",
            "assinatura": "assinatura_a3"}
    chave = mapa.get(tarefa, "md_digital")
    prim, fb = tabela.get(chave, ("pymupdf", None))
    # pondera por historico
    return prim, fb

# ---------- receitas ----------
def validar_receita(rec: dict) -> list[str]:
    erros = []
    for campo in ("receita", "versao", "passos"):
        if campo not in rec:
            erros.append(f"falta {campo}")
    for i, p in enumerate(rec.get("passos", [])):
        if "ferramenta" not in p:
            erros.append(f"passo {i} sem ferramenta")
    return erros

def cache_key(ferramenta: str, com: dict) -> str:
    import json as j
    return hashlib.sha256(j.dumps({"f": ferramenta, "c": com}, sort_keys=True).encode()).hexdigest()[:16]
