# -*- coding: utf-8 -*-
"""RF-806 com certificado A3 (token/cartao via PKCS#11).

O token de teste e um SoftHSM2 - token de software com a mesma interface PKCS#11 de um eToken ICP-Brasil.
Sem ele (outra maquina, Windows), os testes sao pulados; o codigo exercitado e exatamente o mesmo."""
import datetime, json, os, pathlib, shutil, subprocess
import pytest
from papiro_core import LOGS, mcp_seguranca as S
from papiro_core.erros import PapiroErro
from conftest import envelope_ok

MODULO = pathlib.Path("/usr/lib/softhsm/libsofthsm2.so")
ROTULO_TOKEN, ROTULO_CERT, PIN, ID = "PAPIRO-TESTE", "Certificado A3", "4321", "a1b2"


@pytest.fixture(scope="session")
def token_a3(tmp_path_factory):
    if not (MODULO.exists() and shutil.which("softhsm2-util") and shutil.which("pkcs11-tool")):
        pytest.skip("token A3 de teste exige softhsm2 + opensc (pkcs11-tool)")
    base = tmp_path_factory.mktemp("hsm")
    (base / "tokens").mkdir()
    (base / "softhsm2.conf").write_text(f"directories.tokendir = {base / 'tokens'}\n"
                                        "objectstore.backend = file\nlog.level = ERROR\n", encoding="utf-8")
    os.environ["SOFTHSM2_CONF"] = str(base / "softhsm2.conf")
    os.environ["PAPIRO_TESTE_PIN"] = PIN
    subprocess.run(["softhsm2-util", "--init-token", "--free", "--label", ROTULO_TOKEN,
                    "--so-pin", "1234", "--pin", PIN], check=True, capture_output=True)
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Teste PAPIRO A3 (autoassinado)")])
    agora = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(agora - datetime.timedelta(days=1))
            .not_valid_after(agora + datetime.timedelta(days=30))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(chave, hashes.SHA256()))
    (base / "k.der").write_bytes(chave.private_bytes(serialization.Encoding.DER,
                                                     serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (base / "c.der").write_bytes(cert.public_bytes(serialization.Encoding.DER))
    for arquivo, tipo in (("k.der", "privkey"), ("c.der", "cert")):
        subprocess.run(["pkcs11-tool", "--module", str(MODULO), "--token-label", ROTULO_TOKEN, "--login", "--pin", PIN,
                        "--write-object", str(base / arquivo), "--type", tipo, "--id", ID, "--label", ROTULO_CERT],
                       check=True, capture_output=True)
    return {"modulo": str(MODULO), "token": ROTULO_TOKEN, "pin_ref": "env:PAPIRO_TESTE_PIN"}


def test_lista_token_e_certificados(token_a3):
    conectados = S.tokens_conectados(token_a3["modulo"])
    assert [t["rotulo"] for t in conectados] == [ROTULO_TOKEN]   # slot nao inicializado nao entra na lista
    from pyhanko.sign import pkcs11 as p11
    sessao = p11.open_pkcs11_session(token_a3["modulo"], token_criteria=S._criterio_token(token_a3["modulo"], "", None),
                                     user_pin=PIN)
    try:
        certs = S.certificados_do_token(sessao)
    finally:
        sessao.close()
    assert len(certs) == 1 and certs[0]["rotulo"] == ROTULO_CERT and certs[0]["id"] == ID
    assert "Teste PAPIRO A3" in certs[0]["titular"] and certs[0]["valido_ate"] > datetime.date.today().isoformat()


def test_assina_com_token_e_verifica(token_a3, pdf_bom, out_dir):
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, **token_a3))
    assert e["ok"], e.get("error")
    cred = e["dados"]["credencial"]
    assert cred["tipo"] == "a3" and cred["token"] == ROTULO_TOKEN and cred["rotulo"] == ROTULO_CERT
    assinatura = e["dados"]["verificacao"][0]
    assert assinatura["intacta"] and assinatura["valida"] and "Teste PAPIRO A3" in assinatura["signatario"]
    assinado = e["outputs"][0]["path"]
    v = envelope_ok(S.verify(assinado, out_dir))
    assert v["ok"] and v["dados"]["assinaturas"][0]["cobertura"].startswith("ENTIRE")


def test_token_unico_dispensa_rotulo_e_certify_certifica(token_a3, pdf_bom, out_dir):
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, modulo=token_a3["modulo"], pin_ref=token_a3["pin_ref"]))
    assert e["ok"] and e["dados"]["credencial"]["token"] == ROTULO_TOKEN
    c = envelope_ok(S.certify(str(pdf_bom), out_dir, confirm=True, **token_a3))
    assert c["ok"] and c["dados"]["certificado"] is True and c["dados"]["verificacao"][0]["intacta"]


def test_aparencia_visivel_do_a3_nao_cobre_conteudo(token_a3, pdf_bom, out_dir):
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, visivel=True, caixa="380,40,560,100",
                           crm="12345/RS", **token_a3))
    assert e["ok"], e.get("error")
    assert envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, visivel=True, caixa="72,700,520,780",
                              **token_a3))["error"]["code"] == "E_POLITICA"


