# -*- coding: utf-8 -*-
"""RF-607 comparar + G11 fidelidade (SSIM aproximado via pixels)."""
from __future__ import annotations
import difflib, pathlib
import fitz

def diff_texto(a: pathlib.Path, b: pathlib.Path) -> dict:
    ta = fitz.open(a)
    tb = fitz.open(b)
    la = "\n".join(p.get_text() for p in ta).splitlines()
    lb = "\n".join(p.get_text() for p in tb).splitlines()
    ta.close(); tb.close()
    diff = list(difflib.unified_diff(la, lb, lineterm=""))
    return {"linhas_diff": len(diff), "amostra": diff[:60]}

def fidelidade_ssim(a: pathlib.Path, b: pathlib.Path, dpi: int = 72) -> dict:
    """Aproxima SSIM por diferenca media de pixels (0..1, 1=identico)."""
    from PIL import Image, ImageChops
    import io
    da, db = fitz.open(a), fitz.open(b)
    n = min(da.page_count, db.page_count)
    scores = []
    for i in range(n):
        pa = da[i].get_pixmap(dpi=dpi).tobytes("png")
        pb = db[i].get_pixmap(dpi=dpi).tobytes("png")
        ia = Image.open(io.BytesIO(pa)).convert("L")
        ib = Image.open(io.BytesIO(pb)).convert("L")
        if ia.size != ib.size:
            scores.append(0.0)
            continue
        h = ImageChops.difference(ia, ib).histogram()
        total = sum(h)
        media = sum(i * v for i, v in enumerate(h)) / max(total, 1)
        scores.append(round(max(0.0, 1 - media / 128.0), 4))
    da.close(); db.close()
    media = round(sum(scores) / max(len(scores), 1), 4)
    return {"paginas": n, "ssim_medio": media, "por_pagina": scores}
