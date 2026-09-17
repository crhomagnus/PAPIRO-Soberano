# -*- coding: utf-8 -*-
"""Carimbo do tempo RFC 3161 (PRD §12.1): PAdES-B-T e carimbo do documento.

A TSA dos testes e um servidor RFC 3161 de verdade em 127.0.0.1 (pyHanko DummyTimeStamper atras de um HTTP
comum), entao o caminho testado e o mesmo de uma TSA da internet - pedido HTTP, resposta DER, carimbo embutido -
sem depender de rede nem de servico pago."""
import datetime, http.server, socket, threading
import pytest
from papiro_core import WORK, config, mcp_seguranca as S
from conftest import envelope_ok


def _tsa_de_teste():
    """Certificado de TSA (EKU timeStamping, como manda a RFC 3161) + carimbador local."""
    from asn1crypto import keys as a_keys, x509 as a_x509
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    from pyhanko.sign.timestamps import DummyTimeStamper
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Autoridade de Carimbo de Teste")])
    agora = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(agora - datetime.timedelta(days=1))
            .not_valid_after(agora + datetime.timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
            .sign(chave, hashes.SHA256()))
    return DummyTimeStamper(
        tsa_cert=a_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER)),
        tsa_key=a_keys.PrivateKeyInfo.load(chave.private_bytes(serialization.Encoding.DER,
                                                               serialization.PrivateFormat.PKCS8,
                                                               serialization.NoEncryption())))


@pytest.fixture(scope="session")
def tsa_local():
    """Sobe um servidor RFC 3161 em 127.0.0.1 e devolve a URL. Registra o que foi recebido, para conferir."""
    from asn1crypto import tsp
    carimbador = _tsa_de_teste()
    recebidos = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - nome exigido pelo BaseHTTPRequestHandler
            corpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            recebidos.append({"tipo": self.headers.get("Content-Type"), "bytes": corpo})
            try:
                resposta = carimbador.request_tsa_response(tsp.TimeStampReq.load(corpo)).dump()
            except Exception as e:  # noqa: BLE001 - devolve erro HTTP como uma TSA real faria
                self.send_error(400, str(e)[:80])
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/timestamp-reply")
            self.send_header("Content-Length", str(len(resposta)))
            self.end_headers()
            self.wfile.write(resposta)

        def log_message(self, *_):
            pass
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    porta = servidor.server_address[1]
    yield {"url": f"http://127.0.0.1:{porta}/tsr", "recebidos": recebidos}
    servidor.shutdown()


def _porta_fechada() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def test_assinatura_com_carimbo_vira_pades_b_t(tsa_local, pdf_bom, out_dir, pfx_teste):
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="env:PAPIRO_TESTE_PFX_SENHA",
                           confirm=True, carimbo=True, tsa=tsa_local["url"]))
    assert e["ok"], e.get("error")
    assert e["dados"]["perfil"] == "PAdES-B-T" and e["engine"]["name"] == "pyhanko+rfc3161"
    carimbo = e["dados"]["carimbo"]
    assert carimbo["intacto"] and carimbo["valido"] and "Carimbo de Teste" in carimbo["autoridade"]
    momento = datetime.datetime.fromisoformat(carimbo["tempo"])
    assert abs((datetime.datetime.now(datetime.timezone.utc) - momento).total_seconds()) < 300
    assert e["dados"]["verificacao"][0]["intacta"] and e["dados"]["verificacao"][0]["carimbo"]["tempo"]


def test_so_o_resumo_do_documento_vai_para_a_tsa(tsa_local, pdf_bom, out_dir, pfx_teste):
    """§12.5: a TSA recebe o hash, nunca o documento. O pedido tem que ser pequeno e nao conter o PDF."""
    from asn1crypto import tsp
    tsa_local["recebidos"].clear()
    envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="env:PAPIRO_TESTE_PFX_SENHA",
                       confirm=True, carimbo=True, tsa=tsa_local["url"]))
    # O pyHanko pede um carimbo de amostra para dimensionar o campo e depois o definitivo: 2 idas, nenhuma com o PDF.
    assert len(tsa_local["recebidos"]) >= 1
    documento = pdf_bom.read_bytes()
    for pedido in tsa_local["recebidos"]:
        assert pedido["tipo"] == "application/timestamp-query"
        assert len(pedido["bytes"]) < 200                           # um pedido RFC 3161 tem dezenas de bytes
        assert b"%PDF" not in pedido["bytes"] and documento[:64] not in pedido["bytes"]
        digest = tsp.TimeStampReq.load(pedido["bytes"])["message_imprint"]["hashed_message"].native
        assert len(digest) == 32                                    # SHA-256 do conteudo assinado, e so
        assert digest not in documento


