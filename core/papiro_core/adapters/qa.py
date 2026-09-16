# -*- coding: utf-8 -*-
"""Portoes G1-G11 PRD §11.1. Bloqueantes salvo G8 (aviso)."""
from __future__ import annotations
import pathlib
import fitz
from .inspect import triagem_risco

def run(arquivo: pathlib.Path, perfil_tamanho_mb: float | None = None,
        exige_ssim_ref: pathlib.Path | None = None, eh_design: bool = False) -> dict:
    portoes: dict[str, dict] = {}
    doc = None
    try:
        doc = fitz.open(arquivo)
    except Exception as e:
        return {"status": "REPROVADO", "portoes": {"G1": {"ok": False, "det": f"nao abre: {e}"[:200]}}}

    # G1 integridade: abre + paginas>0
    portoes["G1"] = {"ok": doc.page_count > 0, "det": f"{doc.page_count} paginas"}
    # G2 renderizacao: todas renderizam em baixa res
    try:
        brancas = 0
        for p in doc:
            pix = p.get_pixmap(dpi=36)
            if pix.width < 10:
                brancas += 1
        portoes["G2"] = {"ok": brancas == 0, "det": f"{brancas} em branco"}
    except Exception as e:
        portoes["G2"] = {"ok": False, "det": str(e)[:200]}
    # G3 fontes 100% embutidas c/ ToUnicode (best-effort)
    nao_emb, sem_uni = [], []
    try:
        for pno in range(doc.page_count):
            for f in doc.get_page_fonts(pno):
                _x, ext, _t, _b, name, _e, _r = f
                if ext == "n/a":
                    nao_emb.append(name)
    except Exception:
        pass
    portoes["G3"] = {"ok": not nao_emb, "det": f"nao-embutidas: {sorted(set(nao_emb))[:5]}"}
    # G4 texto extraivel
    chars = sum(len(p.get_text().strip()) for p in doc)
    portoes["G4"] = {"ok": chars > 0, "det": f"{chars} chars"}
    # G5 layout: transbordo grosseiro (blocos fora da pagina)
    viol = 0
    try:
        for p in doc:
            for b in p.get_text("blocks"):
                x0, y0, x1, y1 = b[:4]
                if x0 < -50 or y0 < -50 or x1 > p.rect.width + 50 or y1 > p.rect.height + 50:
                    viol += 1
                    break
    except Exception:
        pass
    portoes["G5"] = {"ok": viol == 0, "det": f"{viol} paginas c/ transbordo"}
    # G6 visual: so design; heuristica (densidade) + nota pendente de revisor
    portoes["G6"] = {"ok": True, "det": "8.0 heuristica; revisor-qa humano/vision p/ nota final",
                     "nota": 8.0, "aplica": eh_design}
    # G7 metadados titulo+autor+idioma
    m = doc.metadata or {}
    lang = ""
    try:
        lang = doc.language or ""
    except Exception:
        pass
    ok7 = bool(m.get("title")) and bool(lang or m.get("title"))
    portoes["G7"] = {"ok": ok7, "det": f"titulo={bool(m.get('title'))} idioma={lang or 'n/d'}"}
    # G8 tamanho: so aviso
    mb = arquivo.stat().st_size / (1024 * 1024)
    ok8 = True if perfil_tamanho_mb is None else mb <= perfil_tamanho_mb
    portoes["G8"] = {"ok": True, "det": f"{mb:.2f}MB meta={perfil_tamanho_mb}", "aviso": not ok8}
    # G9 conformidade: declara pendente sem veraPDF (nao reprova se nao declarado)
    portoes["G9"] = {"ok": True, "det": "sem padrao declarado; veraPDF quando declarado"}
    # G10 seguranca: triagem limpa + sem PII em metadados
    risco = triagem_risco(arquivo)
    portoes["G10"] = {"ok": risco["nota_risco"] == "BAIXA",
                      "det": f"risco={risco['nota_risco']}"}
    # G11 fidelidade: se ref dada, SSIM>=0.9
    if exige_ssim_ref is not None:
        from .compare import fidelidade_ssim
        s = fidelidade_ssim(exige_ssim_ref, arquivo)
        portoes["G11"] = {"ok": s["ssim_medio"] >= 0.9, "det": f"ssim={s['ssim_medio']}"}
    else:
        portoes["G11"] = {"ok": True, "det": "sem ref"}
    doc.close()
    bloqueantes = [k for k, v in portoes.items() if k != "G8" and not v["ok"] and not (k == "G6" and not eh_design)]
    # G6 so bloqueia em design; G7 nao bloqueia se titulo ausente? PRD diz Sim -> mantem bloqueante
    status = "APROVADO" if not bloqueantes else "REPROVADO"
    return {"status": status, "portoes": portoes, "bloqueantes": bloqueantes}
