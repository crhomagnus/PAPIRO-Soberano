# -*- coding: utf-8 -*-
"""Contrato das 38 ferramentas do servidor `papiro` (PRD §8): envelope, confinamento, dry_run e cada operacao."""
import json, pathlib
import fitz
import pytest
from papiro_core import OUT, ROOT, mcp_server as M
from conftest import CORPUS, envelope_ok


def ok(env):
    envelope_ok(env)
    assert env["ok"], json.dumps(env, ensure_ascii=False, default=str)[:800]
    return env


def saida(env, sufixo=".pdf"):
    return next(pathlib.Path(o["path"]) for o in env["outputs"] if o["path"].endswith(sufixo))


# ---------- regras gerais ----------
def test_lista_de_ferramentas_igual_ao_prd():
    nomes = {t.name for t in M.mcp._tool_manager.list_tools()}
    prd = set("inspect search render_pages pages outline attachments stamp replace_text annotate layers images metadata "
              "compose office_to_pdf mail_merge graphics capture convert ocr parse extract rag translate alt_text forms "
              "conform validate preflight color impose optimize repair fonts compare qa_run jobs recipes engines".split())
    assert nomes == prd and len(nomes) == 38


def test_entrada_fora_da_raiz_e_out_dir_proibido(pdf_helv, out_dir):
    e = envelope_ok(M.inspect("all", "/etc/hostname", out_dir))
    assert e["error"]["code"] == "E_ENTRADA"
    e = envelope_ok(M.inspect("all", str(pdf_helv), "/tmp"))
    assert e["error"]["code"] == "E_POLITICA"
    e = envelope_ok(M.inspect("all", str(CORPUS / "nao-existe.pdf"), out_dir))
    assert e["error"]["code"] == "E_ENTRADA"


def test_dry_run_devolve_plano_sem_executar(pdf_helv, out_dir):
    e = ok(M.optimize(str(pdf_helv), out_dir, dry_run=True))
    assert e["outputs"] == [] and e["dados"]["plano"]["ferramenta"] == "optimize" and e["dados"]["plano"]["motores"]


def test_entrada_nunca_alterada(pdf_textos, out_dir):
    from papiro_core import sha256_file
    antes = sha256_file(pdf_textos[0])
    ok(M.replace_text(str(pdf_textos[0]), out_dir, "locacao", "aluguel", qa=False))
    ok(M.stamp("watermark", str(pdf_textos[0]), out_dir, texto="X", qa=False))
    assert sha256_file(pdf_textos[0]) == antes


def test_saida_nunca_sobrescreve(pdf_bom, out_dir):
    a = saida(ok(M.metadata(str(pdf_bom), out_dir, titulo="A", autor="B", qa=False)))
    b = saida(ok(M.metadata(str(pdf_bom), out_dir, titulo="A", autor="B", qa=False)))
    assert a != b and a.exists() and b.exists()


def test_arquivo_corrompido_e_senha(out_dir, pdf_bom):
    ruim = CORPUS / "ruim.pdf"
    ruim.write_bytes(b"%PDF-1.4 lixo sem estrutura")
    assert envelope_ok(M.inspect("inventory", str(ruim), out_dir))["error"]["code"] == "E_CORROMPIDO"
    from papiro_core.adapters import convert as CONV
    enc = CORPUS / "enc.pdf"
    CONV.criptografar(pdf_bom, enc, "abc")
    assert envelope_ok(M.inspect("inventory", str(enc), out_dir))["error"]["code"] == "E_SENHA"
    assert ok(M.inspect("inventory", str(enc), out_dir, senha="abc"))["dados"]["paginas"] == 1


# ---------- inspecao ----------
@pytest.mark.parametrize("op", ["all", "inventory", "fonts", "images", "pages", "revisions", "risk"])
def test_inspect_ops(op, pdf_malicioso, out_dir):
    ok(M.inspect(op, str(pdf_malicioso), out_dir))


def test_inspect_op_invalida(pdf_helv, out_dir):
    assert envelope_ok(M.inspect("xyz", str(pdf_helv), out_dir))["error"]["code"] == "E_SEM_SUPORTE"


