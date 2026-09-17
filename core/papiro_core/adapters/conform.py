# -*- coding: utf-8 -*-
"""Nivel 8 - conformidade: PDF/A via Ghostscript validado no veraPDF (RF-801) e preflight PDF/X proprio (§11.4).
veraPDF valida PDF/A e PDF/UA, nao PDF/X - por isso o preflight e do PAPIRO."""
from __future__ import annotations
import json, pathlib, re, tempfile
import fitz, pikepdf
from .. import binfinder as BF, config
from ..erros import PapiroErro
from .inspect import abrir, fontes, imagens

N = pikepdf.Name
FLAVOURS = {"pdf/a-1b": "1b", "pdf/a-1a": "1a", "pdf/a-2b": "2b", "pdf/a-2u": "2u", "pdf/a-2a": "2a", "pdf/a-3b": "3b",
            "pdf/a-3u": "3u", "pdf/a-3a": "3a", "pdf/a-4": "4", "pdf/a-4f": "4f", "pdf/a-4e": "4e",
            "pdf/ua-1": "ua1", "pdf/ua-2": "ua2"}


def normalizar_padrao(padrao: str) -> str:
    """'PDF/A-2b', 'a2b', 'pdfa-2b', 'UA1', 'x-1a' -> 'pdf/a-2b', 'pdf/ua-1', 'pdf/x-1a'."""
    p = (padrao or "").strip().lower().replace(" ", "").replace("_", "-").removeprefix("pdf/").removeprefix("pdf")
    m = re.fullmatch(r"(ua|a|x)-?(\w+)", p)
    if not m:
        raise PapiroErro("E_ENTRADA", f"padrao desconhecido: {padrao}")
    return f"pdf/{m.group(1)}-{m.group(2)}"


def validar_verapdf(arq: pathlib.Path, padrao: str) -> dict:
    p = normalizar_padrao(padrao)
    if p not in FLAVOURS:
        raise PapiroErro("E_ENTRADA", f"padrao nao validavel pelo veraPDF: {padrao}")
    exe = BF.qual("verapdf")
    if not exe:
        raise PapiroErro("E_SEM_SUPORTE", "veraPDF nao instalado")
    r = BF.rodar([exe, "--format", "json", "--flavour", FLAVOURS[p], str(arq)], timeout=config.jobs("timeout_motor_s"),
                 checar=False)
    try:
        dados = json.loads(r.stdout.decode("utf-8", "replace"))
        res = dados["report"]["jobs"][0]["validationResult"]
        res = res[0] if isinstance(res, list) else res
    except Exception:
        raise PapiroErro("E_MOTOR", "saida do veraPDF ilegivel")
    falhas = [{"clausula": s.get("clause"), "teste": s.get("testNumber"), "descricao": s.get("description"),
               "ocorrencias": s.get("failedChecks")}
              for s in res.get("details", {}).get("ruleSummaries", []) if s.get("ruleStatus") == "FAILED"]
    return {"padrao": p.upper().replace("PDF/", "PDF/"), "compliant": bool(res.get("compliant")),
            "regras_reprovadas": res.get("details", {}).get("failedRules"), "falhas": falhas[:50],
            "validador": "veraPDF"}


def _pdfa_def(icc: pathlib.Path, destino: pathlib.Path) -> None:
    destino.write_text(
        "%!\n"
        f"/ICCProfile ({icc.as_posix()}) def\n"
        "[/_objdef {icc_PDFA} /type /stream /OBJ pdfmark\n"
        "[{icc_PDFA} <</N 3 >> /PUT pdfmark\n"
        "[{icc_PDFA} ICCProfile (r) file /PUT pdfmark\n"
        "[/_objdef {OutputIntent_PDFA} /type /dict /OBJ pdfmark\n"
        "[{OutputIntent_PDFA} << /Type /OutputIntent /S /GTS_PDFA1 /DestOutputProfile {icc_PDFA} "
        "/OutputConditionIdentifier (sRGB) /Info (sRGB IEC61966-2.1) >> /PUT pdfmark\n"
        "[{Catalog} <</OutputIntents [ {OutputIntent_PDFA} ]>> /PUT pdfmark\n", encoding="latin-1")


