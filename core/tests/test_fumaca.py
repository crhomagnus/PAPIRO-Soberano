# -*- coding: utf-8 -*-
"""Suite de fumaca PAPIRO §14.3 - 20 testes rapidos, portavel (Windows e Linux, sem caminho fixo)."""
import fitz, yaml
from papiro_core import RECIPES, engines as ENG, jobs as JOBS, mcp_server as M
from papiro_core.adapters import compare as CMP, convert as CONV, create as CRE, edit as ED, inspect as INS
from papiro_core.adapters import pages as PAG, qa as QA


def test_01_inventario(pdf_helv):
    assert INS.inventario(pdf_helv)["paginas"] == 1


def test_02_fontes(pdf_helv):
    assert INS.fontes(pdf_helv)[0]["embutida"] is False


def test_03_imagens_vazio(pdf_helv):
    assert INS.imagens(pdf_helv) == []


def test_04_classe_digital(pdf_helv):
    assert INS.classifica_paginas(pdf_helv)[0]["classe"] == "digital"


def test_05_busca(pdf_helv):
    assert INS.busca(pdf_helv, "Helvetica")


def test_06_risco_baixa(pdf_helv):
    assert INS.triagem_risco(pdf_helv)["nota_risco"] == "BAIXA"


def test_07_merge(pdf_textos, tmp_path):
    assert PAG.merge(list(pdf_textos), tmp_path / "m.pdf")["paginas"] == 2


def test_08_split(pdf_textos, tmp_path):
    PAG.merge(list(pdf_textos), tmp_path / "m.pdf")
    assert len(PAG.split(tmp_path / "m.pdf", tmp_path, intervalos=["1", "2"])) == 2


def test_09_girar(pdf_helv, tmp_path):
    assert PAG.girar(pdf_helv, tmp_path / "r.pdf", [1], 90)["paginas_giradas"] == {1: 90}


def test_10_carimbo(pdf_helv, tmp_path):
    assert ED.carimbo(pdf_helv, tmp_path / "s.pdf", texto="CARIMBO")["paginas"] == 1


def test_11_replace(pdf_textos, tmp_path):
    assert ED.substituir_texto(pdf_textos[0], tmp_path / "r.pdf", "locacao", "aluguel")["trocas"] >= 1


def test_12_metadados(pdf_helv, tmp_path):
    assert ED.metadados(pdf_helv, tmp_path / "m.pdf", titulo="T", autor="PAPIRO")["ok"]


def test_13_markdown_pdf(tmp_path):
    assert CRE.markdown_para_pdf("# Oi\n\nteste", tmp_path / "md.pdf", "T")["paginas"] == 1


def test_14_txt(pdf_helv, tmp_path):
    assert CONV.para_texto(pdf_helv, tmp_path / "t.txt")["paginas"] == 1


def test_15_qa_aprova_documento_bom(pdf_bom):
    assert QA.run(pdf_bom)["status"] == "APROVADO"


def test_16_diff_identico(pdf_helv):
    assert CMP.diff_texto(pdf_helv, pdf_helv)["linhas_diff"] == 0


def test_17_ssim_identico(pdf_helv):
    assert CMP.fidelidade_ssim(pdf_helv, pdf_helv)["ssim_pior_bloco"] >= 0.99


def test_18_receita_valida(out_dir):
    env = M.recipes("validate", arquivo=str(RECIPES / "exemplo-receituario-assinado.yaml"))
    assert env["ok"] and env["dados"]["valida"], env
    assert yaml.safe_load((RECIPES / "exemplo-receituario-assinado.yaml").read_text(encoding="utf-8"))["passos"]


def test_19_engines():
    st = ENG.status()
    assert st["libs"]["pymupdf"] and st["libs"]["pikepdf"]


def test_20_tarja_real(pdf_cpf, tmp_path):
    r0 = fitz.open(pdf_cpf)[0].search_for("529.982.247-25")[0]
    r = ED.tarjar(pdf_cpf, tmp_path / "tar.pdf", [{"pagina": 1, "x0": r0.x0, "y0": r0.y0, "x1": r0.x1, "y1": r0.y1}])
    assert r["verificado"] and "529.982" not in fitz.open(tmp_path / "tar.pdf")[0].get_text()
    assert JOBS.novo_job_id() != JOBS.novo_job_id()
