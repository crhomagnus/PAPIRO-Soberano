# -*- coding: utf-8 -*-
"""LTV - PAdES B-LT e B-LTA (RF-806, PRD §12.1): guardar dentro do PDF a prova de que o certificado valia na hora.

Para isso o PAPIRO precisa buscar a revogacao (CRL/OCSP) na AC que emitiu o certificado. Aqui a AC e uma PKI de
teste com a CRL servida em 127.0.0.1, entao o caminho exercitado e o real - busca de verdade, DSS de verdade -
sem depender da internet nem de certificado pago."""
import datetime, http.server, os, threading
import pytest
from papiro_core import ROOT, WORK, config, mcp_seguranca as S
from conftest import CORPUS, envelope_ok
from test_carimbo_tsa import servidor_rfc3161, tsa_de_teste


def _crl_do_momento(ca_nome, ca_key, revogados=()):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    agora = datetime.datetime.now(datetime.timezone.utc)
    construtor = (x509.CertificateRevocationListBuilder().issuer_name(ca_nome)
                  .last_update(agora - datetime.timedelta(minutes=5))
                  .next_update(agora + datetime.timedelta(days=7)))
    for serie in revogados:
        construtor = construtor.add_revoked_certificate(
            x509.RevokedCertificateBuilder().serial_number(serie).revocation_date(agora).build())
    return construtor.sign(ca_key, hashes.SHA256())


