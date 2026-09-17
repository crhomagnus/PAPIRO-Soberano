# -*- coding: utf-8 -*-
"""Servidor MCP `papiro-seguranca` - 10 ferramentas sensiveis (PRD §8.4), so dentro do subagente pdf-seguranca.

Regras §12: operacao sensivel exige confirm=true; documento reprovado nos portoes nao e assinado; senha de PFX (A1)
e PIN de token (A3) nunca entram como argumento - vem de keyring, variavel de ambiente ou do terminal no ato - e nunca
vao para log; verificacao sempre local (allow_fetching=False); retangulo preto sem remocao e proibido."""
from __future__ import annotations
import contextlib, json, os, pathlib, sys
from mcp.server.fastmcp import FastMCP
from . import FONTS, REPO, config
from .caminhos import nome_seguro
from .erros import PapiroErro
from .runner import Contexto, Resultado, executar
from .adapters import convert as CONV, edit as ED, pii as PII, qa as QA

mcp = FastMCP("papiro-seguranca", instructions=(
    "Operacoes sensiveis do PAPIRO: assinatura PAdES, criptografia, tarjamento LGPD e sanitizacao. "
    "Toda operacao que altera documento exige confirm=true dado pelo usuario. Nunca peca PIN/senha no chat."))

OPERACOES_SENSIVEIS = {"sign", "certify", "timestamp", "ltv_update", "encrypt", "decrypt", "redact_apply", "sanitize"}


def _confirmar(op: str, confirm: bool):
    if op in OPERACOES_SENSIVEIS and not (confirm or os.environ.get("PAPIRO_CONFIRM") == "1"):
        raise PapiroErro("E_POLITICA", f"{op} e sensivel: exige confirmacao explicita do usuario (confirm=true)")