def test_search_e_render(pdf_cpf, out_dir):
    assert ok(M.search(str(pdf_cpf), out_dir, r"\d{3}\.\d{3}"))["dados"]["ocorrencias"] == 1
    e = ok(M.render_pages(str(pdf_cpf), out_dir, dpi=50, prancha=True))
    assert any(o["path"].endswith("prancha.png") for o in e["outputs"])


# ---------- paginas ----------
def test_pages_ops(pdf_textos, pdf_branco, pdf_bom, out_dir):
    a, b = map(str, pdf_textos)
    merge = saida(ok(M.pages("merge", out_dir, entradas=f"{a};{b}", qa=False)))
    m = str(merge)
    with fitz.open(m) as d:
        assert d.page_count == 2 and len(d.get_toc()) == 2
    assert len(ok(M.pages("split", out_dir, entrada=m, a_cada=1))["outputs"]) == 2
    assert len(ok(M.pages("split", out_dir, entrada=m, por_marcador=True))["outputs"]) == 2
    for op, extra in [("extract", {"paginas": "2"}), ("delete", {"paginas": "1"}), ("move", {"paginas": "2,1"}),
                      ("duplicate", {"paginas": "1"}), ("reverse", {}), ("rotate", {"paginas": "1", "angulo": "180"}),
                      ("resize", {"papel": "a5"}), ("nup", {"por_folha": 2}), ("booklet", {}),
                      ("labels", {"rotulos_json": '[{"inicio":1,"estilo":"r"}]'}),
                      ("boxes", {"caixas_json": '{"CropBox":[10,10,500,800]}'})]:
        ok(M.pages(op, out_dir, entrada=m, qa=False, **extra))
    ok(M.pages("interleave", out_dir, entradas=f"{a};{b}", qa=False))
    assert ok(M.pages("blank_remove", out_dir, entrada=str(pdf_branco), qa=False))["dados"]["removidas"] == [1]
    assert envelope_ok(M.pages("poster", out_dir, entrada=m))["error"]["code"] == "E_SEM_SUPORTE"
    assert envelope_ok(M.pages("extract", out_dir, entrada=m, paginas="9"))["error"]["code"] == "E_ENTRADA"
    e = ok(M.pages("reverse", out_dir, entrada=str(pdf_bom)))
    assert e["qa"]["status"] == "APROVADO" and e["qa"]["report"].endswith(".json")


def test_outline_e_attachments(pdf_bom, pdf_malicioso, pdf_helv, out_dir):
    e = ok(M.outline("set", str(pdf_bom), out_dir, toc_json='[[1, "Início", 1]]'))
    assert ok(M.outline("get", str(saida(e)), out_dir))["dados"]["itens"] == 1
    assert ok(M.attachments("list", str(pdf_malicioso), out_dir))["dados"]["anexos"] == 1
    e = ok(M.attachments("add", str(pdf_bom), out_dir, anexo=str(pdf_helv)))
    assert ok(M.attachments("list", str(saida(e)), out_dir))["dados"]["anexos"] == 1


# ---------- edicao ----------
def test_stamp_ops(pdf_bom, pdf_cpf, png_scan, out_dir):
    ok(M.stamp("text", str(pdf_cpf), out_dir, texto="VISTO", ancora="Paciente:", qa=False))
    ok(M.stamp("qr", str(pdf_cpf), out_dir, qr="https://gov.br", qa=False))
    ok(M.stamp("image", str(pdf_cpf), out_dir, imagem=str(png_scan), qa=False))
    ok(M.stamp("watermark", str(pdf_bom), out_dir, texto="RASCUNHO", qa=False))
    ok(M.stamp("footer", str(pdf_cpf), out_dir, qa=False))
    ok(M.stamp("header", str(pdf_cpf), out_dir, modelo="Doc {n}/{total}", qa=False))
    ok(M.stamp("bates", str(pdf_cpf), out_dir, bates_prefixo="PAP", qa=False))
    assert envelope_ok(M.stamp("text", str(pdf_cpf), out_dir, texto="x", ancora="inexistente"))["error"]["code"] == "E_ENTRADA"
    assert envelope_ok(M.stamp("seal3d", str(pdf_cpf), out_dir))["error"]["code"] == "E_SEM_SUPORTE"


