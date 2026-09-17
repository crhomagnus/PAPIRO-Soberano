# -*- coding: utf-8 -*-
"""Regressao dos defeitos provados na varredura de 16/09/2026. Cada teste reproduz a prova original
e so passa com o defeito corrigido."""
import json, pathlib
import fitz, pikepdf
from papiro_core import fidelidade as FID, jobs as JOBS, mcp_server as M
from papiro_core.adapters import compare as CMP, convert as CONV, create as CRE, edit as ED, inspect as INS
from papiro_core.adapters import intel as INTEL, pages as PAG, pii as PII, qa as QA
from conftest import envelope_ok


# ---------- 1. otimizar destruia imagens ----------
def test_otimizar_nao_destroi_imagem_e_reduz(pdf_fotos, tmp_path):
    out = tmp_path / "ot.pdf"
    r = PAG.otimizar(pdf_fotos, out, "email")
    fid = FID.comparar(pdf_fotos, out)
    assert fid["ssim_pior_bloco"] >= 0.90, fid          # era 0,74 com imagem preta
    assert r["depois"] < r["antes"] * 0.5                 # reducao real (a imagem >1200px nunca era reduzida)
    with pikepdf.open(out) as pdf:
        filtros = {str(im.get("/Filter")) for pg in pdf.pages for im in pg.images.values()}
    assert "/DCTDecode" in filtros


def test_otimizar_sem_candidato_fiel_entrega_sem_perda(pdf_bom, tmp_path):
    out = tmp_path / "o.pdf"
    r = PAG.otimizar(pdf_bom, out, "arquivo")
    assert FID.similaridade_texto(pdf_bom, out) == 1.0
    assert r["via"] in ("pymupdf", "ghostscript", "pikepdf-sem-perda")


# ---------- 2. portoes de QA que nunca reprovavam ----------
def test_g3_reprova_fonte_nao_embutida(pdf_helv):
    q = QA.run(pdf_helv)
    assert not q["portoes"]["G3"]["ok"] and q["status"] == "REPROVADO"


def test_g2_detecta_pagina_em_branco(pdf_branco):
    q = QA.run(pdf_branco)
    assert q["portoes"]["G2"]["det"]["paginas_em_branco"] == [1] and not q["portoes"]["G2"]["ok"]
    assert QA.run(pdf_branco, brancas_permitidas=[1])["portoes"]["G2"]["ok"]


def test_g6_sem_nota_nao_aprova_design(pdf_bom):
    assert QA.run(pdf_bom, eh_design=True)["status"] == "PENDENTE_REVISAO"
    assert QA.run(pdf_bom, eh_design=True, nota_visual=7.5)["status"] == "REPROVADO"
    assert QA.run(pdf_bom, eh_design=True, nota_visual=8.6)["status"] == "APROVADO"


def test_g5_reprova_texto_sobreposto(pdf_feio):
    assert QA.run(pdf_feio)["portoes"]["G5"]["det"]["sobreposicao"] > 0


def test_g7_exige_idioma_e_produtor(pdf_textos, tmp_path):
    q = QA.run(pdf_textos[0])
    assert not q["portoes"]["G7"]["ok"]
    out = tmp_path / "m.pdf"
    ED.metadados(pdf_textos[0], out, titulo="T", autor="A", idioma="pt-BR")
    assert QA._g7(out)["ok"]


def test_g9_declarado_valida_de_verdade(pdf_bom):
    q = QA.run(pdf_bom, padrao="PDF/A-2b")
    assert not q["portoes"]["G9"]["ok"]                  # nao foi gerado como PDF/A: tem de reprovar
    assert QA.run(pdf_bom)["portoes"]["G9"]["aplica"] is False


def test_g10_link_nao_reprova_mas_javascript_sim(pdf_link, pdf_malicioso):
    assert QA._g10(pdf_link, False)["ok"]
    assert not QA._g10(pdf_malicioso, False)["ok"]


def test_g11_reprova_documento_diferente(pdf_textos):
    a, b = pdf_textos
    assert not QA.run(b, exige_ssim_ref=a)["portoes"]["G11"]["ok"]   # antes: 0,976 >= 0,9 aprovava
    assert QA.run(a, exige_ssim_ref=a)["portoes"]["G11"]["ok"]


def test_documento_criado_passa_em_todos_os_portoes(pdf_bom):
    q = QA.run(pdf_bom)
    assert q["status"] == "APROVADO", {k: v for k, v in q["portoes"].items() if not v["ok"]}


# ---------- 3. sanitizar so removia anexos ----------
def test_sanitizar_remove_tudo_e_triagem_fica_limpa(pdf_malicioso, tmp_path):
    out = tmp_path / "s.pdf"
    r = CONV.sanitizar(pdf_malicioso, out)
    assert r["triagem_depois"] == "BAIXA"
    with pikepdf.open(out) as pdf:
        assert "/JavaScript" not in pdf.Root.get("/Names", {})
        assert "/OpenAction" not in pdf.Root and "/AA" not in pdf.pages[0].obj
        assert "/Thumb" not in pdf.pages[0].obj and len(pdf.attachments) == 0
    assert b"/Launch" not in out.read_bytes()


