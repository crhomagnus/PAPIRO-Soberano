# -*- coding: utf-8 -*-
"""Suite fumaca PAPIRO §14.3 - 20 testes rapidos."""
import pathlib, json
import fitz

ROOT = pathlib.Path(r"C:\PAPIRO")
import sys
sys.path.insert(0, str(ROOT / "core"))
from papiro_core.adapters import inspect as INS, pages as PAG, edit as ED, create as CRE
from papiro_core.adapters import convert as CONV, intel as INTEL
from papiro_core.adapters import qa as QA, compare as CMP
from papiro_core import jobs as JOBS, engines as ENG

WORK = ROOT / "work" / "_fumaca"
WORK.mkdir(parents=True, exist_ok=True)

def pdf_base(p: pathlib.Path, texto="PAPIRO fumaca"):
    d = fitz.open()
    pg = d.new_page()
    pg.insert_text((72, 72), texto)
    d.save(p)
    d.close()
    return p

def test_01_inventario():
    p = pdf_base(WORK / "t01.pdf")
    assert INS.inventario(p)["paginas"] == 1

def test_02_fontes():
    assert isinstance(INS.fontes(WORK / "t01.pdf"), list)

def test_03_imagens_vazio():
    assert INS.imagens(WORK / "t01.pdf") == []

def test_04_classe_digital():
    c = INS.classifica_paginas(WORK / "t01.pdf")
    assert c[0]["classe"] in ("digital", "hibrida")

def test_05_busca():
    assert INS.busca(WORK / "t01.pdf", "PAPIRO")

def test_06_risco_baixa():
    assert INS.triagem_risco(WORK / "t01.pdf")["nota_risco"] == "BAIXA"

def test_07_merge():
    a = pdf_base(WORK / "a.pdf", "doc A")
    b = pdf_base(WORK / "b.pdf", "doc B")
    out = WORK / "merge.pdf"
    assert PAG.merge([a, b], out)["paginas"] == 2

def test_08_split():
    outs = PAG.split(WORK / "merge.pdf", WORK, ["1-1", "2-2"])
    assert len(outs) == 2

def test_09_girar():
    out = WORK / "rot.pdf"
    assert PAG.girar(WORK / "t01.pdf", out, [1], 90) == 1

def test_10_carimbo():
    out = WORK / "stamp.pdf"
    assert ED.carimbo(WORK / "t01.pdf", out, "CARIMBO")["paginas"] == 1

def test_11_replace():
    out = WORK / "rep.pdf"
    assert ED.substituir_texto(WORK / "t01.pdf", out, "fumaca", "OK")["trocas"] >= 1

def test_12_metadados():
    out = WORK / "meta.pdf"
    assert ED.metadados(WORK / "t01.pdf", out, titulo="T", autor="PAPIRO")["ok"]

def test_13_markdown_pdf():
    out = WORK / "md.pdf"
    assert CRE.markdown_para_pdf("# Oi\n\nteste", out, "T")["ok"]

def test_14_txt():
    out = WORK / "t.txt"
    assert CONV.para_texto(WORK / "t01.pdf", out)["paginas"] == 1

def test_15_qa_aprova_base():
    out = WORK / "qa.pdf"
    ED.metadados(WORK / "t01.pdf", out, titulo="QA", autor="PAPIRO")
    qa = QA.run(out)
    assert qa["portoes"]["G1"]["ok"] and qa["portoes"]["G2"]["ok"] and qa["portoes"]["G4"]["ok"]

def test_16_diff_identico():
    d = CMP.diff_texto(WORK / "t01.pdf", WORK / "t01.pdf")
    assert d["linhas_diff"] == 0

def test_17_ssim_identico():
    s = CMP.fidelidade_ssim(WORK / "t01.pdf", WORK / "t01.pdf")
    assert s["ssim_medio"] >= 0.99

def test_18_receita_valida():
    import yaml
    rec = yaml.safe_load((ROOT / "recipes" / "exemplo-receituario-assinado.yaml").read_text(encoding="utf-8"))
    assert JOBS.validar_receita(rec) == []

def test_19_engines():
    st = ENG.status()
    assert st["libs"].get("pymupdf") and st["libs"].get("pikepdf")

def test_20_tarja_real():
    out = WORK / "tar.pdf"
    r = ED.tarjar(WORK / "t01.pdf", out, [{"pagina": 1, "x0": 70, "y0": 60, "x1": 200, "y1": 90}])
    assert r["tarjas"] == 1 and r["verificado"]