def test_annotate_layers_images_metadata(pdf_bom, pdf_cpf, pdf_fotos, png_scan, out_dir):
    ok(M.annotate("highlight", str(pdf_cpf), out_dir, busca="Paciente"))
    ok(M.annotate("note", str(pdf_cpf), out_dir, texto="conferir"))
    link = saida(ok(M.annotate("link", str(pdf_cpf), out_dir, busca="Paciente", url="https://gov.br")))
    ok(M.annotate("flatten", str(link), out_dir))
    assert envelope_ok(M.annotate("xfdf_export", str(pdf_cpf), out_dir))["error"]["code"] == "E_SEM_SUPORTE"
    marca = saida(ok(M.stamp("watermark", str(pdf_bom), out_dir, texto="X", qa=False)))
    assert ok(M.layers("list", str(marca), out_dir))["dados"]["camadas"][0]["name"] == "Marca d'agua"
    oculto = saida(ok(M.layers("hide", str(marca), out_dir, camadas="Marca d'agua")))
    with fitz.open(oculto) as d:
        assert not next(iter(d.get_ocgs().values()))["on"]
    assert ok(M.images("list", str(pdf_fotos), out_dir))["dados"]["imagens"] == 2
    assert ok(M.images("extract", str(pdf_fotos), out_dir))["dados"]["extraidas"] == 2
    xref = fitz.open(pdf_fotos)[1].get_images()[0][0]
    ok(M.images("replace", str(pdf_fotos), out_dir, xref=xref, imagem=str(png_scan), qa=False))
    ok(M.images("grayscale", str(pdf_fotos), out_dir, qa=False))
    ok(M.images("recompress", str(pdf_fotos), out_dir, qa=False))
    e = envelope_ok(M.metadata(str(pdf_cpf), out_dir, titulo="Laudo", autor="PAPIRO"))
    assert e["qa"]["bloqueantes"] == ["G3"]          # so a fonte base-14 do corpus impede a entrega


# ---------- criacao ----------
def test_compose_motores_e_padroes(out_dir):
    e = ok(M.compose("auto", out_dir, markdown="# Olá\n\nTexto.", titulo="Olá"))
    assert e["qa"]["status"] == "APROVADO" and e["engine"]["version"]
    e = ok(M.compose("typst", out_dir, markdown="# PDF/A\n\nTexto.", titulo="PDF/A", padroes="a-2b"))
    assert e["qa"]["status"] == "APROVADO"
    e = ok(M.compose("html", out_dir, html="<html lang='pt-BR'><body><h1>Título</h1><p>Olá</p></body></html>", titulo="HTML"))
    assert e["engine"]["name"] == "chromium"
    e = envelope_ok(M.compose("auto", out_dir, markdown="# Peça\n\nx", titulo="Peça", design=True))
    assert e["qa"]["status"] == "PENDENTE_REVISAO" and e["ok"] is False


def test_mail_merge_graphics_capture(tmp_path, png_scan, out_dir):
    csv = CORPUS / "dados.csv"
    csv.write_text("nome;data\nAna;01/10\nJosé;02/10\n", encoding="utf-8")
    e = ok(M.mail_merge(out_dir, "Prezado(a) {{nome}}, retorno em {{data}}.", dados_arquivo=str(csv),
                        modo="um_por_registro", campo_nome="nome", qa=False))
    assert e["dados"]["arquivos"] == 2
    ok(M.mail_merge(out_dir, "Oi {{nome}}", dados_json='[{"nome":"Ana"}]'))
    assert envelope_ok(M.mail_merge(out_dir, "Oi {{falta}}", dados_json='[{"nome":"Ana"}]'))["error"]["code"] == "E_ENTRADA"
    ok(M.graphics("qr", out_dir, "https://validar.iti.gov.br"))
    ok(M.graphics("diagram", out_dir, "digraph { consulta -> receita -> assinatura }", titulo="Fluxo", qa=False))
    assert envelope_ok(M.graphics("chart", out_dir, "{}"))["error"]["code"] == "E_SEM_SUPORTE"
    ok(M.capture("photos", out_dir, imagens=str(png_scan), titulo="Foto", qa=False))
    assert envelope_ok(M.capture("web", out_dir, url="ftp://x"))["error"]["code"] == "E_ENTRADA"


def test_office_to_pdf(out_dir):
    odt = CORPUS / "carta.txt"
    odt.write_text("Carta de teste com acentuação.\n", encoding="utf-8")
    e = envelope_ok(M.office_to_pdf(str(odt), out_dir, qa=False))
    assert e["ok"], e
    assert e["engine"]["name"] == "libreoffice"