def test_carimbo_do_documento_sem_assinar(tsa_local, pdf_bom, out_dir):
    e = envelope_ok(S.timestamp(str(pdf_bom), out_dir, confirm=True, tsa=tsa_local["url"]))
    assert e["ok"], e.get("error")
    assert e["dados"]["perfil"].startswith("DocTimeStamp") and e["dados"]["carimbo"]["intacto"]
    assert e["dados"]["verificacao"][-1]["tipo"] == "carimbo_do_documento"
    assert e["warnings"] and "resumo SHA-256" in e["warnings"][0]
    carimbado = e["outputs"][0]["path"]
    v = envelope_ok(S.verify(carimbado, out_dir))                   # verify enxerga o carimbo depois
    assert v["ok"] and v["dados"]["assinaturas"][-1]["tipo"] == "carimbo_do_documento"
    assert v["dados"]["assinaturas"][-1]["carimbo"]["tempo"]


def test_assinar_e_depois_carimbar_o_documento(tsa_local, pdf_bom, out_dir, pfx_teste):
    assinado = envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="env:PAPIRO_TESTE_PFX_SENHA",
                                  confirm=True))["outputs"][0]["path"]
    e = envelope_ok(S.timestamp(assinado, out_dir, confirm=True, tsa=tsa_local["url"]))
    assert e["ok"], e.get("error")
    tipos = [v["tipo"] for v in e["dados"]["verificacao"]]
    assert tipos == ["assinatura", "carimbo_do_documento"]          # assinatura preservada, carimbo por cima
    assert all(v["intacta"] for v in e["dados"]["verificacao"])


def test_erros_da_tsa(tsa_local, pdf_bom, out_dir, pfx_teste):
    a1 = {"pfx": str(pfx_teste), "senha_ref": "env:PAPIRO_TESTE_PFX_SENHA", "confirm": True}
    assert envelope_ok(S.timestamp(str(pdf_bom), out_dir, confirm=True))["error"]["code"] == "E_ENTRADA"
    e = envelope_ok(S.timestamp(str(pdf_bom), out_dir, confirm=True, tsa="ftp://tsa.exemplo"))
    assert e["error"]["code"] == "E_ENTRADA" and "RFC 3161" in e["error"]["message"]
    fechada = envelope_ok(S.timestamp(str(pdf_bom), out_dir, confirm=True, tsa=f"http://127.0.0.1:{_porta_fechada()}/tsr"))
    assert fechada["error"]["code"] in ("E_MOTOR", "E_TEMPO"), fechada["error"]
    assert "TSA" in fechada["error"]["message"] or "tsa" in fechada["error"]["message"].lower()
    assert envelope_ok(S.timestamp(str(pdf_bom), out_dir, tsa=tsa_local["url"]))["error"]["code"] == "E_POLITICA"
    ruim = envelope_ok(S.sign(str(pdf_bom), out_dir, carimbo=True, tsa="http://127.0.0.1:1/tsr", **a1))
    assert ruim["error"]["code"] in ("E_MOTOR", "E_TEMPO") and not ruim["ok"]


def test_job_sensivel_so_carimba_com_autorizacao_explicita(tsa_local, pdf_bom, out_dir, pfx_teste):
    """§12.5: job sensível não fala com serviço on-line. O carimbo só sai com rede_tsa=true."""
    flag = WORK / "_sensivel.flag"
    WORK.mkdir(parents=True, exist_ok=True)
    flag.write_text("teste", encoding="utf-8")
    try:
        a1 = {"pfx": str(pfx_teste), "senha_ref": "env:PAPIRO_TESTE_PFX_SENHA", "confirm": True}
        bloqueado = envelope_ok(S.sign(str(pdf_bom), out_dir, carimbo=True, tsa=tsa_local["url"], **a1))
        assert bloqueado["error"]["code"] == "E_POLITICA"
        assert "rede_tsa=true" in bloqueado["error"]["message"] and "SHA-256" in bloqueado["error"]["message"]
        liberado = envelope_ok(S.sign(str(pdf_bom), out_dir, carimbo=True, tsa=tsa_local["url"], rede_tsa=True, **a1))
        assert liberado["ok"] and liberado["dados"]["perfil"] == "PAdES-B-T"
    finally:
        flag.unlink(missing_ok=True)


def test_tsa_do_papiro_toml(tsa_local, pdf_bom, out_dir, pfx_teste, monkeypatch):
    """Sem tsa= no argumento, vale a do papiro.toml (ou PAPIRO_TSA_URL)."""
    monkeypatch.setenv("PAPIRO_TSA_URL", tsa_local["url"])
    config.carregar.cache_clear()
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="env:PAPIRO_TESTE_PFX_SENHA",
                           confirm=True, carimbo=True))
    assert e["ok"] and e["dados"]["carimbo"]["tsa"].startswith("127.0.0.1")
    config.carregar.cache_clear()


def test_assinatura_sem_carimbo_continua_b_b(pdf_bom, out_dir, pfx_teste):
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, pfx=str(pfx_teste), senha_ref="env:PAPIRO_TESTE_PFX_SENHA",
                           confirm=True))
    assert e["ok"] and e["dados"]["perfil"] == "PAdES-B-B" and e["engine"]["name"] == "pyhanko"
    assert e["dados"]["verificacao"][0]["carimbo"] is None and not e["warnings"]
