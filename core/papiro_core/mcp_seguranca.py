# -*- coding: utf-8 -*-
"""Servidor MCP `papiro-seguranca` - 10 ferramentas sensiveis (PRD §8.4), so dentro do subagente pdf-seguranca.

Regras §12: operacao sensivel exige confirm=true; documento reprovado nos portoes nao e assinado; senha de
PFX nunca entra como argumento (vem de keyring ou variavel de ambiente) e nunca vai para log; verificacao
sempre local (allow_fetching=False); retangulo preto sem remocao e proibido."""
from __future__ import annotations
import json, os, pathlib
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


def _assinar(ctx: Contexto, pfx_ref: str, senha_ref: str, certificar: bool, visivel: bool, pagina: int, caixa: str,
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
    pfx = ctx.entradas[1]
    senha = _segredo(senha_ref)
    try:
        signer = signers.SimpleSigner.load_pkcs12(pfx_file=str(pfx), passphrase=senha.encode())
    finally:
        senha = None  # noqa: F841 - nao manter o segredo vivo
    if signer is None:
        raise PapiroErro("E_SENHA", "PFX nao abriu com o segredo informado")
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
    with open(entrada, "rb") as inf, open(out, "wb") as outf:
        w = IncrementalPdfFileWriter(inf, strict=False)
        signers.PdfSigner(meta, signer=signer, stamp_style=estilo, new_field_spec=spec).sign_pdf(
            w, output=outf, appearance_text_params={"url": url_validacao} if url_validacao else None)
    verif = _verificar(out)
    if not verif or not all(s["intacta"] and s["valida"] for s in verif):
        raise PapiroErro("E_CONFORMIDADE", "assinatura gerada nao passou na verificacao local")
    return Resultado(outputs=[out], motor="pyhanko", dados={"perfil": "PAdES-B-B", "certificado": certificar,
                                                             "verificacao": verif})


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
def sign(entrada: str, out_dir: str, pfx: str, senha_ref: str, confirm: bool = False, visivel: bool = False,
         pagina: int = 1, caixa: str = "", crm: str = "", url_validacao: str = "https://validar.iti.gov.br",
         motivo: str = "", local: str = "", nome_campo: str = "Assinatura1", dry_run: bool = False) -> dict:
    """RF-806 PAdES-B-B com A1 (PFX). senha_ref='env:NOME' ou 'keyring:servico/usuario'. A3/PKCS#11: sem suporte."""
    def acao(ctx):
        _confirmar("sign", confirm)
        return _assinar(ctx, pfx, senha_ref, False, visivel, pagina, caixa, nome_campo, motivo, local, crm,
                        url_validacao if visivel else "", exigir_qa=True)
    return executar("sign", "pades-b-b", acao, entradas=[entrada, pfx], out_dir=out_dir, tarefa="assinatura", dry_run=dry_run)


@mcp.tool()
def certify(entrada: str, out_dir: str, pfx: str, senha_ref: str, confirm: bool = False, nome_campo: str = "Certificacao",
            dry_run: bool = False) -> dict:
    """Assinatura de certificacao DocMDP (permite so preenchimento e novas assinaturas)."""
    def acao(ctx):
        _confirmar("certify", confirm)
        return _assinar(ctx, pfx, senha_ref, True, False, 1, "", nome_campo, "Certificacao", "", "", "", exigir_qa=True)
    return executar("certify", "docmdp", acao, entradas=[entrada, pfx], out_dir=out_dir, tarefa="assinatura", dry_run=dry_run)


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