def _srgb_icc() -> pathlib.Path:
    gs = BF.ghostscript()
    base = pathlib.Path(gs).resolve().parent.parent if gs else None
    candidatos = list(base.glob("share/ghostscript/*/iccprofiles/srgb.icc")) if base else []
    candidatos += [pathlib.Path("/usr/share/color/icc/ghostscript/srgb.icc"),
                   pathlib.Path("/usr/share/ghostscript/iccprofiles/srgb.icc")]
    for c in candidatos:
        if c.exists():
            return c
    raise PapiroErro("E_SEM_SUPORTE", "perfil sRGB do Ghostscript nao encontrado")


def converter_pdfa(entrada: pathlib.Path, out: pathlib.Path, padrao: str = "PDF/A-2b") -> dict:
    """Ghostscript pdfwrite com OutputIntent sRGB; titulo e /Lang preservados; aprovado so com veraPDF."""
    p = normalizar_padrao(padrao)
    m = re.fullmatch(r"pdf/a-([1234])([abuef]?)", p)
    if not m:
        raise PapiroErro("E_ENTRADA", f"padrao PDF/A invalido: {padrao}")
    parte = m.group(1)
    gs = BF.ghostscript()
    if not gs:
        raise PapiroErro("E_SEM_SUPORTE", "Ghostscript ausente")
    icc = _srgb_icc()
    with pikepdf.open(entrada) as orig:
        titulo = str(orig.docinfo.get("/Title", "")) if orig.docinfo is not None else ""
        autor = str(orig.docinfo.get("/Author", "")) if orig.docinfo is not None else ""
        lang = str(orig.Root.get(N.Lang, "")) or None
    with tempfile.TemporaryDirectory() as t:
        defs = pathlib.Path(t) / "PDFA_def.ps"
        _pdfa_def(icc, defs)
        bruto = pathlib.Path(t) / "a.pdf"
        BF.rodar([gs, f"-dPDFA={parte}", "-dBATCH", "-dNOPAUSE", "-dSAFER", "-dNOOUTERSAVE",
                  f"--permit-file-read={icc.parent.as_posix()}/", "-sColorConversionStrategy=RGB",
                  "-sProcessColorModel=DeviceRGB", "-dPDFACompatibilityPolicy=1", "-sDEVICE=pdfwrite",
                  f"-sOutputFile={bruto}", str(defs), str(entrada)], timeout=config.jobs("timeout_motor_s"))
        with pikepdf.open(bruto) as pdf:
            if lang:
                pdf.Root.Lang = pikepdf.String(lang)
            if titulo or autor:
                with pdf.open_metadata(set_pikepdf_as_editor=False) as xmp:
                    if titulo:
                        pdf.docinfo["/Title"] = titulo
                        xmp["dc:title"] = titulo
                    if autor:
                        pdf.docinfo["/Author"] = autor
                        xmp["dc:creator"] = [autor]
            pdf.save(out)
    val = validar_verapdf(out, p)
    if not val["compliant"]:
        raise PapiroErro("E_CONFORMIDADE", f"veraPDF reprovou {p.upper()}: {val['regras_reprovadas']} regras")
    return {"padrao": p.upper(), "validacao": val}


# ---------------- preflight PDF/X §11.4 ----------------
def _cor_composta(cor) -> bool:
    if cor is None:
        return False
    if len(cor) == 4:
        return sum(1 for v in cor if v > 0.001) > 1
    if len(cor) == 3:
        return not (abs(cor[0] - cor[1]) < 0.01 and abs(cor[1] - cor[2]) < 0.01)
    return False


