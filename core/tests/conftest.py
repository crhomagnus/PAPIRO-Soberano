# -*- coding: utf-8 -*-
"""Fixtures do papiro-core. Dados de execucao isolados num PAPIRO_HOME temporario (o repositorio nao e tocado);
todos os PDFs de teste sao gerados aqui, sem dado real de paciente."""
import datetime, json, os, pathlib, sys, tempfile

_BASE = pathlib.Path(tempfile.mkdtemp(prefix="papiro-testes-"))
os.environ["PAPIRO_HOME"] = str(_BASE)
os.environ["PAPIRO_PERFIL"] = "P0"
os.environ.pop("PAPIRO_CONFIRM", None)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import fitz  # noqa: E402
import numpy as np  # noqa: E402
import pikepdf  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from papiro_core import OUT, ROOT  # noqa: E402

CORPUS = ROOT / "corpus_teste"
CORPUS.mkdir(parents=True, exist_ok=True)
FONTE = pathlib.Path(__file__).resolve().parents[2] / "fonts" / "LiberationSans-Regular.ttf"


def _texto(p, paginas, titulo=None, embutir=False, autor="teste", idioma=None):
    d = fitz.open()
    for t in paginas:
        pg = d.new_page()
        if embutir:
            pg.insert_font(fontname="lib", fontfile=str(FONTE))
            pg.insert_textbox(fitz.Rect(72, 72, 523, 770), t, fontsize=11, fontname="lib")
        else:
            pg.insert_textbox(fitz.Rect(72, 72, 523, 770), t, fontsize=11)
    if titulo:
        d.set_metadata({"title": titulo, "author": autor, "producer": "teste"})
    if idioma:
        d.set_language(idioma)
    d.save(p)
    d.close()
    return p


@pytest.fixture
def out_dir(request):
    return str(OUT / "testes" / request.node.name[:80])


@pytest.fixture(scope="session")
def pdf_helv():
    return _texto(CORPUS / "helv.pdf", ["Texto em Helvetica base-14, fonte NAO embutida."], titulo="T")


@pytest.fixture(scope="session")
def pdf_bom():
    from papiro_core.adapters import create as CRE
    p = CORPUS / "bom.pdf"
    CRE.markdown_para_pdf("# Relatório de teste\n\nParágrafo de conteúdo com acentuação — travessão.\n\n- item um\n- item dois\n",
                          p, "Relatório de teste", "PAPIRO")
    return p


@pytest.fixture(scope="session")
def pdf_textos():
    a = _texto(CORPUS / "ta.pdf", ["Contrato de locacao. Clausula primeira: o locatario pagara R$ 1.000,00 mensais. " * 6])
    b = _texto(CORPUS / "tb.pdf", ["Receituario medico. Uso oral: tomar 1 comprimido a cada 8 horas por 7 dias. " * 6])
    return a, b


@pytest.fixture(scope="session")
def pdf_fotos():
    rng = np.random.default_rng(7)
    y, x = np.mgrid[0:1600, 0:1600]
    arr = np.stack([(x / 1600 * 255), (y / 1600 * 255), ((x + y) / 3200 * 255)], -1)
    arr = (arr + rng.normal(0, 8, arr.shape)).clip(0, 255).astype(np.uint8)
    grande, pequena = CORPUS / "foto.png", CORPUS / "foto_pequena.png"
    Image.fromarray(arr).save(grande)
    Image.fromarray(arr[:800, :800]).save(pequena)
    d = fitz.open()
    d.new_page().insert_image(fitz.Rect(36, 36, 559, 559), filename=str(grande))
    d.new_page().insert_image(fitz.Rect(36, 36, 400, 400), filename=str(pequena))
    d.set_metadata({"title": "fotos"})
    p = CORPUS / "fotos.pdf"
    d.save(p)
    return p


@pytest.fixture(scope="session")
def pdf_form():
    d = fitz.open()
    pg = d.new_page()
    w = fitz.Widget()
    w.field_name, w.field_type, w.rect, w.field_value = "nome", fitz.PDF_WIDGET_TYPE_TEXT, fitz.Rect(72, 72, 300, 100), "Fulano"
    pg.add_widget(w)
    c = fitz.Widget()
    c.field_name, c.field_type, c.rect = "aceite", fitz.PDF_WIDGET_TYPE_CHECKBOX, fitz.Rect(72, 120, 90, 138)
    pg.add_widget(c)
    p = CORPUS / "form.pdf"
    d.save(p)
    return p


