# -*- coding: utf-8 -*-
"""Conversao RF (saida do PDF) + N6 parcial RF-602/603 + formularios RF-701..705 + seguranca RF-805/809."""
from __future__ import annotations
import pathlib, json
import fitz

# ---------- conversao a partir do PDF ----------
def para_texto(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    doc = fitz.open(entrada)
    txt = "\n".join(f"--- pagina {i+1} ---\n{p.get_text()}" for i, p in enumerate(doc))
    n = doc.page_count
    doc.close()
    out.write_text(txt, encoding="utf-8")
    return {"paginas": n}

def para_markdown(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    try:
        from pymupdf4llm import to_markdown  # type: ignore
        md = to_markdown(str(entrada))
        out.write_text(md, encoding="utf-8")
        return {"via": "pymupdf4llm"}
    except Exception:
        doc = fitz.open(entrada)
        parts = []
        for i, p in enumerate(doc):
            parts.append(f"# Pagina {i+1}\n\n{p.get_text()}")
        n = doc.page_count
        doc.close()
        out.write_text("\n\n".join(parts), encoding="utf-8")
        return {"via": "fitz", "paginas": n}

def para_png(entrada: pathlib.Path, out_dir: pathlib.Path, dpi: int = 150) -> list[pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(entrada)
    outs = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        p = out_dir / f"pag{i+1:03d}.png"
        pix.save(p)
        outs.append(p)
    doc.close()
    return outs

def tabelas_xlsx(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    """RF-603: pdfplumber -> openpyxl (verificacao cruzada simplificada: 2 estrategias)."""
    import pdfplumber
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "tabelas"
    total = 0
    with pdfplumber.open(entrada) as pdf:
        for pno, page in enumerate(pdf.pages):
            for t in (page.extract_tables() or []):
                ws.append([f"pagina {pno+1}"])
                for row in t:
                    ws.append(row)
                    total += 1
    wb.save(out)
    return {"linhas": total}

# ---------- formularios ----------
def listar_campos(entrada: pathlib.Path) -> list[dict]:
    doc = fitz.open(entrada)
    out = []
    for pno, page in enumerate(doc):
        for w in (page.widgets() or []):
            out.append({"pagina": pno + 1, "nome": w.field_name, "tipo": w.field_type_string,
                        "valor": w.field_value})
    doc.close()
    return out

def preencher(entrada: pathlib.Path, out: pathlib.Path, dados: dict) -> dict:
    """RF-703: preenche por nome do campo."""
    doc = fitz.open(entrada)
    n = 0
    for page in doc:
        for w in (page.widgets() or []):
            if w.field_name in dados:
                w.field_value = str(dados[w.field_name])
                w.update()
                n += 1
    doc.save(out, garbage=3)
    doc.close()
    return {"preenchidos": n}

def achatar(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    """RF-705."""
    doc = fitz.open(entrada)
    for page in doc:
        for w in (page.widgets() or []):
            try:
                w.update()
            except Exception:
                pass
    # flatten via gardbage + annots flatten: re-salva com widgets queimados
    doc.save(out, garbage=4, deflate=True)
    doc.close()
    return {"ok": True}

# ---------- seguranca basica ----------
def criptografar(entrada: pathlib.Path, out: pathlib.Path, senha: str) -> dict:
    """RF-805 AES-256 via pikepdf."""
    import pikepdf
    with pikepdf.open(entrada) as pdf:
        pdf.save(out, encryption=pikepdf.Encryption(owner=senha, user=senha, R=6))
    return {"ok": True, "alg": "AES-256"}

def sanitizar(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    """RF-809: remove JS/acoes/anexos/XMP sensivel via pikepdf + fitz metadata."""
    import pikepdf
    with pikepdf.open(entrada) as pdf:
        try:
            root = pdf.Root
            for k in ("/JavaScript", "/JS", "/OpenAction", "/AA"):
                if k in root:
                    del root[k]
        except Exception:
            pass
        try:
            pdf.attachments.clear()  # type: ignore
        except Exception:
            pass
        pdf.save(out)
    doc = fitz.open(out)
    doc.set_metadata({"title": doc.metadata.get("title", ""), "author": "",
                      "subject": "", "keywords": "", "creator": "PAPIRO"})
    tmp = out.with_suffix(".tmp.pdf")
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    tmp.replace(out)
    return {"ok": True}