def preflight_x(arq: pathlib.Path, padrao: str = "PDF/X-4", limite_tinta: float = 300.0) -> dict:
    p = normalizar_padrao(padrao)
    x1a = p == "pdf/x-1a"
    falhas, avisos = [], []
    with pikepdf.open(arq) as pdf:
        intents = pdf.Root.get(N.OutputIntents)
        if not intents or not any(i.get(N.S) == N.GTS_PDFX and N.DestOutputProfile in i for i in intents):
            falhas.append({"regra": "OutputIntent", "detalhe": "sem OutputIntent GTS_PDFX com perfil ICC"})
        for pno, page in enumerate(pdf.pages, start=1):
            mb = [float(v) for v in page.obj.MediaBox]
            trim, bleed = page.obj.get(N.TrimBox), page.obj.get(N.BleedBox)
            if trim is None or bleed is None:
                falhas.append({"regra": "Caixas", "pagina": pno, "detalhe": "TrimBox ou BleedBox ausente"})
            else:
                t, b = [float(v) for v in trim], [float(v) for v in bleed]
                if not (mb[0] <= b[0] <= t[0] and mb[1] <= b[1] <= t[1] and t[2] <= b[2] <= mb[2] and t[3] <= b[3] <= mb[3]):
                    falhas.append({"regra": "Caixas", "pagina": pno, "detalhe": "caixas nao aninhadas"})
            if x1a:
                gs_dict = page.obj.get(N.Resources, {}).get(N.ExtGState, {})
                for _n, g in (gs_dict.items() if gs_dict else []):
                    if float(g.get(N.CA, 1)) < 1 or float(g.get(N.ca, 1)) < 1 or g.get(N.SMask, N("/None")) != N("/None"):
                        falhas.append({"regra": "Transparencia", "pagina": pno, "detalhe": "transparencia em X-1a"})
                        break
    for f in fontes(arq):
        if not f["embutida"]:
            falhas.append({"regra": "Fontes", "detalhe": f"fonte nao embutida: {f['nome']}"})
    for im in imagens(arq):
        if im["dpi_efetivo"] < 300:
            falhas.append({"regra": "Resolucao", "pagina": im["pagina"], "detalhe": f"imagem com {im['dpi_efetivo']} DPI"})
        if x1a and im["espaco_cor"] in ("DeviceRGB", "ICCBased") and im.get("tem_mascara"):
            falhas.append({"regra": "Transparencia", "pagina": im["pagina"], "detalhe": "imagem com mascara suave"})
        if x1a and im["espaco_cor"] == "DeviceRGB":
            falhas.append({"regra": "Espacos de cor", "pagina": im["pagina"], "detalhe": "imagem RGB em X-1a"})
    with abrir(arq) as doc:
        for page in doc:
            pno = page.number + 1
            for d in page.get_drawings():
                w = d.get("width")
                if d.get("color") is not None and w is not None and 0 < w < 0.25:
                    falhas.append({"regra": "Linhas finas", "pagina": pno, "detalhe": f"traco de {w:.2f} pt"})
                    break
                if x1a and ((d.get("fill") and len(d["fill"]) == 3) or (d.get("color") and len(d["color"]) == 3)):
                    falhas.append({"regra": "Espacos de cor", "pagina": pno, "detalhe": "vetor em RGB em X-1a"})
                    break
            for sp in page.get_texttrace():
                if sp.get("type") == 3:
                    continue
                if sp.get("size", 99) < 8 and _cor_composta(sp.get("color")):
                    falhas.append({"regra": "Texto pequeno", "pagina": pno, "detalhe": f"texto {sp['size']:.1f} pt em cor composta"})
                    break
                cor = sp.get("color")
                if cor is not None and len(cor) == 4 and cor[3] > 0.95 and sum(cor[:3]) > 0.01:
                    avisos.append(f"pagina {pno}: preto de texto composto (nao 100% K)")
                    break
            pix = page.get_pixmap(dpi=36, colorspace=fitz.csCMYK)
            amostras = pix.samples
            if amostras:
                maior = max(sum(amostras[i:i + 4]) for i in range(0, len(amostras), 4)) / 255 * 100
                if maior > limite_tinta:
                    falhas.append({"regra": "Cobertura de tinta", "pagina": pno,
                                   "detalhe": f"{maior:.0f}% > {limite_tinta:.0f}% (conversao CMYK sem ICC, aproximada)"})
    avisos.append("sobreimpressao do preto nao e verificavel sem analisar o conteudo: conferir no RIP da grafica")
    return {"padrao": p.upper(), "aprovado": not falhas, "falhas": falhas, "avisos": avisos, "validador": "preflight PAPIRO"}


def validar_padrao(arq: pathlib.Path, padrao: str) -> dict:
    p = normalizar_padrao(padrao)
    if p.startswith("pdf/x"):
        r = preflight_x(arq, p)
        return {"ok": r["aprovado"], **r}
    r = validar_verapdf(arq, p)
    return {"ok": r["compliant"], **r}
