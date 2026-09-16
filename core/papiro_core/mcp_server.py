# -*- coding: utf-8 -*-
"""Servidor MCP papiro - 38 tools §8.3. Transporte stdio via FastMCP."""
from __future__ import annotations
import json, time, pathlib
from mcp.server.fastmcp import FastMCP
from . import ROOT, new_job_id, job_dirs
from .audit import envelope, err, out_entry
from . import engines as ENG
from .adapters import inspect as INS, pages as PAG, edit as ED, create as CRE
from .adapters import convert as CONV, intel as INTEL
from .adapters import qa as QA, compare as CMP
from . import jobs as JOBS

mcp = FastMCP("papiro")

def _ctx(out_dir: str):
    jid = new_job_id()
    o = pathlib.Path(out_dir)
    o.mkdir(parents=True, exist_ok=True)
    return jid, o, time.time()

@mcp.tool()
def inspect(op: str, entrada: str, out_dir: str, regex: str = "") -> dict:
    """all|fonts|images|pages|revisions|risk + search via op=search."""
    jid, o, t0 = _ctx(out_dir)
    p = pathlib.Path(entrada)
    if not p.exists():
        return envelope(jid, [], {"name": "n/a"}, 0, error=err("E_ENTRADA", entrada))
    try:
        if op == "all":
            d = {"inventario": INS.inventario(p), "fontes": INS.fontes(p)[:100],
                 "imagens": INS.imagens(p)[:100], "paginas": INS.classifica_paginas(p),
                 "revisoes": INS.revisoes(p), "risco": INS.triagem_risco(p)}
        elif op == "fonts": d = INS.fontes(p)
        elif op == "images": d = INS.imagens(p)
        elif op == "pages": d = INS.classifica_paginas(p)
        elif op == "revisions": d = INS.revisoes(p)
        elif op == "risk": d = INS.triagem_risco(p)
        elif op == "search": d = INS.busca(p, regex)
        else: return envelope(jid, [], {}, 0, error=err("E_SEM_SUPORTE", f"op {op}"))
        f = o / f"inspect_{op}.json"
        f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        return envelope(jid, [out_entry(f)], {"name": "pymupdf+pikepdf"}, time.time() - t0)
    except ValueError as e:
        return envelope(jid, [], {}, time.time() - t0, error=err("E_CORROMPIDO", str(e)))

@mcp.tool()
def search(entrada: str, out_dir: str, regex: str) -> dict:
    return inspect("search", entrada, out_dir, regex)

@mcp.tool()
def render_pages(entrada: str, out_dir: str, dpi: int = 110) -> dict:
    jid, o, t0 = _ctx(out_dir)
    outs = CONV.para_png(pathlib.Path(entrada), o / "render", dpi)
    return envelope(jid, [out_entry(p) for p in outs], {"name": "pymupdf"}, time.time() - t0)

@mcp.tool()
def pages(op: str, entrada: str, out_dir: str, paginas: str = "", angulo: int = 90,
          intervalos: str = "", entradas: str = "") -> dict:
    """merge|split|extract|delete|move|rotate|duplicate|interleave|resize|boxes|nup|booklet|poster|labels|blank_remove."""
    jid, o, t0 = _ctx(out_dir)
    p = pathlib.Path(entrada)
    try:
        if op == "merge":
            es = [pathlib.Path(e.strip()) for e in entradas.split(";") if e.strip()]
            out = o / "merge.pdf"
            r = PAG.merge(es, out)
            qa = QA.run(out)
            return envelope(jid, [out_entry(out, r["paginas"])], {"name": "pikepdf"}, time.time() - t0, qa=qa)
        if op == "split":
            outs = PAG.split(p, o, [s.strip() for s in intervalos.split(";") if s.strip()])
            return envelope(jid, [out_entry(x) for x in outs], {"name": "pikepdf"}, time.time() - t0)
        if op == "extract":
            out = o / "extract.pdf"
            n = PAG.extrair(p, [int(x) for x in paginas.split(",") if x.strip()], out)
            return envelope(jid, [out_entry(out, n)], {"name": "pikepdf"}, time.time() - t0)
        if op == "rotate":
            out = o / "rotate.pdf"
            n = PAG.girar(p, out, [int(x) for x in paginas.split(",") if x.strip()], angulo)
            return envelope(jid, [out_entry(out)], {"name": "pikepdf"}, time.time() - t0)
        if op == "blank_remove":
            out = o / "sem_branco.pdf"
            r = PAG.remover_branco(p, out)
            return envelope(jid, [out_entry(out, r["mantidas"])], {"name": "fitz"}, time.time() - t0)
        return envelope(jid, [], {}, 0, error=err("E_SEM_SUPORTE", f"pages.{op} ainda nao implementado nesta fase"))
    except Exception as e:
        return envelope(jid, [], {}, time.time() - t0, error=err("E_MOTOR", str(e)[:500]))

