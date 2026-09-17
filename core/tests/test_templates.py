# -*- coding: utf-8 -*-
"""RF-307: 16 templates Typst, cada um com exemplo, portoes de QA e teste visual contra referencia.png."""
import json, pathlib, shutil
import fitz, numpy as np
import pytest
from PIL import Image
from papiro_core import fidelidade as FID, mcp_server as M, templates as TP
from papiro_core.adapters import qa as QA
from papiro_core.erros import PapiroErro
from conftest import CORPUS, envelope_ok

RF307 = {"relatorio", "proposta", "contrato", "certificado", "catalogo", "apostila", "ebook", "one-pager", "cardapio",
         "cartao", "folder", "cartaz", "receituario", "atestado", "pedido-exame", "encaminhamento"}
IDS = [t["id"] for t in TP.listar()]


def test_biblioteca_tem_os_16_do_prd():
    assert len(IDS) == 16
    nomes = {i.split("/")[-1] for i in IDS}
    for exigido in RF307:
        assert any(n.startswith(exigido) for n in nomes), exigido


@pytest.mark.parametrize("tid", IDS)
def test_template_exemplo_qa_e_visual(tid, tmp_path):
    m = TP.meta(tid)
    out = tmp_path / "t.pdf"
    r = TP.renderizar(tid, TP.exemplo(tid), out)
    assert r["paginas"] >= 1
    padrao = ",".join("PDF/" + p.upper() for p in r["padroes"]) or None
    q = QA.run(out, eh_design=bool(m.get("design")), padrao=padrao)
    if m.get("design"):
        assert q["status"] == "PENDENTE_REVISAO" and q["bloqueantes"] == ["G6"], q["bloqueantes"]
    else:
        assert q["status"] == "APROVADO", {k: v.get("det") for k, v in q["portoes"].items() if not v["ok"]}
    with fitz.open(out) as d:
        pix = d[0].get_pixmap(dpi=36, colorspace=fitz.csGRAY)
        atual = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    referencia = np.asarray(Image.open(TP.TEMPLATES / tid / "referencia.png").convert("L"))
    media, pior = FID.ssim_pagina(atual, referencia)
    assert pior >= 0.98, f"{tid}: layout mudou (SSIM pior bloco {pior:.3f}); revise e regenere referencia.png"


def test_medicos_declaram_pdfa_e_pdfua():
    for tid in IDS:
        if tid.startswith("medico/"):
            assert TP.meta(tid)["padroes"] == ["a-2b", "ua-1"] and TP.meta(tid)["sensivel"] is True


def test_travas_legais_dos_schemas(tmp_path):
    casos = [("atestado", {**TP.exemplo("atestado"), "diagnostico": {"cid": "J06.9"}}, "autorizacao_diagnostico"),
             ("atestado", {**TP.exemplo("atestado"), "paciente": {"nome": "Z"}}, "documento"),
             ("receituario", {**TP.exemplo("receituario"), "tipo": "controle_especial",
                              "itens": [{"medicamento": "X", "posologia": "Y"}]}, "quantidade"),
             ("receituario", {**TP.exemplo("receituario"), "medico": {"nome": "A", "crm": "12a", "uf": "RS"}}, "crm")]
    for tid, dados, termo in casos:
        with pytest.raises(PapiroErro) as e:
            TP.renderizar(tid, dados, tmp_path / "x.pdf")
        assert e.value.codigo == "E_ENTRADA" and termo in e.value.mensagem


def test_controle_especial_duas_vias_e_extenso(tmp_path):
    dados = {**TP.exemplo("receituario"), "tipo": "controle_especial",
             "itens": [{"medicamento": "Medicamento fictício", "posologia": "1 à noite", "quantidade": 2, "unidade": "caixas"}]}
    out = tmp_path / "ce.pdf"
    assert TP.renderizar("receituario", dados, out)["paginas"] == 2
    with fitz.open(out) as d:
        p1, p2 = (" ".join(d[i].get_text().split()) for i in (0, 1))
    assert "1ª via – Retenção da Farmácia ou Drogaria" in p1 and "2ª via – Orientação ao Paciente" in p2
    assert "duas caixas" in p1 and "identificação do comprador" in p1.lower()
    assert QA.run(out, padrao="PDF/A-2b,PDF/UA-1")["status"] == "APROVADO"


def test_atestado_diagnostico_autorizado_e_comparecimento(tmp_path):
    com = {**TP.exemplo("atestado"), "diagnostico": {"cid": "J06.9", "descricao": "exemplo"}, "autorizacao_diagnostico": True}
    TP.renderizar("atestado", com, tmp_path / "a.pdf")
    assert "concordância expressa" in fitz.open(tmp_path / "a.pdf")[0].get_text()
    comp = {**TP.exemplo("atestado"), "dias": 0, "horario": "das 14h00 às 15h00"}
    TP.renderizar("atestado", comp, tmp_path / "b.pdf")
    texto = " ".join(fitz.open(tmp_path / "b.pdf")[0].get_text().split())
    assert "compareceu a atendimento médico" in texto and "afastamento" not in texto


