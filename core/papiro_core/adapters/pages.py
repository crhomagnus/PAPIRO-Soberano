# -*- coding: utf-8 -*-
"""Nivel 1+N9 parcial - paginas, compressao, reparo. RF-101..110, RF-901..904."""
from __future__ import annotations
import pathlib, fitz, pikepdf

def _require_out(out_dir: pathlib.Path) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

def merge(entradas: list[pathlib.Path], out: pathlib.Path) -> dict:
    pdf = pikepdf.Pdf.new()
    total = 0
    for e in entradas:
        with pikepdf.open(e) as src:
            pdf.pages.extend(src.pages)
            total += len(src.pages)
    pdf.save(out)
    return {"paginas": total}

def split(entrada: pathlib.Path, out_dir: pathlib.Path, intervalos: list[str]) -> list[pathlib.Path]:
    """intervalos tipo ['1-3','4-'] 1-based."""
    _require_out(out_dir)
    with pikepdf.open(entrada) as src:
        n = len(src.pages)
        outs = []
        for i, iv in enumerate(intervalos):
            a, _, b = iv.partition("-")
            lo = max(int(a or 1) - 1, 0)
            hi = (int(b) if b.strip() else n)
            dst = pikepdf.Pdf.new()
            dst.pages.extend(src.pages[lo:hi])
            p = out_dir / f"parte{i+1}_{lo+1}-{hi}.pdf"
            dst.save(p)
            outs.append(p)
        return outs

def extrair(entrada: pathlib.Path, paginas: list[int], out: pathlib.Path) -> int:
    with pikepdf.open(entrada) as src:
        dst = pikepdf.Pdf.new()
        for pg in paginas:
            dst.pages.append(src.pages[pg - 1])
        dst.save(out)
        return len(paginas)

def girar(entrada: pathlib.Path, out: pathlib.Path, paginas: list[int], angulo: int) -> int:
    with pikepdf.open(entrada) as src:
        for pg in paginas:
            src.pages[pg - 1].Rotate = (int(src.pages[pg - 1].get("/Rotate", 0)) + angulo) % 360
        src.save(out)
        return len(paginas)

def remover_branco(entrada: pathlib.Path, out: pathlib.Path, limiar_chars: int = 10) -> dict:
    doc = fitz.open(entrada)
    keep = [p for p in range(doc.page_count) if len(doc[p].get_text().strip()) >= limiar_chars or doc[p].get_images()]
    dst = fitz.open()
    for p in keep:
        dst.insert_pdf(doc, from_page=p, to_page=p)
    dst.save(out)
    n = doc.page_count
    doc.close(); dst.close()
    return {"mantidas": len(keep), "removidas": n - len(keep)}

def reparar_cascata(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    """RF-901: tenta pikepdf; se falhar, fitz com garbage (reconstrucao)."""
    tentativas = []
    try:
        with pikepdf.open(entrada) as pdf:
            pdf.save(out)
        return {"ok": True, "via": "pikepdf"}
    except Exception as e:
        tentativas.append(f"pikepdf: {e}"[:200])
    doc = fitz.open(entrada)  # pode lancar -> E_CORROMPIDO real
    doc.save(out, garbage=4, deflate=True)
    n = doc.page_count
    doc.close()
    return {"ok": True, "via": "fitz-garbage", "paginas": n, "tentativas": tentativas}

def otimizar(entrada: pathlib.Path, out: pathlib.Path, perfil: str = "email") -> dict:
    """RF-902: recompressao + garbage. Perfis: tela|email|impressao|arquivo."""
    doc = fitz.open(entrada)
    # subsample agressivo por perfil
    matriz = {"tela": 0.6, "email": 0.75, "impressao": 1.0, "arquivo": 1.0}.get(perfil, 0.75)
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if matriz < 1.0 and (pix.width > 1200 or pix.height > 1200):
                    pix = fitz.Pixmap(pix, [int(pix.width * matriz), int(pix.height * matriz), pix.alpha])
                doc.update_stream(xref, pix.tobytes("jpg", jpg_quality=70 if perfil in ("tela", "email") else 85))
            except Exception:
                continue
    doc.save(out, garbage=4, deflate=True)
    n = doc.page_count
    doc.close()
    antes, depois = entrada.stat().st_size, out.stat().st_size
    return {"paginas": n, "antes": antes, "depois": depois,
            "reducao_pct": round(100 * (1 - depois / max(antes, 1)), 1)}

def linearizar(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    """RF-903: pikepdf linearize (equivale qpdf --linearize)."""
    with pikepdf.open(entrada) as pdf:
        pdf.save(out, linearize=True)
    return {"ok": True}
