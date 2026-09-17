# -*- coding: utf-8 -*-
"""Servidor papiro-seguranca (§8.4, §12), CLI (ADR-01) e nucleo (caminhos, config, jobs, roteador, binfinder)."""
import json, os, pathlib
import fitz, pikepdf
import pytest
from typer.testing import CliRunner
from papiro_core import caminhos as CAM, cli, config, engines as ENG, jobs as JOBS, mcp_seguranca as S, roteador as ROT
from papiro_core import binfinder as BF
from papiro_core.erros import PapiroErro, err
from papiro_core.runner import versao_motor
from conftest import CORPUS, envelope_ok


def ok(env):
    envelope_ok(env)
    assert env["ok"], json.dumps(env, ensure_ascii=False, default=str)[:800]
    return env


# ---------- seguranca ----------
def test_dez_ferramentas():
    assert {t.name for t in S.mcp._tool_manager.list_tools()} == set(
        "sign certify timestamp ltv_update verify encrypt decrypt redact_detect redact_apply sanitize".split())


def test_sensivel_exige_confirmacao(pdf_bom, pfx_teste, out_dir):
    for env in (S.sanitize(str(pdf_bom), out_dir), S.encrypt(str(pdf_bom), out_dir),
                S.decrypt(str(pdf_bom), out_dir, senha="x"), S.redact_apply(str(pdf_bom), out_dir, caixas_json="[]"),
                S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="env:PAPIRO_TESTE_PFX_SENHA"),
                S.timestamp(str(pdf_bom), out_dir), S.ltv_update(str(pdf_bom), out_dir)):
        assert envelope_ok(env)["error"]["code"] == "E_POLITICA"


def test_assinar_verificar_e_travas(pdf_bom, pdf_helv, pfx_teste, out_dir):
    ref = "env:PAPIRO_TESTE_PFX_SENHA"
    e = ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref=ref, confirm=True, visivel=True,
                  caixa="40,40,220,100", crm="00000-RS"))
    ass = pathlib.Path(e["outputs"][0]["path"])
    v = e["dados"]["verificacao"][0]
    assert v["intacta"] and v["valida"] and v["confiavel"] is False and "Teste PAPIRO" in v["signatario"]
    vv = ok(S.verify(str(ass), out_dir))["dados"]["assinaturas"]
    assert vv[0]["cobertura"] in ("ENTIRE_FILE", "ENTIRE_REVISION")
    ok(S.certify(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref=ref, confirm=True))
    # reprovado nos portoes nao assina
    assert envelope_ok(S.sign(str(pdf_helv), out_dir, pfx=str(pfx_teste), senha_ref=ref, confirm=True))["error"]["code"] == "E_POLITICA"
    # aparencia sobre o conteudo e proibida
    assert envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref=ref, confirm=True, visivel=True,
                              caixa="60,700,400,780"))["error"]["code"] == "E_POLITICA"
    # senha nunca como argumento direto
    assert envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="senha-de-teste",
                              confirm=True))["error"]["code"] == "E_POLITICA"
    assert envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="env:NAO_EXISTE",
                              confirm=True))["error"]["code"] == "E_SENHA"
    assert ok(S.verify(str(pdf_bom), out_dir))["warnings"] == ["documento sem assinaturas"]
    # carimbo do tempo existe (test_carimbo_tsa.py); sem TSA configurada, ele pede a TSA
    assert envelope_ok(S.timestamp(str(pdf_bom), out_dir, confirm=True))["error"]["code"] == "E_ENTRADA"
    assert envelope_ok(S.ltv_update(str(pdf_bom), out_dir, confirm=True))["error"]["code"] == "E_SEM_SUPORTE"


def test_encrypt_decrypt(pdf_bom, out_dir):
    e = ok(S.encrypt(str(pdf_bom), out_dir, confirm=True))
    senha = e["dados"]["senha"]
    enc = pathlib.Path(e["outputs"][0]["path"])
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(enc)
    with pikepdf.open(enc, password=senha) as pdf:
        assert pdf.encryption.bits == 256
    from papiro_core.audit import AUDIT
    assert senha not in AUDIT.read_text(encoding="utf-8")
    ok(S.decrypt(str(enc), out_dir, senha=senha, confirm=True))
    assert envelope_ok(S.decrypt(str(enc), out_dir, senha="errada", confirm=True))["error"]["code"] == "E_SENHA"
    os.environ["PAPIRO_TESTE_SENHA_PDF"] = "Minha-senha-1"
    e = ok(S.encrypt(str(pdf_bom), out_dir, confirm=True, senha_ref="env:PAPIRO_TESTE_SENHA_PDF"))
    assert e["dados"]["senha"] is None


def test_tarja_fluxo_completo(pdf_cpf, out_dir):
    d = ok(S.redact_detect(str(pdf_cpf), out_dir))
    assert "CPF" in d["dados"]["categorias"]
    caixas = next(pathlib.Path(o["path"]) for o in d["outputs"] if o["path"].endswith(".json"))
    aprovadas = [c for c in json.loads(caixas.read_text(encoding="utf-8")) if c["categoria"] == "CPF"]
    arq = CORPUS / "aprovadas.json"
    arq.write_text(json.dumps(aprovadas), encoding="utf-8")
    e = ok(S.redact_apply(str(pdf_cpf), out_dir, confirm=True, caixas_arquivo=str(arq), saida="joana_529.982.247-25.pdf"))
    assert e["outputs"][0]["path"].endswith("tarjado.pdf") and e["warnings"]
    with fitz.open(e["outputs"][0]["path"]) as doc:
        assert "529.982" not in doc[0].get_text()