def _json(ctx: Contexto, nome: str, dados) -> pathlib.Path:
    p = ctx.saida(nome)
    p.write_text(json.dumps(dados, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return p


def _segredo(ref: str) -> str:
    """ref = 'env:NOME' ou 'keyring:servico/usuario'. O valor nunca aparece em envelope nem log."""
    if ref.startswith("env:"):
        valor = os.environ.get(ref[4:])
    elif ref.startswith("keyring:"):
        try:
            import keyring
            servico, _, usuario = ref[8:].partition("/")
            valor = keyring.get_password(servico, usuario)
        except Exception:
            valor = None
    else:
        raise PapiroErro("E_POLITICA", "senha so por referencia: 'env:NOME' ou 'keyring:servico/usuario'")
    if not valor:
        raise PapiroErro("E_SENHA", "segredo referenciado nao encontrado")
    return valor


MODULOS_PKCS11 = (  # caminhos usuais dos tokens/cartoes A3; o do usuario vem antes (argumento, env ou papiro.toml)
    r"C:\Windows\System32\eTPKCS11.dll",            # SafeNet/Gemalto (eToken, boa parte dos A3 ICP-Brasil)
    r"C:\Windows\System32\aetpkss1.dll",            # Athena/SafeSign
    r"C:\Windows\System32\WDPKCS.dll",              # Watchdata
    r"C:\Windows\System32\asepkcs.dll",             # Athena ASE
    r"C:\Windows\System32\opensc-pkcs11.dll",
    "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so", "/usr/lib/opensc-pkcs11.so", "/usr/lib64/opensc-pkcs11.so",
    "/usr/lib/softhsm/libsofthsm2.so",              # so para teste: token de software
)


def _modulo_pkcs11(modulo: str) -> str:
    """Biblioteca PKCS#11 do token A3: argumento > PAPIRO_PKCS11_MODULO > papiro.toml > caminhos usuais."""
    for origem, valor in (("argumento modulo", modulo), ("PAPIRO_PKCS11_MODULO", os.environ.get("PAPIRO_PKCS11_MODULO", "")),
                          ("papiro.toml [assinatura] pkcs11_modulo",
                           config.carregar().get("assinatura", {}).get("pkcs11_modulo", ""))):
        if valor:
            p = pathlib.Path(valor).expanduser()
            if not p.exists():
                raise PapiroErro("E_ENTRADA", f"modulo PKCS#11 do {origem} nao existe: {valor}")
            return str(p)
    for c in MODULOS_PKCS11:
        if pathlib.Path(c).exists():
            return c
    raise PapiroErro("E_ENTRADA", "token A3: informe a biblioteca PKCS#11 (modulo='C:\\\\Windows\\\\System32\\\\eTPKCS11.dll' "
                                  "ou [assinatura] pkcs11_modulo no papiro.toml). Ela vem do driver do seu token.")


def _pin(pin_ref: str) -> str:
    """PIN do token: 'env:NOME', 'keyring:servico/usuario' ou 'prompt' (digitado no ato, so em terminal). Nunca gravado."""
    if pin_ref == "prompt":
        if not sys.stdin.isatty():
            raise PapiroErro("E_POLITICA", "pin_ref='prompt' so funciona em terminal; no MCP use 'env:NOME' ou 'keyring:servico/usuario'")
        import getpass
        valor = getpass.getpass("PIN do token A3 (nao aparece na tela, nao e gravado): ")
        if not valor:
            raise PapiroErro("E_SENHA", "PIN vazio")
        return valor
    return _segredo(pin_ref)


def tokens_conectados(lib_location: str) -> list[dict]:
    """Tokens/cartoes presentes na biblioteca PKCS#11 (rotulo, fabricante, serie)."""
    from pyhanko.sign.pkcs11 import p11_lib

    def texto(v) -> str:
        return (v.decode("utf-8", "replace") if isinstance(v, bytes) else (v or "")).strip()
    itens = []
    for slot in p11_lib(lib_location).get_slots(token_present=True):
        try:
            t = slot.get_token()
        except Exception:  # noqa: BLE001 - slot sem token legivel
            continue
        rotulo = texto(t.label)
        if not rotulo:
            continue  # slot com token nao inicializado (nao serve para assinar)
        itens.append({"rotulo": rotulo, "fabricante": texto(t.manufacturer_id), "serie": texto(t.serial),
                      "slot": getattr(slot, "slot_id", None)})
    return itens


def _criterio_token(lib: str, rotulo: str, slot: int | None):
    """Sem rotulo e sem slot, usa o unico token conectado; com varios, exige escolha."""
    from pyhanko.config.pkcs11 import TokenCriteria
    if slot is not None:
        return None
    conectados = tokens_conectados(lib)
    if rotulo:
        if conectados and rotulo not in [t["rotulo"] for t in conectados]:
            lista = ", ".join(repr(t["rotulo"]) for t in conectados) or "nenhum"
            raise PapiroErro("E_ENTRADA", f"token {rotulo!r} nao esta conectado. Conectados: {lista}")
        return TokenCriteria(label=rotulo)
    if not conectados:
        raise PapiroErro("E_ENTRADA", "nenhum token A3 conectado (confira o cabo/leitora e o driver do fabricante)")
    if len(conectados) > 1:
        lista = "; ".join(f"{t['rotulo']!r} ({t['fabricante']})" for t in conectados)
        raise PapiroErro("E_ENTRADA", f"ha {len(conectados)} tokens conectados: escolha com token=<rotulo>. {lista}")
    return TokenCriteria(label=conectados[0]["rotulo"])


def _erro_pkcs11(e: Exception) -> PapiroErro:
    nome = type(e).__name__
    if nome == "PKCS11Error" and "token" in str(e).lower():
        return PapiroErro("E_ENTRADA", f"token A3 nao encontrado: {e}")
    if nome in ("PinIncorrect", "PinInvalid", "PinLenRange", "PinExpired"):
        return PapiroErro("E_SENHA", f"PIN recusado pelo token ({nome}). Atencao: tokens bloqueiam apos poucas tentativas")
    if nome in ("PinLocked",):
        return PapiroErro("E_SENHA", "PIN bloqueado no token: desbloqueie com o gerenciador do fabricante")
    if nome in ("TokenNotPresent", "NoSuchToken", "SlotIDInvalid", "TokenNotRecognised"):
        return PapiroErro("E_ENTRADA", f"token A3 nao encontrado ({nome}): confira se esta conectado e o rotulo em token=")
    if nome in ("DeviceError", "DeviceRemoved", "SessionHandleInvalid"):
        return PapiroErro("E_MOTOR", f"falha de comunicacao com o token ({nome})")
    return PapiroErro("E_MOTOR", f"PKCS#11: {nome}")


def certificados_do_token(sessao) -> list[dict]:
    """Certificados gravados no token (rotulo, id, titular, validade) - nenhuma chave privada sai do token."""
    from asn1crypto import x509 as ax509
    from pkcs11 import Attribute, ObjectClass
    itens = []
    for obj in sessao.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
        item = {"rotulo": None, "id": None, "titular": None, "emissor": None, "valido_ate": None}
        for chave, attr in (("rotulo", Attribute.LABEL), ("id", Attribute.ID)):
            try:
                v = obj[attr]
                item[chave] = v.hex() if isinstance(v, bytes) and chave == "id" else v
            except Exception:  # noqa: BLE001 - atributo ausente no token
                pass
        try:
            cert = ax509.Certificate.load(obj[Attribute.VALUE])
            item["titular"] = cert.subject.human_friendly
            item["emissor"] = cert.issuer.human_friendly
            item["valido_ate"] = cert["tbs_certificate"]["validity"]["not_after"].native.isoformat()
        except Exception:  # noqa: BLE001 - certificado ilegivel no token
            pass
        itens.append(item)
    return itens


def _escolher_certificado(sessao, rotulo: str, id_chave: str) -> dict:
    achados = certificados_do_token(sessao)
    if not achados:
        raise PapiroErro("E_ENTRADA", "o token nao tem nenhum certificado gravado")
    filtrados = [c for c in achados
                 if (not rotulo or c["rotulo"] == rotulo) and (not id_chave or c["id"] == id_chave.lower())]
    if not filtrados:
        disponiveis = "; ".join(f"rotulo={c['rotulo']!r} id={c['id']} titular={c['titular']}" for c in achados)
        raise PapiroErro("E_ENTRADA", f"certificado nao encontrado no token. Disponiveis: {disponiveis}")
    if len(filtrados) > 1:
        disponiveis = "; ".join(f"rotulo={c['rotulo']!r} id={c['id']} titular={c['titular']}" for c in filtrados)
        raise PapiroErro("E_ENTRADA", f"o token tem {len(filtrados)} certificados: escolha com rotulo= ou id_chave=. {disponiveis}")
    return filtrados[0]


@contextlib.contextmanager
def _abrir_credencial(ctx: Contexto, cred: dict):
    """Entrega o assinante pronto: A1 le o PFX; A3 abre sessao no token e a fecha no fim. Segredo nunca fica vivo."""
    from pyhanko.sign import signers
    if cred["tipo"] == "a1":
        senha = _segredo(cred["senha_ref"])
        try:
            signer = signers.SimpleSigner.load_pkcs12(pfx_file=str(ctx.entradas[1]), passphrase=senha.encode())
        finally:
            senha = None  # noqa: F841 - nao manter o segredo vivo
        if signer is None:
            raise PapiroErro("E_SENHA", "PFX nao abriu com o segredo informado")
        yield signer, {"tipo": "a1", "arquivo": ctx.entradas[1].name}
        return
    from pyhanko.sign import pkcs11 as p11
    lib = _modulo_pkcs11(cred["modulo"])
    criterio = _criterio_token(lib, cred["token"], cred["slot"])
    rotulo_token = cred["token"] or getattr(criterio, "label", None)
    pin = _pin(cred["pin_ref"])
    try:
        sessao = p11.open_pkcs11_session(lib, slot_no=cred["slot"], token_criteria=criterio, user_pin=pin)
    except PapiroErro:
        raise
    except Exception as e:  # noqa: BLE001 - erro do driver do token
        raise _erro_pkcs11(e)
    finally:
        pin = None  # noqa: F841 - PIN nunca permanece em memoria nossa nem em log
    try:
        escolhido = _escolher_certificado(sessao, cred["rotulo"], cred["id_chave"])
        ident = {"cert_id": bytes.fromhex(escolhido["id"]), "key_id": bytes.fromhex(escolhido["id"])} if escolhido["id"] \
            else {"cert_label": escolhido["rotulo"], "key_label": escolhido["rotulo"]}
        try:
            signer = p11.PKCS11Signer(sessao, **ident)
        except Exception as e:  # noqa: BLE001 - erro do driver do token
            raise _erro_pkcs11(e)
        yield signer, {"tipo": "a3", "modulo": pathlib.Path(lib).name, "token": rotulo_token, "slot": cred["slot"],
                       "rotulo": escolhido["rotulo"], "id": escolhido["id"], "titular": escolhido["titular"],
                       "emissor": escolhido["emissor"], "valido_ate": escolhido["valido_ate"]}
    finally:
        try:
            sessao.close()
        except Exception:  # noqa: BLE001 - sessao ja encerrada
            pass


def _area_livre(pdf: pathlib.Path, pagina: int, caixa_pdf: tuple[float, float, float, float]) -> bool:
    """Caixa em coordenadas PDF (origem embaixo): livre se nao ha texto, imagem nem desenho nela."""
    import fitz
    with fitz.open(pdf) as d:
        page = d[pagina - 1]
        x0, y0, x1, y1 = caixa_pdf
        r = fitz.Rect(x0, page.rect.height - y1, x1, page.rect.height - y0)
        if page.get_text("text", clip=r).strip():
            return False
        if any(fitz.Rect(ir).intersects(r) for img in page.get_images(full=True) for ir in page.get_image_rects(img[0])):
            return False
        return not any(fitz.Rect(dr["rect"]).intersects(r) for dr in page.get_drawings())


def _assinar(ctx: Contexto, cred: dict, certificar: bool, visivel: bool, pagina: int, caixa: str,
             nome_campo: str, motivo: str, local: str, crm: str, url_validacao: str, exigir_qa: bool) -> Resultado:
    from pyhanko import stamp
    from pyhanko.pdf_utils.font.opentype import GlyphAccumulatorFactory
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.pdf_utils.text import TextBoxStyle
    from pyhanko.sign import fields, signers
    entrada = ctx.entradas[0]
    if exigir_qa:
        q = QA.run(entrada)
        if q["status"] != "APROVADO":
            raise PapiroErro("E_POLITICA", f"documento reprovado nos portoes ({', '.join(q['bloqueantes'])}): nao assina")
    spec = fields.SigFieldSpec(nome_campo)
    estilo = None
    if visivel:
        try:
            x0, y0, x1, y1 = [float(v) for v in caixa.split(",")]
        except ValueError:
            raise PapiroErro("E_ENTRADA", "caixa deve ser 'x0,y0,x1,y1' em pt (origem no canto inferior esquerdo)")
        if not _area_livre(entrada, pagina, (x0, y0, x1, y1)):
            raise PapiroErro("E_POLITICA", "aparencia da assinatura cairia sobre o conteudo: escolha area livre")
        spec = fields.SigFieldSpec(nome_campo, on_page=pagina - 1, box=(x0, y0, x1, y1))
        texto = "Assinado digitalmente por:\n%(signer)s\n" + (f"CRM {crm}\n" if crm else "") + "%(ts)s"
        caixa_texto = TextBoxStyle(font=GlyphAccumulatorFactory(str(FONTS / "LiberationSans-Regular.ttf")), font_size=7)
        if url_validacao:
            estilo = stamp.QRStampStyle(stamp_text=texto + "\nValide: %(url)s", text_box_style=caixa_texto, border_width=0)
        else:
            estilo = stamp.TextStampStyle(stamp_text=texto, text_box_style=caixa_texto, border_width=0)
    meta = signers.PdfSignatureMetadata(field_name=nome_campo, subfilter=fields.SigSeedSubFilter.PADES,
                                        md_algorithm="sha256", certify=certificar, reason=motivo or None,
                                        location=local or None,
                                        docmdp_permissions=fields.MDPPerm.FILL_FORMS)
    out = ctx.saida(("certificado" if certificar else "assinado") + ".pdf")
    with _abrir_credencial(ctx, cred) as (signer, descricao):
        try:
            with open(entrada, "rb") as inf, open(out, "wb") as outf:
                w = IncrementalPdfFileWriter(inf, strict=False)
                signers.PdfSigner(meta, signer=signer, stamp_style=estilo, new_field_spec=spec).sign_pdf(
                    w, output=outf, appearance_text_params={"url": url_validacao} if url_validacao else None)
        except PapiroErro:
            raise
        except Exception as e:  # noqa: BLE001 - falha do token no meio da assinatura
            if cred["tipo"] == "a3" and type(e).__module__.startswith("pkcs11"):
                raise _erro_pkcs11(e)
            raise
    verif = _verificar(out)
    if not verif or not all(s["intacta"] and s["valida"] for s in verif):
        raise PapiroErro("E_CONFORMIDADE", "assinatura gerada nao passou na verificacao local")
    return Resultado(outputs=[out], motor="pyhanko", dados={"perfil": "PAdES-B-B", "certificado": certificar,
                                                             "credencial": descricao, "verificacao": verif})


def _e_a3(token: str, modulo: str, pin_ref: str, rotulo: str, id_chave: str, slot: int | None) -> bool:
    return bool(token or modulo or pin_ref or rotulo or id_chave or slot is not None)


def _credencial(pfx: str, senha_ref: str, token: str, modulo: str, pin_ref: str, rotulo: str, id_chave: str,
                slot: int | None) -> dict:
    """A3 (token/cartao via PKCS#11) quando houver qualquer dado de token; senao A1 (arquivo PFX)."""
    if _e_a3(token, modulo, pin_ref, rotulo, id_chave, slot):
        if pfx:
            raise PapiroErro("E_ENTRADA", "escolha uma credencial: PFX (A1) ou token (A3), nao as duas")
        if not pin_ref:
            raise PapiroErro("E_POLITICA", "informe pin_ref: 'env:NOME', 'keyring:servico/usuario' ou 'prompt' "
                                           "(o PIN nunca e gravado nem registrado em log)")
        return {"tipo": "a3", "token": token, "modulo": modulo, "pin_ref": pin_ref, "rotulo": rotulo,
                "id_chave": id_chave, "slot": slot}
    if not pfx or not senha_ref:
        raise PapiroErro("E_ENTRADA", "informe a credencial: A1 com pfx= e senha_ref=, ou A3 com token=/modulo= e pin_ref=")
    return {"tipo": "a1", "senha_ref": senha_ref}


def _raizes() -> list:
    from pyhanko.keys import load_certs_from_pemder
    pasta = pathlib.Path(config.carregar().get("assinatura", {}).get("raizes", "certs/icp-brasil")).expanduser()
    if not pasta.is_absolute():
        pasta = REPO / pasta
    arquivos = [p for p in pasta.glob("*") if p.suffix.lower() in (".crt", ".cer", ".pem", ".der")] if pasta.exists() else []
    return list(load_certs_from_pemder([str(p) for p in arquivos])) if arquivos else []


def _verificar(pdf: pathlib.Path) -> list[dict]:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    raizes = _raizes()
    saida = []
    with open(pdf, "rb") as fh:
        leitor = PdfFileReader(fh, strict=False)
        for sig in leitor.embedded_signatures:
            vc = ValidationContext(trust_roots=raizes or None, allow_fetching=False, revocation_mode="soft-fail")
            st = validate_pdf_signature(sig, vc)
            saida.append({
                "campo": sig.field_name, "intacta": bool(st.intact), "valida": bool(st.valid),
                "confiavel": bool(st.trusted), "cobertura": getattr(st.coverage, "name", str(st.coverage)),
                "modificacao": getattr(st.modification_level, "name", None),
                "signatario": st.signing_cert.subject.human_friendly if st.signing_cert else None,
                "emissor": st.signing_cert.issuer.human_friendly if st.signing_cert else None,
                "data_declarada": str(st.signer_reported_dt) if st.signer_reported_dt else None,
                "algoritmo": st.md_algorithm, "resumo": st.bottom_line,
                "ancoras": "ICP-Brasil carregadas" if raizes else "nenhuma ancora carregada: confiavel sempre falso"})
    return saida


# ================= 10 ferramentas =================
@mcp.tool()
def sign(entrada: str, out_dir: str, pfx: str = "", senha_ref: str = "", confirm: bool = False, visivel: bool = False,
         pagina: int = 1, caixa: str = "", crm: str = "", url_validacao: str = "https://validar.iti.gov.br",
         motivo: str = "", local: str = "", nome_campo: str = "Assinatura1", token: str = "", modulo: str = "",
         pin_ref: str = "", rotulo: str = "", id_chave: str = "", slot: int | None = None,
         dry_run: bool = False) -> dict:
    """RF-806 PAdES-B-B. A1: pfx= + senha_ref='env:NOME'|'keyring:servico/usuario'.
    A3 (token/cartao ICP-Brasil): token=<rotulo do token> e/ou modulo=<biblioteca PKCS#11> + pin_ref=(env:|keyring:|prompt);
    rotulo=/id_chave= escolhem o certificado quando o token tem mais de um. O PIN nunca e gravado nem vai para log."""
    def acao(ctx):
        _confirmar("sign", confirm)
        cred = _credencial(pfx, senha_ref, token, modulo, pin_ref, rotulo, id_chave, slot)
        return _assinar(ctx, cred, False, visivel, pagina, caixa, nome_campo, motivo, local, crm,
                        url_validacao if visivel else "", exigir_qa=True)
    return executar("sign", "pades-b-b" + ("-a3" if _e_a3(token, modulo, pin_ref, rotulo, id_chave, slot) else ""), acao,
                    entradas=[entrada] + ([pfx] if pfx else []), out_dir=out_dir, tarefa="assinatura", dry_run=dry_run)


@mcp.tool()
def certify(entrada: str, out_dir: str, pfx: str = "", senha_ref: str = "", confirm: bool = False,
            nome_campo: str = "Certificacao", token: str = "", modulo: str = "", pin_ref: str = "", rotulo: str = "",
            id_chave: str = "", slot: int | None = None, dry_run: bool = False) -> dict:
    """Assinatura de certificacao DocMDP (permite so preenchimento e novas assinaturas). A1 (pfx) ou A3 (token), como em sign."""
    def acao(ctx):
        _confirmar("certify", confirm)
        cred = _credencial(pfx, senha_ref, token, modulo, pin_ref, rotulo, id_chave, slot)
        return _assinar(ctx, cred, True, False, 1, "", nome_campo, "Certificacao", "", "", "", exigir_qa=True)
    return executar("certify", "docmdp", acao, entradas=[entrada] + ([pfx] if pfx else []), out_dir=out_dir,
                    tarefa="assinatura", dry_run=dry_run)


@mcp.tool()
def timestamp(entrada: str, out_dir: str, confirm: bool = False, dry_run: bool = False) -> dict:
    """RFC 3161: sem suporte nesta versao (exige TSA configurada e acesso a rede; job sensivel e soberano)."""
    def acao(_ctx):
        _confirmar("timestamp", confirm)
        raise PapiroErro("E_SEM_SUPORTE", "carimbo do tempo exige TSA RFC 3161 configurada em papiro.toml [assinatura]")
    return executar("timestamp", "rfc3161", acao, entradas=[entrada], out_dir=out_dir, tarefa="assinatura", dry_run=dry_run)


@mcp.tool()
def ltv_update(entrada: str, out_dir: str, confirm: bool = False, dry_run: bool = False) -> dict:
    """B-LT/B-LTA: sem suporte nesta versao (exige buscar revogacao on-line)."""
    def acao(_ctx):
        _confirmar("ltv_update", confirm)
        raise PapiroErro("E_SEM_SUPORTE", "LTV exige dados de revogacao (OCSP/CRL) buscados on-line")
    return executar("ltv_update", "b-lta", acao, entradas=[entrada], out_dir=out_dir, tarefa="assinatura", dry_run=dry_run)


@mcp.tool()
def verify(entrada: str, out_dir: str, dry_run: bool = False) -> dict:
    """RF-807: integridade, cobertura, modificacoes, signatario e cadeia (ancoras ICP-Brasil locais em certs/)."""
    def acao(ctx):
        r = _verificar(ctx.entradas[0])
        return Resultado(outputs=[_json(ctx, "verificacao.json", r)], motor="pyhanko",
                         dados={"assinaturas": r}, warnings=[] if r else ["documento sem assinaturas"])
    return executar("verify", "local", acao, entradas=[entrada], out_dir=out_dir, tarefa="assinatura", dry_run=dry_run)


@mcp.tool()
def encrypt(entrada: str, out_dir: str, confirm: bool = False, senha_ref: str = "", imprimir: bool = True,
            copiar: bool = False, editar: bool = False, dry_run: bool = False) -> dict:
    """RF-805 AES-256. Sem senha_ref gera senha forte (devolvida uma unica vez, nunca registrada)."""
    def acao(ctx):
        _confirmar("encrypt", confirm)
        out = ctx.saida("protegido.pdf")
        r = CONV.criptografar(ctx.entradas[0], out, _segredo(senha_ref) if senha_ref else "",
                              imprimir=imprimir, copiar=copiar, editar=editar)
        return Resultado(outputs=[out], motor="pikepdf", dados=r, warnings=[r["aviso"]])
    return executar("encrypt", "aes-256", acao, entradas=[entrada], out_dir=out_dir, tarefa="seguranca", dry_run=dry_run)


@mcp.tool()
def decrypt(entrada: str, out_dir: str, senha: str, confirm: bool = False, dry_run: bool = False) -> dict:
    """Remove a senha somente com a senha correta (sem quebra)."""
    def acao(ctx):
        _confirmar("decrypt", confirm)
        out = ctx.saida("sem_senha.pdf")
        CONV.decriptar(ctx.entradas[0], out, senha)
        return Resultado(outputs=[out], motor="pikepdf")
    return executar("decrypt", "senha", acao, entradas=[entrada], out_dir=out_dir, tarefa="seguranca", dry_run=dry_run)


@mcp.tool()
def redact_detect(entrada: str, out_dir: str, dry_run: bool = False) -> dict:
    """§12.3 passos 1-2: detecta dados pessoais e gera PDF de revisao com caixas coloridas + caixas.json para aprovar."""
    def acao(ctx):
        achados = PII.detectar_pdf(ctx.entradas[0])
        revisao = ctx.saida("revisao_tarja.pdf")
        PII.pdf_revisao(ctx.entradas[0], achados, revisao)
        caixas = _json(ctx, "caixas.json", achados)
        motor = "presidio+regex" if any(a["motor"].startswith("presidio") for a in achados) else "regex-pii"
        return Resultado(outputs=[caixas, revisao], motor=motor,
                         dados={"achados": len(achados), "categorias": sorted({a["categoria"] for a in achados})})
    return executar("redact_detect", "detectar", acao, entradas=[entrada], out_dir=out_dir, tarefa="pii", dry_run=dry_run)


@mcp.tool()
def redact_apply(entrada: str, out_dir: str, confirm: bool = False, caixas_json: str = "", caixas_arquivo: str = "",
                 saida: str = "tarjado.pdf", dry_run: bool = False) -> dict:
    """§12.3 passos 4-5: remocao real sob as caixas aprovadas, re-extracao e limpeza; nome sem dado pessoal."""
    entradas = [entrada] + ([caixas_arquivo] if caixas_arquivo else [])

    def acao(ctx):
        _confirmar("redact_apply", confirm)
        caixas = json.loads(ctx.entradas[1].read_text(encoding="utf-8") if caixas_arquivo else (caixas_json or "[]"))
        nome = nome_seguro(saida, "tarjado.pdf")
        avisos = []
        stem = pathlib.Path(nome).stem
        if (PII.detectar_texto(stem, usar_presidio=False)
                or PII.detectar_texto(stem.replace("_", " "), usar_presidio=False)):
            avisos.append("nome de saida continha dado pessoal: substituido por 'tarjado.pdf'")
            nome = "tarjado.pdf"
        out = ctx.saida(nome)
        r = ED.tarjar(ctx.entradas[0], out, caixas)
        return Resultado(outputs=[out], motor="pymupdf-redact", dados=r, warnings=avisos)
    return executar("redact_apply", "aplicar", acao, entradas=entradas, out_dir=out_dir, tarefa="tarjamento", dry_run=dry_run)


@mcp.tool()
def sanitize(entrada: str, out_dir: str, confirm: bool = False, manter_metadados_basicos: bool = True,
             dry_run: bool = False) -> dict:
    """RF-809: remove JavaScript, acoes, anexos, XFA, XMP, miniaturas e dados privados; exige triagem RF-009 limpa."""
    def acao(ctx):
        _confirmar("sanitize", confirm)
        out = ctx.saida("sanitizado.pdf")
        r = CONV.sanitizar(ctx.entradas[0], out, manter_metadados_basicos)
        return Resultado(outputs=[out], motor="pikepdf", dados=r)
    return executar("sanitize", "limpar", acao, entradas=[entrada], out_dir=out_dir, tarefa="seguranca", dry_run=dry_run)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