# ---------- conversao e IA ----------
@pytest.mark.parametrize("destino", ["txt", "md", "json", "png", "svg", "xlsx", "csv"])
def test_convert(destino, pdf_cpf, out_dir):
    ok(M.convert(str(pdf_cpf), out_dir, destino, dpi=40))


def test_convert_sem_suporte_parse_extract(pdf_cpf, out_dir):
    assert envelope_ok(M.convert(str(pdf_cpf), out_dir, "docx"))["error"]["code"] == "E_SEM_SUPORTE"
    ok(M.parse(str(pdf_cpf), out_dir, "json"))
    ok(M.extract("tables", str(pdf_cpf), out_dir))
    ok(M.extract("fields", str(pdf_cpf), out_dir))
    assert "CPF" in ok(M.extract("entities", str(pdf_cpf), out_dir))["dados"]["categorias"]


def test_ocr_rag_translate_alt(pdf_hibrido, pdf_rag, out_dir):
    e = envelope_ok(M.ocr(str(pdf_hibrido), out_dir))
    assert e["dados"]["paginas_ocr"] == [2]
    ok(M.rag("index", out_dir, doc_id="rag-teste", entrada=str(pdf_rag)))
    r = ok(M.rag("ask", out_dir, pergunta="zebrafinal"))
    assert r["dados"]["respostas"][0]["pagina"] == 3 and any(o["path"].endswith("evidencias.pdf") for o in r["outputs"])
    assert envelope_ok(M.rag("index", out_dir, entrada=str(pdf_rag)))["error"]["code"] == "E_ENTRADA"
    assert envelope_ok(M.translate(str(pdf_rag), out_dir))["error"]["code"] == "E_SEM_SUPORTE"
    assert envelope_ok(M.alt_text(str(pdf_rag), out_dir))["error"]["code"] == "E_SEM_SUPORTE"


# ---------- formularios ----------
def test_forms(pdf_form, out_dir):
    assert len(ok(M.forms("list", str(pdf_form), out_dir))["dados"]["campos"]) == 2
    assert ok(M.forms("detect_xfa", str(pdf_form), out_dir))["dados"]["xfa"] is False
    preenchido = saida(ok(M.forms("fill", str(pdf_form), out_dir, dados_json='{"nome": "João Ação", "aceite": true}')))
    with fitz.open(preenchido) as d:
        valores = {w.field_name: w.field_value for w in d[0].widgets()}
    assert valores["nome"] == "João Ação" and valores["aceite"] not in ("Off", "", None)
    for fmt in ("json", "csv", "fdf", "xfdf"):
        ok(M.forms("export", str(preenchido), out_dir, formato=fmt))
    xf = next(pathlib.Path(o["path"]) for o in ok(M.forms("export", str(preenchido), out_dir, formato="xfdf"))["outputs"])
    ok(M.forms("import_xfdf", str(pdf_form), out_dir, xfdf=str(xf)))
    dados = CORPUS / "lote.json"
    dados.write_text('[{"nome":"Ana"},{"nome":"Bia"}]', encoding="utf-8")
    assert ok(M.forms("fill_batch", str(pdf_form), out_dir, dados_arquivo=str(dados), campo_nome="nome"))["dados"]["registros"] == 2
    ok(M.forms("flatten", str(preenchido), out_dir))
    assert envelope_ok(M.forms("create", str(pdf_form), out_dir))["error"]["code"] == "E_SEM_SUPORTE"


# ---------- conformidade ----------
def test_conform_validate_preflight_color_impose(pdf_bom, out_dir):
    e = ok(M.conform("pdfa", str(pdf_bom), out_dir, padrao="PDF/A-2b"))
    pdfa = saida(e)
    v = ok(M.validate(str(pdfa), out_dir, padrao="PDF/A-2b"))
    assert v["dados"]["valido"]
    assert envelope_ok(M.validate(str(pdf_bom), out_dir, padrao="PDF/A-2b"))["ok"] is False
    assert envelope_ok(M.conform("pdfua", str(pdf_bom), out_dir))["error"]["code"] == "E_SEM_SUPORTE"
    p = envelope_ok(M.preflight(str(pdf_bom), out_dir))
    assert p["ok"] is False and "OutputIntent" in p["qa"]["bloqueantes"]
    ok(M.color("gray", str(pdf_bom), out_dir, qa=False))
    e = envelope_ok(M.color("cmyk", str(pdf_bom), out_dir, qa=False))
    assert e["ok"] and e["warnings"]
    assert envelope_ok(M.color("profile", str(pdf_bom), out_dir))["error"]["code"] == "E_SEM_SUPORTE"
    ok(M.impose("booklet", str(pdf_bom), out_dir))


