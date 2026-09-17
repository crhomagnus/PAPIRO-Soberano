# -*- coding: utf-8 -*-
"""RF-607 - comparar versoes: texto (difflib), estrutura (pikepdf/PyMuPDF) e visual (SSIM OpenCV),
com PDF marcado nas regioes alteradas."""
from __future__ import annotations
import difflib, pathlib
import fitz, numpy as np
from .. import fidelidade as FID
from .inspect import abrir, fontes, inventario


def diff_texto(a: pathlib.Path, b: pathlib.Path) -> dict:
    with abrir(a) as da, abrir(b) as db:
        la = [f"[p{p.number + 1}] {ln}" for p in da for ln in p.get_text(sort=True).splitlines() if ln.strip()]
        lb = [f"[p{p.number + 1}] {ln}" for p in db for ln in p.get_text(sort=True).splitlines() if ln.strip()]
    sa = [x.split("] ", 1)[1] for x in la]
    sb = [x.split("] ", 1)[1] for x in lb]
    diff = list(difflib.unified_diff(sa, sb, lineterm="", n=1))
    removidas = [ln[1:] for ln in diff if ln.startswith("-") and not ln.startswith("---")]
    adicionadas = [ln[1:] for ln in diff if ln.startswith("+") and not ln.startswith("+++")]
    return {"linhas_removidas": len(removidas), "linhas_adicionadas": len(adicionadas),
            "linhas_diff": len(removidas) + len(adicionadas), "amostra": diff[:80]}


def diff_estrutura(a: pathlib.Path, b: pathlib.Path) -> list[dict]:
    ia, ib = inventario(a), inventario(b)
    mudancas = []
    for chave in ("paginas", "versao_pdf", "titulo", "autor", "idioma", "marcado_tags", "tem_acroform",
                  "camadas_ocg", "anexos", "assinaturas_detectadas", "pdfa_declarado"):
        if ia.get(chave) != ib.get(chave):
            mudancas.append({"item": chave, "antes": ia.get(chave), "depois": ib.get(chave)})
    with fitz.open(a) as da, fitz.open(b) as db:
        ta, tb = da.get_toc(), db.get_toc()
        if ta != tb:
            mudancas.append({"item": "marcadores", "antes": len(ta), "depois": len(tb)})
        for i in range(min(da.page_count, db.page_count)):
            if tuple(da[i].rect) != tuple(db[i].rect) or da[i].rotation != db[i].rotation:
                mudancas.append({"item": f"pagina {i + 1} tamanho/rotacao",
                                 "antes": [list(da[i].rect), da[i].rotation], "depois": [list(db[i].rect), db[i].rotation]})
    fa = {f["nome"].split("+")[-1] for f in fontes(a)}
    fb = {f["nome"].split("+")[-1] for f in fontes(b)}
    if fa != fb:
        mudancas.append({"item": "fontes", "removidas": sorted(fa - fb), "adicionadas": sorted(fb - fa)})
    return mudancas


def marcar_visual(a: pathlib.Path, b: pathlib.Path, out_pdf: pathlib.Path, dpi: int = 100) -> dict:
    """Copia de B com retangulos vermelhos onde a renderizacao difere de A."""
    import cv2
    regioes = {}
    with fitz.open(a) as da, fitz.open(b) as db:
        for i in range(min(da.page_count, db.page_count)):
            ga, gb = FID.render_cinza(da[i], dpi), FID.render_cinza(db[i], dpi)
            if ga.shape != gb.shape:
                regioes[i + 1] = [tuple(db[i].rect)]
                continue
            dif = cv2.absdiff(ga, gb)
            _, mascara = cv2.threshold(dif, 40, 255, cv2.THRESH_BINARY)
            mascara = cv2.dilate(mascara, np.ones((9, 9), np.uint8))
            contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            escala = 72 / dpi
            caixas = []
            for c in contornos:
                x, y, w, h = cv2.boundingRect(c)
                if w * h >= 16:
                    caixas.append((x * escala, y * escala, (x + w) * escala, (y + h) * escala))
            if caixas:
                regioes[i + 1] = caixas
                page = db[i]
                shape = page.new_shape()
                for cx in caixas:
                    shape.draw_rect(fitz.Rect(cx))
                shape.finish(color=(1, 0, 0), width=1.2)
                shape.commit()
        db.save(out_pdf, garbage=3, deflate=True)
    return {"paginas_com_diferenca": sorted(regioes), "regioes": sum(len(v) for v in regioes.values())}


def comparar(a: pathlib.Path, b: pathlib.Path, out_pdf: pathlib.Path, dpi: int = 100) -> dict:
    visual = FID.comparar(a, b, dpi=72)
    marcas = marcar_visual(a, b, out_pdf, dpi)
    texto = diff_texto(a, b)
    estrutura = diff_estrutura(a, b)
    identicos = texto["linhas_diff"] == 0 and not estrutura and not marcas["paginas_com_diferenca"]
    return {"identicos": identicos, "texto": texto, "estrutura": estrutura, "visual": visual, "marcas": marcas}


def fidelidade_ssim(a: pathlib.Path, b: pathlib.Path, dpi: int = 72) -> dict:
    """Compatibilidade: SSIM real (OpenCV) no lugar da diferenca media de pixels da v1.0."""
    return FID.comparar(a, b, dpi=dpi)