# ---------- 4. OCR ----------
def test_ocr_hibrido_reconhece_pagina_escaneada(pdf_hibrido, tmp_path):
    out = tmp_path / "ocr.pdf"
    r = INTEL.ocr(pdf_hibrido, out, "por")
    assert r["paginas_ocr"] == [2]
    with fitz.open(out) as d:
        assert "LAUDO" in d[1].get_text().upper()


def test_ocr_fallback_tesseract_direto(pdf_hibrido, tmp_path, monkeypatch):
    from papiro_core.erros import PapiroErro

    def sem_ocrmypdf(*a, **k):
        raise PapiroErro("E_SEM_SUPORTE", "simulado")
    monkeypatch.setattr(INTEL, "_ocr_ocrmypdf", sem_ocrmypdf)
    out = tmp_path / "ocr2.pdf"
    r = INTEL.ocr(pdf_hibrido, out, "por")
    assert r["via"] == "tesseract" and r["fallback_from"] == "ocrmypdf"
    with fitz.open(out) as d:
        assert "ESCANEADO" in d[1].get_text().upper()


# ---------- 5. flatten nao achatava ----------
def test_flatten_remove_campos_editaveis(pdf_form, tmp_path):
    out = tmp_path / "f.pdf"
    r = CONV.achatar(pdf_form, out)
    with fitz.open(out) as d:
        assert sum(len(list(p.widgets() or [])) for p in d) == 0
    assert r["aparencia_identica"]


# ---------- 6. compose cortava linhas e perdia caracteres ----------
def test_compose_preserva_texto_longo_e_caracteres(tmp_path):
    linha = ("Paciente orientado quanto ao uso contínuo da medicação — dose única diária — com retorno em trinta "
             "dias para reavaliação clínica, exames laboratoriais e ajuste terapêutico se necessário. ULTIMAPALAVRA")
    for motor in ("typst", "story"):
        out = tmp_path / f"{motor}.pdf"
        CRE.markdown_para_pdf(f"# Título\n\n{linha}\n\nAspas \"duplas\" e # * _ ` $ < > @ [ ] ~", out, "T", motor=motor)
        with fitz.open(out) as d:
            t = " ".join(p.get_text() for p in d)
        assert "ULTIMAPALAVRA" in t and "—" in t and "duplas" in t and "# Título" not in t
        assert QA.run(out)["status"] == "APROVADO"


# ---------- 7. RAG citava sempre a pagina 1 ----------
def test_rag_cita_pagina_correta(pdf_rag, tmp_path):
    db = tmp_path / "rag.db"
    INTEL.rag_index(pdf_rag, "d1", "sha", str(pdf_rag), db=db)
    r = INTEL.rag_ask("zebrafinal", db=db)
    assert r and r[0]["pagina"] == 3 and "zebrafinal" in r[0]["trecho"]
    ev = tmp_path / "ev.pdf"
    assert INTEL.rag_evidencias(r, ev) == 1


# ---------- 8. MCP ----------
def test_job_id_unico(pdf_helv, out_dir):
    ids = {M.inspect("risk", str(pdf_helv), out_dir)["job_id"] for _ in range(3)}
    assert len(ids) == 3


def test_merge_com_qa_reprovado_nao_e_ok(pdf_helv, pdf_textos, out_dir):
    env = envelope_ok(M.pages("merge", out_dir, entradas=f"{pdf_helv};{pdf_textos[0]}"))
    assert env["ok"] is False and env["qa"]["status"] == "REPROVADO" and env["error"]["code"] == "E_CONFORMIDADE"


def test_attachments_extract_funciona_e_barra_traversal(pdf_anexo_traversal, out_dir):
    env = envelope_ok(M.attachments("extract", str(pdf_anexo_traversal), out_dir))
    assert env["ok"], env
    saida = pathlib.Path(env["outputs"][0]["path"])
    assert saida.name == "ESCAPOU.txt" and saida.parent == pathlib.Path(out_dir).resolve()
    assert not (pathlib.Path(out_dir).resolve().parent.parent / "ESCAPOU.txt").exists()


def test_roteador_e_estatistica_sao_usados(pdf_helv, out_dir):
    antes = {(s["tarefa"], s["motor"]): s["total"] for s in JOBS.stats_resumo()}
    env = M.inspect("fonts", str(pdf_helv), out_dir)
    depois = {(s["tarefa"], s["motor"]): s["total"] for s in JOBS.stats_resumo()}
    assert depois.get(("inspecao", env["engine"]["name"]), 0) == antes.get(("inspecao", env["engine"]["name"]), 0) + 1
    assert JOBS.job_status(env["job_id"])["status"] == "concluido"