# ---------- otimizacao, reparo, fontes, comparacao ----------
def test_optimize_repair_fonts_compare(pdf_fotos, pdf_helv, pdf_textos, out_dir):
    e = envelope_ok(M.optimize(str(pdf_fotos), out_dir, "email", linearizar=True))
    assert e["dados"]["reducao_pct"] > 50 and e["dados"]["linearizado"]
    ok(M.repair(str(pdf_helv), out_dir, qa=False))
    assert ok(M.fonts("list", str(pdf_helv), out_dir))["dados"]["nao_embutidas"] == ["Helvetica"]
    embutido = saida(ok(M.fonts("embed", str(pdf_helv), out_dir, qa=False)))
    from papiro_core.adapters import inspect as INS
    assert all(f["embutida"] and f["to_unicode"] for f in INS.fontes(embutido))
    from papiro_core.adapters import qa as QA
    assert QA._g3(embutido)["ok"]
    c = ok(M.compare(str(pdf_textos[0]), str(pdf_textos[1]), out_dir))
    assert c["dados"]["identicos"] is False and c["dados"]["paginas_com_diferenca"] == [1]


# ---------- operacao ----------
def test_qa_jobs_recipes_engines(pdf_bom, pdf_textos, out_dir):
    e = ok(M.qa_run(str(pdf_bom), out_dir))
    assert e["qa"]["status"] == "APROVADO" and pathlib.Path(e["qa"]["report"]).exists()
    assert pathlib.Path(e["qa"]["report"]).with_suffix(".md").exists()
    e = envelope_ok(M.qa_run(str(pdf_textos[1]), out_dir, referencia=str(pdf_textos[0])))
    assert e["ok"] is False and "G11" in e["qa"]["bloqueantes"]
    assert ok(M.jobs("status", job_id=e["job_id"]))["dados"]["status"] == "falhou"
    assert ok(M.jobs("list", limite=5))["dados"]
    assert ok(M.jobs("stats"))["dados"]
    assert ok(M.jobs("route", pedido="Quero comprimir este PDF"))["dados"]["tarefa"] == "otimizar"
    assert ok(M.jobs("cancel", job_id="nao-existe"))["dados"]["existe"] is False
    assert envelope_ok(M.jobs("xyz"))["error"]["code"] == "E_SEM_SUPORTE"
    assert "exemplo-receituario-assinado.yaml" in ok(M.recipes("list"))["dados"]["receitas"]
    ruim = CORPUS / "receita_ruim.yaml"
    ruim.write_text("receita: x\nversao: 0\npassos:\n  - ferramenta: compose\n", encoding="utf-8")
    assert ok(M.recipes("validate", arquivo=str(ruim)))["dados"]["valida"] is False
    assert envelope_ok(M.recipes("run", arquivo=str(ruim)))["error"]["code"] == "E_SEM_SUPORTE"
    assert ok(M.engines())["dados"]["libs"]["pymupdf"]


def test_recursos_e_prompts(pdf_bom, out_dir):
    e = ok(M.qa_run(str(pdf_bom), out_dir))
    assert json.loads(M.recurso_relatorio(e["job_id"]))["status"] == "APROVADO"
    assert "erro" in json.loads(M.recurso_relatorio("inexistente"))
    assert "libs" in json.loads(M.recurso_engines())
    assert isinstance(json.loads(M.recurso_brandkits()), list) and isinstance(json.loads(M.recurso_templates()), list)
    for p in (M.prompt_criar("receituario", "x"), M.prompt_revisar("a.pdf"), M.prompt_grafica("a.pdf"),
              M.prompt_medico("atestado", "{}")):
        assert "PAPIRO" in p or "qa_run" in p or "preflight" in p
