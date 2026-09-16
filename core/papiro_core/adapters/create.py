# -*- coding: utf-8 -*-
"""Nivel 3 - criacao RF-301..310. Implementacao real sem dependencia paga:
MD->PDF via fitz; imagens->PDF sem recompressao; QR via segno; Office via LibreOffice se presente."""
from __future__ import annotations
import pathlib, shutil, subprocess
import fitz
import segno

def markdown_para_pdf(md_text: str, out: pathlib.Path, titulo: str = "") -> dict:
    """RF-301 simplificado: rende MD como texto paginado (Typst quando instalado = preferido)."""
    if shutil.which("typst"):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".typ", delete=False, encoding="utf-8") as f:
            f.write(f'#set page(paper: "a4", margin: 2cm)\n#heading("{titulo}")\n' + md_text.replace('"', "'"))
            typ = f.name
        r = subprocess.run(["typst", "compile", typ, str(out)], capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            doc = fitz.open(out)
            n = doc.page_count
            doc.close()
            return {"ok": True, "via": "typst", "paginas": n}
    # fallback fitz
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    if titulo:
        page.insert_text((72, y), titulo, fontsize=20)
        y += 30
    for line in md_text.splitlines():
        if y > 770:
            page = doc.new_page()
            y = 72
        page.insert_text((72, y), line[:110], fontsize=10)
        y += 14
    doc.save(out)
    n = doc.page_count
    doc.close()
    return {"ok": True, "via": "fitz", "paginas": n}

def imagens_para_pdf(imagens: list[pathlib.Path], out: pathlib.Path) -> dict:
    """RF-309: fotos->PDF (img2pdf quando disponivel = sem recompressao; senao fitz)."""
    try:
        import img2pdf  # type: ignore
        with open(out, "wb") as f:
            f.write(img2pdf.convert([str(p) for p in imagens]))
        doc = fitz.open(out)
        n = doc.page_count
        doc.close()
        return {"ok": True, "via": "img2pdf", "paginas": n}
    except Exception:
        doc = fitz.open()
        for im in imagens:
            pix = fitz.Pixmap(str(im))
            page = doc.new_page(width=pix.width, height=pix.height)
            page.insert_image(page.rect, filename=str(im))
        doc.save(out)
        n = doc.page_count
        doc.close()
        return {"ok": True, "via": "fitz", "paginas": n}

def qr_pdf(conteudo: str, out: pathlib.Path) -> dict:
    """RF-310: QR verificavel em PDF."""
    import tempfile
    qr = segno.make(conteudo)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as t:
        qr.save(t.name, scale=8)
        tmp = t.name
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(72, 72, 300, 300), filename=tmp)
    page.insert_text((72, 320), conteudo[:90], fontsize=10)
    doc.save(out)
    doc.close()
    pathlib.Path(tmp).unlink(missing_ok=True)
    return {"ok": True, "paginas": 1}

def office_para_pdf(entrada: pathlib.Path, out_dir: pathlib.Path) -> dict:
    """RF-303: LibreOffice headless. Erro claro se ausente (E_SEM_SUPORTE)."""
    soffice = shutil.which("soffice") or shutil.which("soffice.com")
    if not soffice:
        raise RuntimeError("E_SEM_SUPORTE: LibreOffice (soffice) nao instalado; instale via winget.")
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(entrada)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"E_MOTOR: soffice falhou: {(r.stderr or r.stdout)[:500]}")
    pdf = out_dir / (entrada.stem + ".pdf")
    return {"ok": True, "saida": str(pdf)}
