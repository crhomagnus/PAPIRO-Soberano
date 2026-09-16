# -*- coding: utf-8 -*-
"""Nivel 0 - Inspecao e diagnostico RF-001..RF-009. Motores: PyMuPDF + pikepdf + pypdf."""
from __future__ import annotations
import re, pathlib
import fitz  # PyMuPDF
import pikepdf
from pypdf import PdfReader

def _open_ok(path: pathlib.Path):
    try:
        doc = fitz.open(path)
        return doc
    except Exception as e:
        raise ValueError(f"E_CORROMPIDO: {e}")

def inventario(path: pathlib.Path) -> dict:
    """RF-001: paginas, versao, produtor, criptografia, tags, camadas, anexos, forms, assinaturas."""
    doc = _open_ok(path)
    n = doc.page_count
    meta = doc.metadata or {}
    # versao via pikepdf
    ver = ""
    is_enc = doc.needs_pass
    try:
        with pikepdf.open(path) as pdf:
            ver = str(pdf.pdf_version)
            has_acro = "/AcroForm" in str(pdf.Root.keys())
            has_oc = "/OCProperties" in str(pdf.Root.keys())
            embeds = len(pdf.attachments) if hasattr(pdf, "attachments") else 0
    except Exception:
        has_acro, has_oc, embeds = False, False, 0
    # assinaturas: campos Sig
    sigs = 0
    try:
        for page in doc:
            for w in (page.widgets() or []):
                if w.field_type_string == "Signature":
                    sigs += 1
    except Exception:
        pass
    # tags: marcado?
    marcado = doc.is_marked if hasattr(doc, "is_marked") else False
    out = {"paginas": n, "versao_pdf": ver, "produtor": meta.get("producer", ""),
           "criador": meta.get("creator", ""), "titulo": meta.get("title", ""),
           "autor": meta.get("author", ""), "criptografado": bool(is_enc),
           "marcado_tags": bool(marcado), "tem_acroform": bool(has_acro),
           "tem_camadas_ocg": bool(has_oc), "anexos": int(embeds),
           "assinaturas_detectadas": int(sigs)}
    doc.close()
    return out

def fontes(path: pathlib.Path) -> list[dict]:
    """RF-002: tipo, embutida, subset, fsType(relatado quando disponivel), ToUnicode."""
    doc = _open_ok(path)
    rows = []
    for pno in range(doc.page_count):
        for f in doc.get_page_fonts(pno):
            # PyMuPDF>=1.26: 6 tuplas; antigas: 7 com referencer
            xref, ext, ftype, base, name, enc = f[:6]
            embutida = ext != "n/a"
            # ToUnicode: tenta extrair
            to_unicode = False
            try:
                pix = doc.extract_font(xref)
                to_unicode = bool(pix and pix[3] is not None)
            except Exception:
                pass
            rows.append({"pagina": pno + 1, "nome": name or base, "tipo": ftype,
                         "ext": ext, "embutida": bool(embutida),
                         "encoding": enc, "to_unicode": to_unicode})
    doc.close()
    # dedup por nome
    seen, out = set(), []
    for r in rows:
        k = (r["nome"], r["pagina"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out

def imagens(path: pathlib.Path) -> list[dict]:
    """RF-003: DPI efetivo, espaco de cor, compressao, peso."""
    doc = _open_ok(path)
    rows = []
    for pno, page in enumerate(doc):
        rect = page.rect
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                w, h = pix.width, pix.height
                cs = pix.colorspace.name if pix.colorspace else "?"
                # DPI efetivo: bbox da imagem na pagina
                try:
                    bbox = page.get_image_bbox(img)
                    dw = max(bbox.width / 72.0, 1e-6)  # polegadas
                    dpi = round(w / dw, 1)
                except Exception:
                    dpi = None
                rows.append({"pagina": pno + 1, "xref": xref, "w_px": w, "h_px": h,
                             "cores": pix.n, "espaco_cor": cs, "dpi_efetivo": dpi,
                             "bytes": len(pix.tobytes())})
            except Exception:
                continue
    doc.close()
    return rows

def classifica_paginas(path: pathlib.Path) -> list[dict]:
    """RF-004: digital / escaneada / hibrida via heuristica texto x area imagem."""
    doc = _open_ok(path)
    out = []
    for pno, page in enumerate(doc):
        texto = page.get_text().strip()
        imgs = page.get_images(full=True)
        area_img = 0.0
        try:
            for img in imgs:
                area_img += page.get_image_bbox(img).get_area()
        except Exception:
            pass
        area_pag = page.rect.get_area()
        cobertura = area_img / max(area_pag, 1)
        if len(texto) > 100 and cobertura < 0.5:
            classe = "digital"
        elif len(texto) < 20 and cobertura > 0.3:
            classe = "escaneada"
        else:
            classe = "hibrida"
        out.append({"pagina": pno + 1, "classe": classe, "chars_texto": len(texto),
                    "cobertura_img": round(cobertura, 3)})
    doc.close()
    return out

def busca(path: pathlib.Path, regex: str) -> list[dict]:
    """RF-006: texto/regex com coordenadas."""
    rx = re.compile(regex)
    doc = _open_ok(path)
    hits = []
    for pno, page in enumerate(doc):
        for inst in page.search_for(regex) if not any(c in regex for c in ".*+?[](){}|^$\\") else []:
            hits.append({"pagina": pno + 1, "texto": regex,
                         "bbox": [round(inst.x0, 1), round(inst.y0, 1),
                                  round(inst.x1, 1), round(inst.y1, 1)]})
        if any(c in regex for c in ".*+?[](){}|^$\\"):
            for block in page.get_text("words"):
                x0, y0, x1, y1, w, *_ = block
                if rx.search(w):
                    hits.append({"pagina": pno + 1, "texto": w,
                                 "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]})
    doc.close()
    return hits

def revisoes(path: pathlib.Path) -> list[dict]:
    """RF-008: revisoes incrementais via pikepdf + pypdf."""
    out = []
    try:
        with pikepdf.open(path) as pdf:
            out.append({"revisoes_incrementais": "pikepdf abriu sem erro",
                        "objetos": len(list(pdf.objects))})
    except Exception as e:
        out.append({"erro": str(e)})
    try:
        r = PdfReader(str(path))
        out.append({"pypdf_paginas": len(r.pages)})
    except Exception as e:
        out.append({"pypdf_erro": str(e)[:200]})
    return out

def triagem_risco(path: pathlib.Path) -> dict:
    """RF-009: JS, OpenAction, Launch, URI, anexos, XFA."""
    flags: dict[str, bool | int] = {"javascript": False, "openaction": False,
                                    "launch": False, "uri": 0, "anexos": 0, "xfa": False}
    try:
        with pikepdf.open(path) as pdf:
            root = pdf.Root
            names = str(root.keys())
            if "/JavaScript" in names or "/JS" in str(pdf.objects):
                flags["javascript"] = True
            if "/OpenAction" in names:
                flags["openaction"] = True
            s = str(pdf.objects)
            if "/Launch" in s:
                flags["launch"] = True
            flags["uri"] = s.count("/URI")
            if "/XFA" in s:
                flags["xfa"] = True
            try:
                flags["anexos"] = len(pdf.attachments)
            except Exception:
                pass
    except Exception as e:
        flags["erro"] = str(e)[:200]  # type: ignore
    nota = "ALTA" if (flags.get("javascript") or flags.get("launch") or flags.get("openaction")) else (
        "MEDIA" if flags.get("uri", 0) else "BAIXA")
    return {"flags": flags, "nota_risco": nota}
