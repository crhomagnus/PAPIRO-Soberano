# -*- coding: utf-8 -*-
"""Fidelidade visual (G11, RF-607, RF-902): SSIM de Wang et al. (2004) com janela gaussiana 11x11,
sigma 1,5, via OpenCV. Mede media e pior bloco por pagina - a media sozinha e cega a uma linha
de texto trocada numa pagina quase toda branca."""
from __future__ import annotations
import pathlib
import numpy as np
import fitz


def render_cinza(page: fitz.Page, dpi: int = 72) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def ssim_mapa(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    import cv2
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    k, s = (11, 11), 1.5
    mu_a, mu_b = cv2.GaussianBlur(a, k, s), cv2.GaussianBlur(b, k, s)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    s_a2 = cv2.GaussianBlur(a * a, k, s) - mu_a2
    s_b2 = cv2.GaussianBlur(b * b, k, s) - mu_b2
    s_ab = cv2.GaussianBlur(a * b, k, s) - mu_ab
    return ((2 * mu_ab + c1) * (2 * s_ab + c2)) / ((mu_a2 + mu_b2 + c1) * (s_a2 + s_b2 + c2))


def ssim_pagina(a: np.ndarray, b: np.ndarray, grade: int = 8) -> tuple[float, float]:
    """(media, pior bloco) - blocos de uma grade grade x grade."""
    if a.shape != b.shape:
        return 0.0, 0.0
    m = ssim_mapa(a, b)
    h, w = m.shape
    piores = []
    for i in range(grade):
        for j in range(grade):
            bloco = m[i * h // grade:(i + 1) * h // grade, j * w // grade:(j + 1) * w // grade]
            if bloco.size:
                piores.append(float(bloco.mean()))
    return float(m.mean()), float(min(piores) if piores else m.mean())


def comparar(a: pathlib.Path, b: pathlib.Path, dpi: int = 72, grade: int = 8) -> dict:
    with fitz.open(a) as da, fitz.open(b) as db:
        n = min(da.page_count, db.page_count)
        paginas = []
        for i in range(n):
            media, pior = ssim_pagina(render_cinza(da[i], dpi), render_cinza(db[i], dpi), grade)
            paginas.append({"pagina": i + 1, "ssim": round(media, 4), "ssim_pior_bloco": round(pior, 4)})
        mesmas = da.page_count == db.page_count
        return {"paginas_a": da.page_count, "paginas_b": db.page_count, "mesmo_numero_paginas": mesmas,
                "ssim_medio": round(sum(p["ssim"] for p in paginas) / max(n, 1), 4) if mesmas else 0.0,
                "ssim_pior_bloco": round(min((p["ssim_pior_bloco"] for p in paginas), default=0.0), 4) if mesmas else 0.0,
                "por_pagina": paginas, "dpi": dpi}


def texto_normalizado(p: pathlib.Path) -> list[str]:
    with fitz.open(p) as d:
        return " ".join(pg.get_text() for pg in d).split()


def similaridade_texto(a: pathlib.Path, b: pathlib.Path) -> float:
    """Sobreposicao de multiconjunto de palavras (1,0 = mesmo texto)."""
    from collections import Counter
    ca, cb = Counter(texto_normalizado(a)), Counter(texto_normalizado(b))
    total = max(sum(ca.values()), sum(cb.values()))
    if total == 0:
        return 1.0
    return sum((ca & cb).values()) / total