def _malicioso(p, nome_anexo="segredo.txt"):
    N, D, A, S = pikepdf.Name, pikepdf.Dictionary, pikepdf.Array, pikepdf.String
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    js = pdf.make_indirect(D(S=N.JavaScript, JS=S("app.alert('x')")))
    pdf.Root.Names = D(JavaScript=D(Names=A([S("j1"), js])))
    pdf.Root.OpenAction = D(S=N.JavaScript, JS=S("1"))
    pg = pdf.pages[0]
    pg.obj.AA = D(O=pdf.make_indirect(D(S=N.JavaScript, JS=S("1"))))
    launch = pdf.make_indirect(D(Type=N.Annot, Subtype=N.Link, Rect=A([0, 0, 100, 100]), A=D(S=N.Launch, F=S("cmd.exe"))))
    anexo_annot = pdf.make_indirect(D(Type=N.Annot, Subtype=N.FileAttachment, Rect=A([100, 100, 120, 120])))
    pg.obj.Annots = pdf.make_indirect(A([launch, anexo_annot]))
    pg.obj.Thumb = pdf.make_stream(b"\x00" * 10)
    with pdf.open_metadata() as meta:
        meta["dc:creator"] = ["Fulano Paciente"]
    pdf.attachments[nome_anexo] = pikepdf.AttachedFileSpec(pdf, b"dados sigilosos", filename=nome_anexo)
    pdf.save(p)
    return p


@pytest.fixture(scope="session")
def pdf_malicioso():
    return _malicioso(CORPUS / "malicioso.pdf")


@pytest.fixture(scope="session")
def pdf_anexo_traversal():
    return _malicioso(CORPUS / "traversal.pdf", "../../ESCAPOU.txt")


@pytest.fixture(scope="session")
def png_scan():
    tmp = fitz.open()
    tp = tmp.new_page()
    tp.insert_text((72, 100), "LAUDO ESCANEADO PAGINA DOIS", fontsize=28)
    p = CORPUS / "scan.png"
    tp.get_pixmap(dpi=200).save(p)
    return p


@pytest.fixture(scope="session")
def pdf_hibrido(png_scan):
    d = fitz.open()
    d.new_page().insert_textbox(fitz.Rect(72, 72, 523, 770), "Pagina digital com bastante texto. " * 10)
    d.new_page().insert_image(fitz.Rect(0, 0, 595, 842), filename=str(png_scan))
    p = CORPUS / "hibrido.pdf"
    d.save(p)
    return p


@pytest.fixture(scope="session")
def pdf_incremental():
    p = _texto(CORPUS / "incr.pdf", ["versao 1"])
    d = fitz.open(p)
    d[0].insert_text((72, 400), "alteracao posterior")
    d.saveIncr()
    d.close()
    return p


@pytest.fixture(scope="session")
def pdf_cpf():
    return _texto(CORPUS / "cpf.pdf", ["Paciente: Joana. CPF 529.982.247-25. Resto do laudo permanece legivel."], titulo="L")


@pytest.fixture(scope="session")
def pdf_rag():
    return _texto(CORPUS / "rag.pdf", ["intro " * 50, "meio " * 50, "a palavra zebrafinal aparece so aqui " * 3])


@pytest.fixture(scope="session")
def pdf_link():
    d = fitz.open()
    pg = d.new_page()
    pg.insert_text((72, 72), "Veja o site oficial " * 3)
    pg.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(72, 60, 300, 80), "uri": "https://www.gov.br"})
    p = CORPUS / "link.pdf"
    d.save(p)
    return p


@pytest.fixture(scope="session")
def pdf_branco():
    d = fitz.open()
    d.new_page()
    d.new_page().insert_text((72, 72), "so a pagina 2 tem texto")
    p = CORPUS / "branco.pdf"
    d.save(p)
    return p


@pytest.fixture(scope="session")
def pdf_vetor():
    d = fitz.open()
    d.new_page().insert_text((72, 72), "pagina com texto suficiente aqui")
    pg = d.new_page()
    pg.draw_rect(fitz.Rect(100, 100, 500, 500), color=(0, 0, 1), fill=(0.2, 0.4, 0.8))
    p = CORPUS / "vetor.pdf"
    d.save(p)
    return p


@pytest.fixture(scope="session")
def pdf_feio():
    d = fitz.open()
    pg = d.new_page()
    pg.insert_font(fontname="lib", fontfile=str(FONTE))
    for i in range(10):
        pg.insert_text((72, 200 + i % 3), "SOBREPOSTO", fontsize=18, fontname="lib")
    d.set_metadata({"title": "Feio", "author": "t", "producer": "t"})
    d.set_language("pt-BR")
    p = CORPUS / "feio.pdf"
    d.save(p)
    return p


@pytest.fixture(scope="session")
def pfx_teste():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Teste PAPIRO (autoassinado)")])
    agora = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(agora - datetime.timedelta(days=1))
            .not_valid_after(agora + datetime.timedelta(days=30))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(chave, hashes.SHA256()))
    p = CORPUS / "teste.pfx"
    p.write_bytes(pkcs12.serialize_key_and_certificates(b"teste", chave, cert, None,
                                                        serialization.BestAvailableEncryption(b"senha-de-teste")))
    os.environ["PAPIRO_TESTE_PFX_SENHA"] = "senha-de-teste"
    return p


def envelope_ok(env: dict) -> dict:
    """Contrato §8.1 presente em toda resposta."""
    for chave in ("ok", "job_id", "outputs", "engine", "metrics", "warnings", "qa", "audit_id"):
        assert chave in env, f"envelope sem {chave}: {json.dumps(env)[:300]}"
    return env