# ---------- 9. inspecao ----------
def test_tags_detectadas(tmp_path, pdf_textos):
    p = tmp_path / "tag.pdf"
    with pikepdf.open(pdf_textos[0]) as pdf:
        pdf.Root.MarkInfo = pikepdf.Dictionary(Marked=True)
        pdf.save(p)
    assert INS.inventario(p)["marcado_tags"] is True


def test_to_unicode_real(pdf_helv, pdf_bom):
    assert INS.fontes(pdf_helv)[0]["to_unicode"] is False     # era sempre True
    assert all(f["to_unicode"] and f["embutida"] for f in INS.fontes(pdf_bom))


def test_revisao_incremental_detectada(pdf_incremental):
    r = INS.revisoes(pdf_incremental)
    assert r["revisoes_incrementais"] == 1 and "mudancas" in r["revisoes"][-1]


def test_busca_regex_varias_palavras(pdf_cpf):
    hits = INS.busca(pdf_cpf, r"CPF \d{3}\.\d{3}\.\d{3}-\d{2}")
    assert hits and hits[0]["pagina"] == 1 and hits[0]["texto"].startswith("CPF 529")


# ---------- 10. demais ----------
def test_mala_direta_usa_o_modelo(tmp_path):
    r = CRE.mala_direta("Prezado {{nome}}, consulta em {{data}}.", [{"nome": "Ana", "data": "01/10"}], tmp_path)
    with fitz.open(r["saidas"][0]) as d:
        assert "Prezado Ana, consulta em 01/10." in d[0].get_text()


def test_marca_dagua_em_camada_ocg(pdf_bom, tmp_path):
    out = tmp_path / "md.pdf"
    ED.marca_dagua(pdf_bom, out, "CONFIDENCIAL")
    with fitz.open(out) as d:
        assert [v["name"] for v in d.get_ocgs().values()] == ["Marca d'agua"]


def test_remover_branco_nao_apaga_pagina_vetorial(pdf_vetor, pdf_branco, tmp_path):
    assert PAG.remover_branco(pdf_vetor, tmp_path / "a.pdf")["removidas"] == []
    assert PAG.remover_branco(pdf_branco, tmp_path / "b.pdf")["removidas"] == [1]


def test_pii_categorias_do_prd():
    texto = ("CPF 529.982.247-25; CPF 123.456.789-00; CNPJ 11.222.333/0001-81; CNS 700 0000 0000 0005; "
             "RG 12.345.678-9; CRM/RS 12345; CEP 97010-000; nascido em 12/03/1980; Paciente: Maria da Silva; "
             "tel (55) 99715-0000; email a@b.com")
    achados = PII.detectar_texto(texto, usar_presidio=False)
    cats = {a["categoria"] for a in achados}
    assert {"CPF", "CNPJ", "CNS", "RG", "CRM", "CEP", "DATA_NASCIMENTO", "NOME", "TELEFONE", "EMAIL"} <= cats
    assert "123.456.789-00" not in {a["texto"] for a in achados}      # digito verificador invalido


def test_tarja_verifica_de_verdade(pdf_cpf, tmp_path, monkeypatch):
    r0 = fitz.open(pdf_cpf)[0].search_for("529.982.247-25")[0]
    caixa = [{"pagina": 1, "x0": r0.x0, "y0": r0.y0, "x1": r0.x1, "y1": r0.y1}]
    out = tmp_path / "t.pdf"
    r = ED.tarjar(pdf_cpf, out, caixa)
    with fitz.open(out) as d:
        t = d[0].get_text()
    assert "529.982" not in t and "Resto do laudo" in t and r["verificado"]
    # se a remocao falhar, nada e entregue
    monkeypatch.setattr(fitz.Page, "apply_redactions", lambda self, **k: True)
    import pytest
    from papiro_core.erros import PapiroErro
    with pytest.raises(PapiroErro) as e:
        ED.tarjar(pdf_cpf, tmp_path / "t2.pdf", caixa)
    assert e.value.codigo == "E_CONFORMIDADE" and not (tmp_path / "t2.pdf").exists()


def test_comparacao_ssim_real(pdf_textos, tmp_path):
    r = CMP.comparar(pdf_textos[0], pdf_textos[1], tmp_path / "c.pdf")
    assert not r["identicos"] and r["visual"]["ssim_pior_bloco"] < 0.9 and r["texto"]["linhas_diff"] > 0


def test_auditoria_sem_caminho_nem_nome(pdf_cpf, out_dir):
    from papiro_core.audit import AUDIT
    env = M.inspect("risk", str(pdf_cpf), out_dir)
    linha = [json.loads(x) for x in AUDIT.read_text(encoding="utf-8").splitlines() if env["audit_id"] in x][0]
    bruto = json.dumps(linha)
    assert "cpf.pdf" not in bruto and "/" not in "".join(o.get("ext", "") for o in linha["outputs"])
    assert linha["outputs"][0]["sha256"] == env["outputs"][0]["sha256"]
