# -*- coding: utf-8 -*-
"""CLI papiro - espelho da MCP §8 + comandos §7.3. Uso: python -m papiro_core.cli <cmd>."""
from __future__ import annotations
import json, time, pathlib, shutil
import typer
from rich import print as rprint
from . import ROOT, new_job_id, job_dirs
from .audit import envelope, err, out_entry
from . import engines as ENG
from .adapters import inspect as INS, pages as PAG, edit as ED, create as CRE
from .adapters import convert as CONV, intel as INTEL
from .adapters import qa as QA, compare as CMP
from . import jobs as JOBS

app = typer.Typer(add_completion=False, help="PAPIRO SOBERANO - CLI espelho MCP")

def _job() -> tuple[str, pathlib.Path, pathlib.Path]:
    jid = new_job_id()
    w, o = job_dirs(jid)
    return jid, w, o

@app.command()
def status():
    """Saude do ambiente (papiro-status)."""
    st = ENG.status()
    rprint(json.dumps({"perfil": ENG.perfil_hardware(), **st}, indent=2, ensure_ascii=False))

@app.command()
def inspecionar(arquivo: str):
    """Nivel 0 RF-001..009."""
    t0 = time.time()
    jid, _w, o = _job()
    p = pathlib.Path(arquivo)
    if not p.exists():
        rprint(json.dumps(envelope(jid, [], {"name": "n/a"}, 0, error=err("E_ENTRADA", f"nao existe: {arquivo}")), ensure_ascii=False))
        raise typer.Exit(1)
    try:
        rel = {"inventario": INS.inventario(p), "fontes": INS.fontes(p)[:50],
               "imagens": INS.imagens(p)[:50], "paginas": INS.classifica_paginas(p),
               "revisoes": INS.revisoes(p), "risco": INS.triagem_risco(p)}
    except ValueError as e:
        rprint(json.dumps(envelope(jid, [], {"name": "n/a"}, time.time() - t0, error=err("E_CORROMPIDO", str(e))), ensure_ascii=False))
        raise typer.Exit(1)
    f = o / "inspecao.json"
    f.write_text(json.dumps(rel, indent=2, ensure_ascii=False), encoding="utf-8")
    rprint(json.dumps(envelope(jid, [out_entry(f)], {"name": "pymupdf+pikepdf", "version": "1.27/9"}, time.time() - t0), ensure_ascii=False))

@app.command()
def merge(saida: str, entradas: list[str]):
    """Junta PDFs com marcador por origem (RF-101)."""
    t0 = time.time()
    jid, _w, o = _job()
    outs = o / pathlib.Path(saida).name
    es = [pathlib.Path(e) for e in entradas]
    for e in es:
        if not e.exists():
            rprint(json.dumps(envelope(jid, [], {}, 0, error=err("E_ENTRADA", f"nao existe: {e}")), ensure_ascii=False))
            raise typer.Exit(1)
    r = PAG.merge(es, outs)
    qa = QA.run(outs)
    (o / "qa-report.json").write_text(json.dumps({"job_id": jid, **qa}, indent=2, ensure_ascii=False), encoding="utf-8")
    rprint(json.dumps(envelope(jid, [out_entry(outs, r["paginas"])], {"name": "pikepdf"}, time.time() - t0, qa=qa,
                               error=None if qa["status"] == "APROVADO" else err("E_CONFORMIDADE", f"QA {qa['status']}: {qa['bloqueantes']}")), ensure_ascii=False))

@app.command()
def ocr_cmd(arquivo: str, saida: str, idioma: str = "por"):
    """OCR RF-601 (comando papiro-ocr)."""
    t0 = time.time()
    jid, _w, o = _job()
    p = pathlib.Path(arquivo)
    out = o / pathlib.Path(saida).name
    try:
        r = INTEL.ocr(p, out, idioma)
    except RuntimeError as e:
        msg = str(e)
        code = msg.split(":")[0] if msg.startswith("E_") else "E_MOTOR"
        rprint(json.dumps(envelope(jid, [], {"name": "ocr"}, time.time() - t0, error=err(code, msg)), ensure_ascii=False))
        raise typer.Exit(1)
    qa = QA.run(out)
    rprint(json.dumps(envelope(jid, [out_entry(out)], {"name": r.get("via", "ocr")}, time.time() - t0, qa=qa), ensure_ascii=False))

@app.command()
def criar(template_md: str, saida: str, titulo: str = ""):
    """Cria PDF de Markdown (RF-301)."""
    t0 = time.time()
    jid, _w, o = _job()
    md = pathlib.Path(template_md).read_text(encoding="utf-8") if pathlib.Path(template_md).exists() else template_md
    out = o / pathlib.Path(saida).name
    r = CRE.markdown_para_pdf(md, out, titulo)
    qa = QA.run(out, eh_design=True)
    (o / "qa-report.json").write_text(json.dumps({"job_id": jid, **qa}, indent=2, ensure_ascii=False), encoding="utf-8")
    rprint(json.dumps(envelope(jid, [out_entry(out, r.get("paginas", 0))], {"name": r.get("via", "?")}, time.time() - t0, qa=qa), ensure_ascii=False))

@app.command()
def otimizar_cmd(arquivo: str, saida: str, perfil: str = "email"):
    """Compressao RF-902 + linearize RF-903."""
    t0 = time.time()
    jid, _w, o = _job()
    out = o / pathlib.Path(saida).name
    r = PAG.otimizar(pathlib.Path(arquivo), out, perfil)
    qa = QA.run(out)
    rprint(json.dumps(envelope(jid, [out_entry(out, r["paginas"])], {"name": "fitz"}, time.time() - t0, qa=qa), ensure_ascii=False))

@app.command()
def comparar(a: str, b: str):
    """Diff RF-607."""
    t0 = time.time()
    jid, _w, o = _job()
    d = CMP.diff_texto(pathlib.Path(a), pathlib.Path(b))
    s = CMP.fidelidade_ssim(pathlib.Path(a), pathlib.Path(b))
    f = o / "comparacao.json"
    f.write_text(json.dumps({"diff": d, "fidelidade": s}, indent=2, ensure_ascii=False), encoding="utf-8")
    rprint(json.dumps(envelope(jid, [out_entry(f)], {"name": "difflib+ssim"}, time.time() - t0), ensure_ascii=False))

@app.command()
def tarjar_cmd(arquivo: str, saida: str, caixas_json: str):
    """Tarja real RF-808. caixas_json='[{\"pagina\":1,\"x0\":..}]'."""
    import json as j
    t0 = time.time()
    jid, _w, o = _job()
    out = o / pathlib.Path(saida).name
    caixas = j.loads(caixas_json)
    r = ED.tarjar(pathlib.Path(arquivo), out, caixas)
    qa = QA.run(out)
    rprint(json.dumps(envelope(jid, [out_entry(out, r["paginas"])], {"name": "fitz-redact"}, time.time() - t0, qa=qa), ensure_ascii=False))

@app.command()
def receita(acao: str, arquivo: str = ""):
    """Gestao receitas: validar|mostrar."""
    import yaml
    p = pathlib.Path(arquivo)
    if acao == "validar":
        rec = yaml.safe_load(p.read_text(encoding="utf-8"))
        erros = JOBS.validar_receita(rec)
        rprint(json.dumps({"valida": not erros, "erros": erros}, ensure_ascii=False))
    elif acao == "mostrar":
        rprint(p.read_text(encoding="utf-8"))
    else:
        rprint("uso: receita validar|mostrar <arquivo>")

def app_run():
    app()

if __name__ == "__main__":
    app()