@mcp.tool()
def outline(entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    import fitz
    doc = fitz.open(entrada)
    toc = doc.get_toc()
    doc.close()
    f = o / "outline.json"
    f.write_text(json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def attachments(op: str, entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    import pikepdf
    with pikepdf.open(entrada) as pdf:
        names = list(pdf.attachments.keys()) if hasattr(pdf, "attachments") else []
        if op == "list":
            f = o / "anexos.json"
            f.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
            return envelope(jid, [out_entry(f)], {"name": "pikepdf"}, time.time() - t0)
        for n in names:
            (o / n).write_bytes(pdf.attachments[n].obj.read_bytes())
    return envelope(jid, [], {"name": "pikepdf"}, time.time() - t0)

@mcp.tool()
def stamp(entrada: str, out_dir: str, texto: str, pagina: int = 1, x: float = 72, y: float = 72) -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / "stamp.pdf"
    ED.carimbo(pathlib.Path(entrada), out, texto, pagina, x, y)
    return envelope(jid, [out_entry(out)], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def replace_text(entrada: str, out_dir: str, de: str, para: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / "replace.pdf"
    r = ED.substituir_texto(pathlib.Path(entrada), out, de, para)
    return envelope(jid, [out_entry(out, r["paginas"])], {"name": "fitz"}, time.time() - t0,
                    warnings=[r.get("aviso", "")])

@mcp.tool()
def annotate(op: str, entrada: str, out_dir: str) -> dict:
    return {"ok": False, "error": err("E_SEM_SUPORTE", "annotate xfdf em fase 2")}

@mcp.tool()
def layers(op: str, entrada: str, out_dir: str) -> dict:
    return {"ok": False, "error": err("E_SEM_SUPORTE", "OCG em fase 2 (pikepdf manual)")}

@mcp.tool()
def images(op: str, entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    d = INS.imagens(pathlib.Path(entrada))
    f = o / "imagens.json"
    f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def metadata(entrada: str, out_dir: str, titulo: str = "", autor: str = "") -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / "meta.pdf"
    ED.metadados(pathlib.Path(entrada), out, titulo, autor)
    return envelope(jid, [out_entry(out)], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def compose(motor: str, out_dir: str, markdown: str = "", titulo: str = "", saida: str = "doc.pdf") -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    r = CRE.markdown_para_pdf(markdown, out, titulo)
    qa = QA.run(out, eh_design=True)
    return envelope(jid, [out_entry(out, r.get("paginas", 0))], {"name": r.get("via", motor)}, time.time() - t0, qa=qa)

@mcp.tool()
def office_to_pdf(entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    try:
        r = CRE.office_para_pdf(pathlib.Path(entrada), o)
        return envelope(jid, [out_entry(pathlib.Path(r["saida"]))], {"name": "libreoffice"}, time.time() - t0)
    except RuntimeError as e:
        return envelope(jid, [], {}, time.time() - t0, error=err("E_SEM_SUPORTE", str(e)))

@mcp.tool()
def mail_merge(out_dir: str, markdown_tpl: str = "", dados_json: str = "[]", saida: str = "lote.pdf") -> dict:
    import json as j
    jid, o, t0 = _ctx(out_dir)
    dados = j.loads(dados_json or "[]")
    import fitz
    doc = fitz.open()
    for row in dados:
        page = doc.new_page()
        y = 72
        for k, v in (row.items() if isinstance(row, dict) else enumerate(row)):
            page.insert_text((72, y), f"{k}: {v}"[:110], fontsize=10)
            y += 14
    out = o / saida
    doc.save(out)
    n = doc.page_count
    doc.close()
    return envelope(jid, [out_entry(out, n)], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def graphics(out_dir: str, tipo: str = "qr", conteudo: str = "PAPIRO", saida: str = "graf.pdf") -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    CRE.qr_pdf(conteudo, out)
    return envelope(jid, [out_entry(out, 1)], {"name": "segno"}, time.time() - t0)

@mcp.tool()
def capture(out_dir: str, imagens: str = "", saida: str = "cap.pdf") -> dict:
    jid, o, t0 = _ctx(out_dir)
    ims = [pathlib.Path(p.strip()) for p in imagens.split(";") if p.strip()]
    out = o / saida
    r = CRE.imagens_para_pdf(ims, out)
    return envelope(jid, [out_entry(out, r["paginas"])], {"name": r["via"]}, time.time() - t0)

@mcp.tool()
def convert(entrada: str, out_dir: str, destino: str = "md") -> dict:
    jid, o, t0 = _ctx(out_dir)
    p = pathlib.Path(entrada)
    if destino in ("txt",):
        out = o / (p.stem + ".txt")
        CONV.para_texto(p, out)
    elif destino in ("md",):
        out = o / (p.stem + ".md")
        CONV.para_markdown(p, out)
    elif destino in ("png",):
        outs = CONV.para_png(p, o / "png")
        return envelope(jid, [out_entry(x) for x in outs], {"name": "fitz"}, time.time() - t0)
    elif destino in ("xlsx",):
        out = o / (p.stem + ".xlsx")
        CONV.tabelas_xlsx(p, out)
    else:
        return envelope(jid, [], {}, 0, error=err("E_SEM_SUPORTE", f"convert->{destino}"))
    return envelope(jid, [out_entry(out)], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def ocr(entrada: str, out_dir: str, idioma: str = "por", saida: str = "ocr.pdf") -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    try:
        r = INTEL.ocr(pathlib.Path(entrada), out, idioma)
        return envelope(jid, [out_entry(out)], {"name": r.get("via", "ocr")}, time.time() - t0,
                        warnings=[r.get("aviso", "")] if r.get("aviso") else [])
    except RuntimeError as e:
        return envelope(jid, [], {}, time.time() - t0, error=err("E_SEM_SUPORTE", str(e)))

@mcp.tool()
def parse(entrada: str, out_dir: str) -> dict:
    return convert(entrada, out_dir, "md")

@mcp.tool()
def extract(op: str, entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    p = pathlib.Path(entrada)
    if op == "tables":
        out = o / "tabelas.xlsx"
        r = CONV.tabelas_xlsx(p, out)
        return envelope(jid, [out_entry(out)], {"name": "pdfplumber"}, time.time() - t0)
    if op == "fields":
        d = CONV.listar_campos(p)
        f = o / "fields.json"
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        return envelope(jid, [out_entry(f)], {"name": "fitz"}, time.time() - t0)
    if op == "entities":
        t = INTEL.texto_completo(p)
        d = INTEL.detectar_pii(t)
        f = o / "entities.json"
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        return envelope(jid, [out_entry(f)], {"name": "regex"}, time.time() - t0)
    return envelope(jid, [], {}, 0, error=err("E_SEM_SUPORTE", op))

@mcp.tool()
def rag(op: str, out_dir: str, doc_id: str = "", entrada: str = "", pergunta: str = "") -> dict:
    from pathlib import Path
    db = Path(out_dir) / "rag.db"
    if op == "index":
        INTEL.rag_index(db, doc_id, INTEL.texto_completo(Path(entrada)))
        return {"ok": True, "db": str(db)}
    if op == "ask":
        return {"ok": True, "respostas": INTEL.rag_ask(db, pergunta)}
    return {"ok": False, "error": err("E_SEM_SUPORTE", op)}

@mcp.tool()
def translate(entrada: str, out_dir: str, idioma: str = "en") -> dict:
    return {"ok": False, "error": err("E_SEM_SUPORTE", "traducao exige Ollama/BabelDOC (fase 2)")}

@mcp.tool()
def alt_text(entrada: str, out_dir: str) -> dict:
    return {"ok": False, "error": err("E_SEM_SUPORTE", "alt-text exige modelo de visao (fase 2)")}

@mcp.tool()
def forms(op: str, entrada: str, out_dir: str, dados_json: str = "{}") -> dict:
    import json as j
    jid, o, t0 = _ctx(out_dir)
    p = pathlib.Path(entrada)
    if op == "export":
        d = CONV.listar_campos(p)
        f = o / "form.json"
        f.write_text(j.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        return envelope(jid, [out_entry(f)], {"name": "fitz"}, time.time() - t0)
    if op == "fill":
        out = o / "filled.pdf"
        r = CONV.preencher(p, out, j.loads(dados_json or "{}"))
        return envelope(jid, [out_entry(out)], {"name": "fitz"}, time.time() - t0)
    if op == "flatten":
        out = o / "flat.pdf"
        CONV.achatar(p, out)
        return envelope(jid, [out_entry(out)], {"name": "fitz"}, time.time() - t0)
    return envelope(jid, [], {}, 0, error=err("E_SEM_SUPORTE", f"forms.{op}"))

@mcp.tool()
def conform(op: str, entrada: str, out_dir: str) -> dict:
    return {"ok": False, "error": err("E_SEM_SUPORTE", f"conform.{op} exige Ghostscript/veraPDF (fase 2). Use validate/optimize.")}

@mcp.tool()
def validate(entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    qa = QA.run(pathlib.Path(entrada))
    f = o / "validate.json"
    f.write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "qa"}, time.time() - t0, qa=qa)

@mcp.tool()
def preflight(entrada: str, out_dir: str) -> dict:
    return validate(entrada, out_dir)

@mcp.tool()
def color(op: str, entrada: str, out_dir: str) -> dict:
    return {"ok": False, "error": err("E_SEM_SUPORTE", "color ICC exige Ghostscript/LittleCMS (fase 2)")}

@mcp.tool()
def impose(op: str, entrada: str, out_dir: str) -> dict:
    return {"ok": False, "error": err("E_SEM_SUPORTE", "impose exige pdfimpose (fase 2)")}

@mcp.tool()
def optimize(entrada: str, out_dir: str, perfil: str = "email", saida: str = "otim.pdf") -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    r = PAG.otimizar(pathlib.Path(entrada), out, perfil)
    return envelope(jid, [out_entry(out, r["paginas"])], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def repair(entrada: str, out_dir: str, saida: str = "rep.pdf") -> dict:
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    try:
        r = PAG.reparar_cascata(pathlib.Path(entrada), out)
        return envelope(jid, [out_entry(out)], {"name": r["via"]}, time.time() - t0)
    except Exception as e:
        return envelope(jid, [], {}, time.time() - t0, error=err("E_CORROMPIDO", str(e)[:500]))

@mcp.tool()
def fonts(op: str, entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    d = INS.fontes(pathlib.Path(entrada))
    f = o / "fonts.json"
    f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "fitz"}, time.time() - t0)

@mcp.tool()
def compare(a: str, b: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    d = CMP.diff_texto(pathlib.Path(a), pathlib.Path(b))
    s = CMP.fidelidade_ssim(pathlib.Path(a), pathlib.Path(b))
    f = o / "compare.json"
    f.write_text(json.dumps({"diff": d, "ssim": s}, indent=2, ensure_ascii=False), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "difflib+ssim"}, time.time() - t0)

@mcp.tool()
def qa_run(entrada: str, out_dir: str, design: bool = False) -> dict:
    jid, o, t0 = _ctx(out_dir)
    qa = QA.run(pathlib.Path(entrada), eh_design=design)
    f = o / "qa-report.json"
    f.write_text(json.dumps({"job_id": jid, **qa}, indent=2, ensure_ascii=False), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "qa"}, time.time() - t0, qa=qa)

@mcp.tool()
def jobs(op: str, job_id: str = "") -> dict:
    if op == "status":
        return JOBS.job_status(job_id)
    return {"ok": False, "error": err("E_SEM_SUPORTE", op)}

@mcp.tool()
def recipes(op: str, out_dir: str, arquivo: str = "") -> dict:
    import yaml
    if op == "validate":
        rec = yaml.safe_load(pathlib.Path(arquivo).read_text(encoding="utf-8"))
        erros = JOBS.validar_receita(rec)
        return {"valida": not erros, "erros": erros}
    if op == "list":
        return {"receitas": [str(p) for p in (ROOT / "recipes").glob("*.yaml")]}
    return {"ok": False, "error": err("E_SEM_SUPORTE", op)}

@mcp.tool()
def engines() -> dict:
    return ENG.status()

def main():
    mcp.run()

if __name__ == "__main__":
    main()