@pytest.fixture(scope="session")
def pki_teste():
    """AC de teste + certificado com ponto de distribuicao de CRL em 127.0.0.1 + a AC como ancora de confianca."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    agora = datetime.datetime.now(datetime.timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC Raiz de Teste PAPIRO")])
    ca = (x509.CertificateBuilder().subject_name(ca_nome).issuer_name(ca_nome).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(agora - datetime.timedelta(days=1))
          .not_valid_after(agora + datetime.timedelta(days=365))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                       data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                       crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
          .sign(ca_key, hashes.SHA256()))
    estado = {"pedidos_crl": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - nome exigido pelo BaseHTTPRequestHandler
            estado["pedidos_crl"] += 1
            corpo = _crl_do_momento(ca_nome, ca_key).public_bytes(serialization.Encoding.DER)
            self.send_response(200)
            self.send_header("Content-Type", "application/pkix-crl")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *_):
            pass
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    url_crl = f"http://127.0.0.1:{servidor.server_address[1]}/crl"
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Assinante de Teste LTV")])
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(ca_nome).public_key(chave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(agora - datetime.timedelta(days=1))
            .not_valid_after(agora + datetime.timedelta(days=90))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.CRLDistributionPoints([x509.DistributionPoint(
                full_name=[x509.UniformResourceIdentifier(url_crl)], relative_name=None, reasons=None,
                crl_issuer=None)]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    tsa = servidor_rfc3161(tsa_de_teste(emissor=(ca_nome, ca_key), url_crl=url_crl))
    pfx = CORPUS / "ltv.pfx"
    pfx.write_bytes(pkcs12.serialize_key_and_certificates(b"ltv", chave, cert, [ca],
                                                          serialization.BestAvailableEncryption(b"senha-de-teste")))
    os.environ["PAPIRO_TESTE_PFX_SENHA"] = "senha-de-teste"   # o pfx acima usa esta senha; nao depender de ordem
    ancoras = ROOT / "certs_teste"
    ancoras.mkdir(exist_ok=True)
    (ancoras / "ac-raiz-teste.crt").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    yield {"pfx": str(pfx), "senha_ref": "env:PAPIRO_TESTE_PFX_SENHA", "ancoras": str(ancoras), "estado": estado,
           "url_crl": url_crl, "tsa": tsa["url"]}
    tsa["servidor"].shutdown()
    servidor.shutdown()


@pytest.fixture
def com_ancoras(pki_teste):
    """Aponta [assinatura] raizes para a AC de teste (e desfaz depois)."""
    (ROOT / "papiro.toml").write_text(f'[assinatura]\nraizes = "{pki_teste["ancoras"]}"\n', encoding="utf-8")
    config.carregar.cache_clear()
    yield pki_teste
    (ROOT / "papiro.toml").unlink(missing_ok=True)
    config.carregar.cache_clear()


def _assinado_com_carimbo(pki, tsa, out_dir) -> str:
    e = envelope_ok(S.sign(str(CORPUS / "bom.pdf"), out_dir, pfx=pki["pfx"], senha_ref=pki["senha_ref"],
                           confirm=True, carimbo=True, tsa=tsa))
    assert e["ok"], e.get("error")
    return e["outputs"][0]["path"]


def test_ltv_update_busca_revogacao_e_grava_no_documento(com_ancoras, out_dir, pdf_bom):
    """B-LT: a prova de validade do certificado passa a morar dentro do PDF."""
    assinado = _assinado_com_carimbo(com_ancoras, com_ancoras["tsa"], out_dir)
    com_ancoras["estado"]["pedidos_crl"] = 0
    e = envelope_ok(S.ltv_update(assinado, out_dir, confirm=True))
    assert e["ok"], e.get("error")
    assert e["dados"]["perfil"] == "PAdES-B-LT"
    assert com_ancoras["estado"]["pedidos_crl"] >= 1                 # foi buscar a CRL na AC, de verdade
    dss = e["dados"]["dss"]
    assert dss["crls"] >= 1 and dss["certificados"] >= 2             # a CRL e a cadeia ficaram guardadas
    assert e["warnings"] and "revogacao" in e["warnings"][0].lower()


def test_ltv_update_lta_acrescenta_carimbo_de_arquivo(com_ancoras, out_dir, pdf_bom):
    """B-LTA: B-LT mais um carimbo do tempo por cima, que e o que estende a validade no tempo."""
    assinado = _assinado_com_carimbo(com_ancoras, com_ancoras["tsa"], out_dir)
    e = envelope_ok(S.ltv_update(assinado, out_dir, confirm=True, lta=True, tsa=com_ancoras["tsa"]))
    assert e["ok"], e.get("error")
    assert e["dados"]["perfil"] == "PAdES-B-LTA" and e["dados"]["dss"]["crls"] >= 1
    tipos = [v["tipo"] for v in e["dados"]["verificacao"]]
    assert tipos.count("carimbo_do_documento") == 1 and tipos[0] == "assinatura"
    assert all(v["intacta"] for v in e["dados"]["verificacao"])


def test_assinar_direto_em_lta(com_ancoras, out_dir, pdf_bom):
    """sign ... ltv='lta' faz tudo de uma vez: assina, carimba e ja guarda a revogacao."""
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=com_ancoras["pfx"], senha_ref=com_ancoras["senha_ref"],
                           confirm=True, carimbo=True, tsa=com_ancoras["tsa"], ltv="lta"))
    assert e["ok"], e.get("error")
    assert e["dados"]["perfil"] == "PAdES-B-LTA" and e["dados"]["dss"]["crls"] >= 1
    assert e["dados"]["carimbo"]["intacto"]


def test_ltv_precisa_de_ancora_e_de_assinatura(out_dir, pdf_bom, pfx_teste):
    """Sem ancora nao da para montar a cadeia; sem assinatura nao ha o que provar. As duas dizem o porque."""
    sem_assinatura = envelope_ok(S.ltv_update(str(pdf_bom), out_dir, confirm=True))
    assert sem_assinatura["error"]["code"] == "E_ENTRADA" and "assinatura" in sem_assinatura["error"]["message"]
    autoassinado = envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste),
                                      senha_ref="env:PAPIRO_TESTE_PFX_SENHA", confirm=True))["outputs"][0]["path"]
    e = envelope_ok(S.ltv_update(autoassinado, out_dir, confirm=True))
    assert e["error"]["code"] in ("E_CONFORMIDADE", "E_MOTOR")
    assert "cadeia" in e["error"]["message"].lower() or "ancora" in e["error"]["message"].lower()


def test_ltv_em_job_sensivel_exige_autorizacao(com_ancoras, out_dir, pdf_bom):
    """§12.5: buscar revogacao e rede. Em job sensivel so acontece com rede_ltv=true, e o aviso diz o que vaza."""
    assinado = _assinado_com_carimbo(com_ancoras, com_ancoras["tsa"], out_dir)
    flag = WORK / "_sensivel.flag"
    WORK.mkdir(parents=True, exist_ok=True)
    flag.write_text("teste", encoding="utf-8")
    try:
        bloqueado = envelope_ok(S.ltv_update(assinado, out_dir, confirm=True))
        assert bloqueado["error"]["code"] == "E_POLITICA" and "rede_ltv=true" in bloqueado["error"]["message"]
        assert "certificado" in bloqueado["error"]["message"].lower()
        liberado = envelope_ok(S.ltv_update(assinado, out_dir, confirm=True, rede_ltv=True))
        assert liberado["ok"] and liberado["dados"]["perfil"] == "PAdES-B-LT"
    finally:
        flag.unlink(missing_ok=True)


def test_ltv_exige_confirmacao(com_ancoras, out_dir, pdf_bom):
    assinado = _assinado_com_carimbo(com_ancoras, com_ancoras["tsa"], out_dir)
    assert envelope_ok(S.ltv_update(assinado, out_dir))["error"]["code"] == "E_POLITICA"