def test_por_extenso():
    casos = {(1, True): "uma", (2, True): "duas", (10, False): "dez", (21, True): "vinte e uma", (100, False): "cem",
             (101, False): "cento e um", (215, True): "duzentas e quinze", (1000, False): "mil", (1100, False): "mil e cem",
             (2001, True): "duas mil e uma", (1234, False): "mil duzentos e trinta e quatro", (0, False): "zero"}
    for (n, fem), esperado in casos.items():
        assert TP.por_extenso(n, fem) == esperado
    with pytest.raises(PapiroErro):
        TP.por_extenso(1_000_000)


def test_resolver_ids():
    assert TP.resolver("receituario").name == "receituario-a5"
    assert TP.resolver("medico/atestado-a5").name == "atestado-a5"
    for ruim in ("nao-existe", "../docs", ""):
        with pytest.raises(PapiroErro):
            TP.resolver(ruim)


def test_fonte_do_brandkit_ausente_e_erro(tmp_path, monkeypatch):
    kits = tmp_path / "brandkits"
    shutil.copytree(TP.BRANDKITS / "padrao", kits / "inexistente")
    tokens = (kits / "inexistente" / "tokens.yaml").read_text(encoding="utf-8").replace("Liberation Sans", "Inter")
    (kits / "inexistente" / "tokens.yaml").write_text(tokens, encoding="utf-8")
    monkeypatch.setattr(TP, "BRANDKITS", kits)
    with pytest.raises(PapiroErro) as e:
        TP.renderizar("proposta", TP.exemplo("proposta"), tmp_path / "p.pdf", marca="inexistente")
    assert "inter" in e.value.mensagem.lower()
    with pytest.raises(PapiroErro):
        TP.renderizar("proposta", TP.exemplo("proposta"), tmp_path / "p.pdf", marca="nenhuma")


def test_imagens_e_logos(png_scan, tmp_path):
    cat = TP.exemplo("catalogo")
    cat["logo"] = str(png_scan)
    cat["produtos"][0]["imagem"] = str(png_scan)
    out = tmp_path / "c.pdf"
    TP.renderizar("catalogo", cat, out)
    with fitz.open(out) as d:
        colocacoes = sum(len(d[0].get_image_rects(img[0])) for img in d[0].get_images())
    assert colocacoes >= 2      # logo + foto do produto (mesmo PNG vira um so objeto de imagem)
    cat["produtos"][0]["imagem"] = "/etc/hostname"
    with pytest.raises(PapiroErro) as e:
        TP.renderizar("catalogo", cat, out)
    assert e.value.codigo == "E_ENTRADA"


def test_mcp_compose_com_template(out_dir):
    e = envelope_ok(M.compose("auto", out_dir, template="atestado", usar_exemplo=True))
    assert e["ok"] and e["qa"]["status"] == "APROVADO" and e["dados"]["padroes"] == ["a-2b", "ua-1"]
    arq = CORPUS / "dados_proposta.json"
    arq.write_text(json.dumps(TP.exemplo("proposta")), encoding="utf-8")
    assert envelope_ok(M.compose("typst", out_dir, template="proposta", dados_arquivo=str(arq)))["ok"]
    e = envelope_ok(M.compose("auto", out_dir, template="cartaz-a3", usar_exemplo=True))
    assert e["qa"]["status"] == "PENDENTE_REVISAO"
    assert envelope_ok(M.compose("auto", out_dir, template="cartaz-a3", usar_exemplo=True, nota_visual=8.4))["ok"]
    assert envelope_ok(M.compose("html", out_dir, template="proposta", usar_exemplo=True))["error"]["code"] == "E_ENTRADA"
    assert envelope_ok(M.compose("auto", out_dir, template="proposta", dados_json="{ruim"))["error"]["code"] == "E_ENTRADA"
    assert len(json.loads(M.recurso_templates())) == 16 and json.loads(M.recurso_brandkits()) == ["padrao"]


def test_mcp_mail_merge_com_template(out_dir):
    base = TP.exemplo("certificado")
    registros = [dict(base, participante=n) for n in ("Ana", "Bruno", "Carla")]
    e = envelope_ok(M.mail_merge(out_dir, template="certificado", dados_json=json.dumps(registros),
                                 modo="um_por_registro", campo_nome="participante", qa=False))
    assert e["ok"] and e["dados"]["arquivos"] == 3
    assert {pathlib.Path(o["path"]).name for o in e["outputs"]} == {"Ana.pdf", "Bruno.pdf", "Carla.pdf"}
    e = envelope_ok(M.mail_merge(out_dir, template="atestado", dados_json=json.dumps([TP.exemplo("atestado")] * 5), qa=False))
    assert e["ok"] and e["outputs"][0]["pages"] == 5 and e["warnings"]
    ruins = [TP.exemplo("atestado"), {"medico": base}]
    e = envelope_ok(M.mail_merge(out_dir, template="atestado", dados_json=json.dumps(ruins)))
    assert e["error"]["code"] == "E_ENTRADA" and "registro 2" in e["error"]["message"]
    assert envelope_ok(M.mail_merge(out_dir, dados_json="[]"))["error"]["code"] == "E_ENTRADA"