def test_sanitize_confirmado(pdf_malicioso, out_dir):
    assert ok(S.sanitize(str(pdf_malicioso), out_dir, confirm=True))["dados"]["triagem_depois"] == "BAIXA"


# ---------- CLI ----------
def test_cli(pdf_bom, pdf_textos, out_dir):
    r = CliRunner()
    assert r.invoke(cli.app, ["status"]).exit_code == 0
    lista = r.invoke(cli.app, ["ferramentas"]).output.split()
    assert len(lista) == 48 and "seguranca.sign" in lista
    res = r.invoke(cli.app, ["chamar", "inspect", json.dumps({"op": "risk", "entrada": str(pdf_bom), "out_dir": out_dir})])
    assert res.exit_code == 0 and json.loads(res.output)["ok"]
    assert r.invoke(cli.app, ["chamar", "nao-existe"]).exit_code == 2
    assert r.invoke(cli.app, ["chamar", "engines", "{json ruim"]).exit_code == 2
    assert r.invoke(cli.app, ["inspecionar", str(pdf_bom), "--out-dir", out_dir]).exit_code == 0
    assert r.invoke(cli.app, ["qa", str(pdf_bom), "--out-dir", out_dir]).exit_code == 0
    assert r.invoke(cli.app, ["qa", str(pdf_textos[0]), "--out-dir", out_dir]).exit_code == 1
    assert r.invoke(cli.app, ["comparar", str(pdf_textos[0]), str(pdf_textos[1]), "--out-dir", out_dir]).exit_code == 0
    md = CORPUS / "cli.md"
    md.write_text("# CLI\n\nTexto.", encoding="utf-8")
    assert r.invoke(cli.app, ["criar", str(md), "--out-dir", out_dir]).exit_code == 0
    assert r.invoke(cli.app, ["otimizar", str(pdf_bom), "--out-dir", out_dir, "--perfil", "tela"]).exit_code in (0, 1)
    assert r.invoke(cli.app, ["ocr", str(pdf_bom), "--out-dir", out_dir]).exit_code == 0
    assert r.invoke(cli.app, ["inspecionar", str(pdf_bom)]).exit_code == 0   # out_dir padrao: out/<data>


# ---------- nucleo ----------
def test_caminhos(tmp_path):
    assert CAM.nome_seguro("../../a/b\\c.pdf") == "c.pdf"
    assert CAM.nome_seguro("..") == "arquivo"
    assert CAM.nome_seguro('a<b>:"c|?.pdf') == "a_b___c__.pdf"
    with pytest.raises(PapiroErro):
        CAM.validar_entrada("")
    with pytest.raises(PapiroErro):
        CAM.validar_out_dir("")
    os.environ["PAPIRO_PASTAS_LIBERADAS"] = str(tmp_path)
    try:
        f = tmp_path / "x.pdf"
        f.write_bytes(b"%PDF")
        assert CAM.validar_entrada(str(f)) == f.resolve()
    finally:
        os.environ.pop("PAPIRO_PASTAS_LIBERADAS")


def test_config_erros_versoes():
    assert config.perfil() == "P0"
    assert config.qa("limiar_ssim") == 0.95 and config.jobs("timeout_motor_s") > 0
    assert err("E_MOTOR")["message"] == "Motor falhou"
    with pytest.raises(ValueError):
        PapiroErro("E_INEXISTENTE")
    assert versao_motor("pymupdf+pikepdf").startswith("pymupdf ")
    assert versao_motor("regex-pii") is None
    assert ENG.perfil_hardware() in ("P0", "P1", "P2")
    assert "por" in ENG.tesseract_idiomas()


def test_jobs_e_roteador():
    jid = JOBS.novo_job_id()
    JOBS.job_criar(jid, "teste", "op", {"x": 1})
    assert JOBS.job_cancelar(jid)["status"] == "cancelado"
    JOBS.passo_salvar("exec1", "p1", "ok", "chave1", {"saida": "a.pdf"})
    assert JOBS.passo_ler("exec1", "p1")["saida"]["saida"] == "a.pdf"
    assert JOBS.cache_buscar("chave1") == {"saida": "a.pdf"} and JOBS.passo_ler("exec1", "p2") is None
    assert JOBS.taxa_motor("tarefa-nova", "motor-novo") == 0.8
    for _ in range(5):
        JOBS.stat_motor("tarefa-x", "ruim", False)
    assert JOBS.taxa_motor("tarefa-x", "ruim") < 0.5
    assert ROT.classificar("Preciso tarjar o CPF") == "tarjamento"
    assert ROT.classificar("algo sem palavra-chave") == "inspecao"
    assert ROT.classificar("Criar um RELATÓRIO") == "criacao"
    prim, fb = ROT.escolher_motor("criacao")
    assert prim == "typst" and fb == "pymupdf-story"
    todos = ROT.ranquear("ocr_estrutural", so_disponiveis=False)
    assert {m["motor"] for m in todos} == {"docling", "paddleocr-vl"} and not any(m["disponivel"] for m in todos)


def test_binfinder():
    assert BF.qual("typst") and BF.qual("qpdf") and BF.ghostscript()
    assert BF.qual("programa-que-nao-existe-123") is None
    with pytest.raises(PapiroErro) as e:
        BF.rodar(["programa-que-nao-existe-123"])
    assert e.value.codigo == "E_SEM_SUPORTE"
    with pytest.raises(PapiroErro) as e:
        BF.rodar(["sleep", "5"], timeout=0.5)
    assert e.value.codigo == "E_TEMPO"
    with pytest.raises(PapiroErro) as e:
        BF.rodar(["false"])
    assert e.value.codigo == "E_MOTOR"
    assert "PATH" in BF.env_extra()