@pytest.mark.parametrize("kw,codigo,trecho", [
    ({"pin_ref": "env:NAO_EXISTE"}, "E_SENHA", "nao encontrado"),
    ({"pin_ref": "env:PATH"}, "E_SENHA", "PIN recusado"),
    ({"pin_ref": ""}, "E_POLITICA", "informe pin_ref"),
    ({"pin_ref": "4321"}, "E_POLITICA", "so por referencia"),
    ({"token": "NAO-EXISTE"}, "E_ENTRADA", "nao esta conectado"),
    ({"rotulo": "Outro"}, "E_ENTRADA", "certificado nao encontrado"),
    ({"modulo": "/nao/existe.so"}, "E_ENTRADA", "nao existe"),
])
def test_erros_do_token_viram_envelope(token_a3, pdf_bom, out_dir, kw, codigo, trecho):
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, **{**token_a3, **kw}))
    assert e["error"]["code"] == codigo and trecho in e["error"]["message"], e["error"]


def test_politica_do_a3(token_a3, pdf_bom, pdf_helv, out_dir, pfx_teste):
    """Sem confirmacao nao assina; A1 e A3 juntos e erro; documento reprovado nos portoes nao e assinado."""
    assert envelope_ok(S.sign(str(pdf_bom), out_dir, **token_a3))["error"]["code"] == "E_POLITICA"
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, pfx=str(pfx_teste), **token_a3))
    assert e["error"]["code"] == "E_ENTRADA" and "nao as duas" in e["error"]["message"]
    reprovado = envelope_ok(S.sign(str(pdf_helv), out_dir, confirm=True, **token_a3))
    assert reprovado["error"]["code"] == "E_POLITICA" and "reprovado nos portoes" in reprovado["error"]["message"]


def test_pin_nunca_aparece_em_log_nem_em_receita(token_a3, pdf_bom, out_dir):
    envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, **token_a3))
    from papiro_core import jobs as JOBS

    def percorrer(no, chaves: list, valores: list):
        if isinstance(no, dict):
            for chave, valor in no.items():
                chaves.append(str(chave))
                percorrer(valor, chaves, valores)
        elif isinstance(no, (list, tuple)):
            for item in no:
                percorrer(item, chaves, valores)
        else:
            valores.append(str(no))
    with JOBS._con() as c:
        planos = [json.loads(linha[0]) for linha in c.execute("SELECT plano FROM jobs") if linha[0]]
    trilha = [json.loads(l) for l in (LOGS / "audit.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert planos and trilha
    for registro in planos + trilha:
        chaves, valores = [], []
        percorrer(registro, chaves, valores)
        assert PIN not in valores, f"o PIN foi parar em {registro}"
        assert not [c for c in chaves if "pin" in c.lower() or "senha" in c.lower()], registro
        assert "PAPIRO_TESTE_PIN" not in valores    # nem a referencia do segredo entra no plano do job


def test_pin_prompt_exige_terminal(token_a3, pdf_bom, out_dir, monkeypatch):
    monkeypatch.setattr("sys.stdin", type("F", (), {"isatty": staticmethod(lambda: False)})())
    e = envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, **{**token_a3, "pin_ref": "prompt"}))
    assert e["error"]["code"] == "E_POLITICA" and "terminal" in e["error"]["message"]
    monkeypatch.setattr("sys.stdin", type("T", (), {"isatty": staticmethod(lambda: True)})())
    monkeypatch.setattr("getpass.getpass", lambda *_: PIN)
    assert envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True, **{**token_a3, "pin_ref": "prompt"}))["ok"]
    monkeypatch.setattr("getpass.getpass", lambda *_: "")
    assert envelope_ok(S.sign(str(pdf_bom), out_dir, confirm=True,
                              **{**token_a3, "pin_ref": "prompt"}))["error"]["code"] == "E_SENHA"


def test_modulo_pkcs11_vem_da_configuracao(monkeypatch, tmp_path):
    monkeypatch.setenv("PAPIRO_PKCS11_MODULO", str(MODULO) if MODULO.exists() else "")
    if MODULO.exists():
        assert S._modulo_pkcs11("") == str(MODULO)
    monkeypatch.setenv("PAPIRO_PKCS11_MODULO", str(tmp_path / "nao-existe.dll"))
    with pytest.raises(PapiroErro) as e:
        S._modulo_pkcs11("")
    assert e.value.codigo == "E_ENTRADA" and "PAPIRO_PKCS11_MODULO" in e.value.mensagem


def test_cli_token_lista(token_a3, capsys):
    from papiro_core import cli
    cli.token(modulo=token_a3["modulo"], pin_ref=token_a3["pin_ref"], certificados=True)
    saida = json.loads(capsys.readouterr().out)
    assert saida["ok"] and saida["tokens"][0]["certificados"][0]["rotulo"] == ROTULO_CERT
