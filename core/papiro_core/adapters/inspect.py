# -*- coding: utf-8 -*-
"""Nivel 0 - Inspecao e diagnostico RF-001..RF-009. Motores: PyMuPDF + pikepdf (+ pdffonts, fontTools)."""
from __future__ import annotations
import io, pathlib, re
import fitz  # PyMuPDF
import pikepdf
from .. import binfinder as BF
from ..erros import PapiroErro

N = pikepdf.Name


def abrir(path: pathlib.Path, senha: str | None = None) -> fitz.Document:
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise PapiroErro("E_CORROMPIDO", f"PyMuPDF nao abriu ({type(e).__name__})")
    if doc.needs_pass:
        if not senha or not doc.authenticate(senha):
            doc.close()
            raise PapiroErro("E_SENHA")
    return doc


def abrir_pike(path: pathlib.Path, senha: str | None = None) -> pikepdf.Pdf:
    try:
        return pikepdf.open(path, password=senha or "")
    except pikepdf.PasswordError:
        raise PapiroErro("E_SENHA")
    except Exception as e:
        raise PapiroErro("E_CORROMPIDO", f"pikepdf nao abriu ({type(e).__name__})")


# ---------------- RF-001 ----------------
def inventario(path: pathlib.Path, senha: str | None = None) -> dict:
    doc = abrir(path, senha)
    meta = doc.metadata or {}
    n = doc.page_count
    doc.close()
    with abrir_pike(path, senha) as pdf:
        root = pdf.Root
        mark = root.get(N.MarkInfo)
        marcado = bool(mark is not None and bool(mark.get(N.Marked, False)))
        acro = root.get(N.AcroForm)
        ocp = root.get(N.OCProperties)
        ocgs = len(ocp.get(N.OCGs, [])) if ocp is not None else 0
        idioma = str(root.get(N.Lang, "")) or ""
        pdfa = ""
        try:
            with pdf.open_metadata() as xmp:
                parte, conf = xmp.get("pdfaid:part"), xmp.get("pdfaid:conformance")
                pdfa = f"PDF/A-{parte}{(conf or '').lower()}" if parte else ""
        except Exception:
            pass
        out = {
            "paginas": n, "versao_pdf": str(pdf.pdf_version), "produtor": meta.get("producer", ""),
            "criador": meta.get("creator", ""), "titulo": meta.get("title", ""), "autor": meta.get("author", ""),
            "idioma": idioma, "criptografado": bool(pdf.is_encrypted), "linearizado": bool(pdf.is_linearized),
            "marcado_tags": marcado, "tem_struct_tree": root.get(N.StructTreeRoot) is not None,
            "tem_acroform": acro is not None and len(acro.get(N.Fields, [])) > 0,
            "tem_xfa": acro is not None and acro.get(N.XFA) is not None,
            "camadas_ocg": ocgs, "anexos": len(pdf.attachments),
            "assinaturas_detectadas": len(assinaturas(pdf)), "pdfa_declarado": pdfa,
            "bytes": path.stat().st_size,
        }
    return out


# ---------------- RF-002 ----------------
def _fontes_de_recursos(res, vistos: set):
    if res is None:
        return
    fonts = res.get(N.Font)
    if fonts is not None:
        for _nome, f in fonts.items():
            yield f
    xobjs = res.get(N.XObject)
    if xobjs is not None:
        for _nome, xo in xobjs.items():
            try:
                if xo.get(N.Subtype) == N.Form and xo.objgen not in vistos:
                    vistos.add(xo.objgen)
                    yield from _fontes_de_recursos(xo.get(N.Resources), vistos)
            except Exception:
                continue


def _fstype(fd) -> int | None:
    stream = fd.get(N.FontFile2)
    if stream is None:
        ff3 = fd.get(N.FontFile3)
        stream = ff3 if (ff3 is not None and ff3.get(N.Subtype) == N.OpenType) else None
    if stream is None:
        return None
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(io.BytesIO(stream.read_bytes()), lazy=True)
        return int(t["OS/2"].fsType) if "OS/2" in t else None
    except Exception:
        return None


def fontes(path: pathlib.Path, senha: str | None = None) -> list[dict]:
    """Uma linha por fonte distinta: tipo, embutida, subset, fsType, ToUnicode e paginas de uso."""
    linhas: dict[tuple, dict] = {}
    with abrir_pike(path, senha) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            vistos: set = set()
            recursos = page.obj.get(N.Resources)
            for f in _fontes_de_recursos(recursos, vistos):
                chave = f.objgen if f.is_indirect else (id(f),)
                if chave in linhas:
                    if pno not in linhas[chave]["paginas"]:
                        linhas[chave]["paginas"].append(pno)
                    continue
                sub = str(f.get(N.Subtype, ""))
                base = str(f.get(N.BaseFont, "")).lstrip("/")
                alvo = f
                if sub == "/Type0":
                    desc = f.get(N.DescendantFonts)
                    alvo = desc[0] if desc is not None and len(desc) else f
                fd = alvo.get(N.FontDescriptor)
                if sub == "/Type3":
                    embutida = True
                else:
                    embutida = fd is not None and any(k in fd for k in ("/FontFile", "/FontFile2", "/FontFile3"))
                linhas[chave] = {
                    "nome": base or "(sem nome)", "tipo": sub.lstrip("/"),
                    "tipo_descendente": str(alvo.get(N.Subtype, "")).lstrip("/") if alvo is not f else "",
                    "embutida": bool(embutida), "subset": bool(re.match(r"^[A-Z]{6}\+", base)),
                    "to_unicode": N.ToUnicode in f, "fsType": _fstype(fd) if (embutida and fd is not None) else None,
                    "paginas": [pno],
                }
    return list(linhas.values())


def fontes_pdffonts(path: pathlib.Path) -> list[dict] | None:
    """Relatorio do Poppler pdffonts (motor do PRD para RF-002/G3). None se ausente."""
    exe = BF.qual("pdffonts")
    if not exe:
        return None
    r = BF.rodar([exe, str(path)], timeout=60, checar=False)
    linhas = r.stdout.decode("utf-8", "replace").splitlines()
    if len(linhas) < 2 or not linhas[1].startswith("---"):
        return []
    cols = [(m.start(), m.end()) for m in re.finditer(r"-+", linhas[1])]
    out = []
    for ln in linhas[2:]:
        campos = [ln[a:b + 1].strip() if i < len(cols) - 1 else ln[a:].strip() for i, (a, b) in enumerate(cols)]
        if len(campos) >= 6:
            out.append({"nome": campos[0], "tipo": campos[1], "encoding": campos[2],
                        "embutida": campos[3] == "yes", "subset": campos[4] == "yes", "to_unicode": campos[5] == "yes"})
    return out


# ---------------- RF-003 ----------------
def imagens(path: pathlib.Path, senha: str | None = None) -> list[dict]:
    doc = abrir(path, senha)
    rows = []
    for pno, page in enumerate(doc, start=1):
        for img in page.get_images(full=True):
            xref, smask, w, h, bpc, cs = img[0], img[1], img[2], img[3], img[4], img[5]
            filtro = doc.xref_get_key(xref, "Filter")[1]
            for rect in page.get_image_rects(xref) or []:
                if rect.is_empty:
                    continue
                dpi_x = round(w / max(rect.width / 72.0, 1e-6), 1)
                dpi_y = round(h / max(rect.height / 72.0, 1e-6), 1)
                rows.append({"pagina": pno, "xref": xref, "w_px": w, "h_px": h, "bpc": bpc,
                             "espaco_cor": cs, "tem_mascara": bool(smask), "filtro": filtro,
                             "dpi_efetivo": min(dpi_x, dpi_y), "dpi_x": dpi_x, "dpi_y": dpi_y,
                             "bytes": len(doc.xref_stream_raw(xref) or b"")})
    doc.close()
    return rows


# ---------------- RF-004 ----------------
def _chars_texto(page) -> tuple[int, int]:
    """(visiveis, invisiveis) - texto invisivel = camada OCR (render mode 3)."""
    vis = inv = 0
    try:
        for span in page.get_texttrace():
            n = len(span.get("chars", ()))
            if span.get("type") == 3 or span.get("opacity", 1) == 0:
                inv += n
            else:
                vis += n
    except Exception:
        vis = len(page.get_text().strip())
    return vis, inv


def classifica_paginas(path: pathlib.Path, senha: str | None = None) -> list[dict]:
    doc = abrir(path, senha)
    out = []
    for pno, page in enumerate(doc, start=1):
        vis, inv = _chars_texto(page)
        area_img = 0.0
        for img in page.get_images(full=True):
            for r in page.get_image_rects(img[0]) or []:
                area_img += abs(r & page.rect)
        cobertura = min(area_img / max(abs(page.rect), 1), 1.0)
        if cobertura >= 0.5 and vis < 50:
            classe = "escaneada"
        elif (vis + inv) > 0 and cobertura < 0.5:
            classe = "digital"
        elif (vis + inv) == 0 and cobertura == 0:
            classe = "digital"  # vetorial ou vazia
        else:
            classe = "hibrida"
        out.append({"pagina": pno, "classe": classe, "chars_visiveis": vis, "chars_ocr_invisivel": inv,
                    "tem_camada_texto": (vis + inv) > 0, "cobertura_img": round(cobertura, 3),
                    "desenhos": len(page.get_drawings()) if (vis + inv) == 0 else None})
    doc.close()
    return out


# ---------------- RF-006 ----------------
def busca(path: pathlib.Path, regex: str, senha: str | None = None, ignorar_caixa: bool = False) -> list[dict]:
    """Regex sobre cada linha de texto; caixa = uniao das palavras que o casamento toca."""
    try:
        rx = re.compile(regex, re.IGNORECASE if ignorar_caixa else 0)
    except re.error as e:
        raise PapiroErro("E_ENTRADA", f"regex invalida: {e}")
    doc = abrir(path, senha)
    hits = []
    for pno, page in enumerate(doc, start=1):
        linhas: dict[tuple, list] = {}
        for w in page.get_text("words"):
            linhas.setdefault((w[5], w[6]), []).append(w)
        for palavras in linhas.values():
            palavras.sort(key=lambda w: w[7])
            texto, faixas, pos = "", [], 0
            for w in palavras:
                if texto:
                    texto += " "
                    pos += 1
                faixas.append((pos, pos + len(w[4]), w))
                texto += w[4]
                pos += len(w[4])
            for m in rx.finditer(texto):
                if m.start() == m.end():
                    continue
                tocadas = [w for a, b, w in faixas if a < m.end() and b > m.start()]
                r = fitz.Rect(tocadas[0][:4])
                for w in tocadas[1:]:
                    r |= fitz.Rect(w[:4])
                hits.append({"pagina": pno, "texto": m.group(0),
                             "bbox": [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)]})
    doc.close()
    return hits


# ---------------- RF-008 ----------------
def assinaturas(pdf: pikepdf.Pdf) -> list[dict]:
    acro = pdf.Root.get(N.AcroForm)
    out = []
    if acro is None:
        return out
    pilha = list(acro.get(N.Fields, []))
    while pilha:
        f = pilha.pop()
        try:
            pilha.extend(f.get(N.Kids, []))
            if f.get(N.FT) != N.Sig:
                continue
            v = f.get(N.V)
            br = [int(x) for x in v.get(N.ByteRange, [])] if v is not None else []
            out.append({"campo": str(f.get(N.T, "")), "assinado": v is not None,
                        "signatario": str(v.get(N.Name, "")) if v is not None else "",
                        "data": str(v.get(N.M, "")) if v is not None else "",
                        "byte_range": br, "cobre_ate": (br[2] + br[3]) if len(br) == 4 else None})
        except Exception:
            continue
    return out


def revisoes(path: pathlib.Path, senha: str | None = None) -> dict:
    dados = path.read_bytes()
    fins = [m.end() for m in re.finditer(rb"%%EOF[ \t]*(\r\n|\r|\n)?", dados)]
    tamanho_util = len(dados.rstrip(b"\x00\r\n\t "))
    with abrir_pike(path, senha) as pdf:
        linearizado = bool(pdf.is_linearized)
        sigs = assinaturas(pdf)
    lista, anteriores = [], None
    for i, fim in enumerate(fins, start=1):
        item = {"revisao": i, "bytes_ate": fim}
        try:
            with pikepdf.open(io.BytesIO(dados[:fim]), password=senha or "") as parte:
                info = parte.docinfo
                objs = {}
                for o in list(parte.objects)[:20000]:
                    try:
                        objs[o.objgen] = hash(o.unparse())
                    except Exception:
                        continue
                item.update({"paginas": len(parte.pages), "objetos": len(objs),
                             "modificado_em": str(info.get(N.ModDate, "")) if info is not None else ""})
                if anteriores is not None:
                    item["mudancas"] = {
                        "adicionados": len(objs.keys() - anteriores.keys()),
                        "removidos": len(anteriores.keys() - objs.keys()),
                        "alterados": sum(1 for k in objs.keys() & anteriores.keys() if objs[k] != anteriores[k])}
                anteriores = objs
        except Exception:
            item["parcial"] = "secao de linearizacao ou revisao ilegivel isoladamente"
        lista.append(item)
    n_incrementais = max(len(fins) - 1 - (1 if linearizado and len(fins) >= 2 else 0), 0)
    for s in sigs:
        cobre = s.get("cobre_ate")
        s["alterado_apos_assinatura"] = bool(cobre is not None and cobre < tamanho_util)
        s["revisoes_posteriores"] = sum(1 for r in lista if cobre is not None and r["bytes_ate"] > cobre + 2)
    return {"total_marcadores_eof": len(fins), "linearizado": linearizado,
            "revisoes_incrementais": n_incrementais, "revisoes": lista, "assinaturas": sigs}


# ---------------- RF-009 ----------------
def triagem_risco(path: pathlib.Path, senha: str | None = None) -> dict:
    c = {"javascript": 0, "launch": 0, "acoes_automaticas_aa": 0, "openaction_acao": 0, "uri": 0, "anexos": 0,
         "xfa": False, "submit_import": 0, "goto_remoto": 0, "richmedia": 0}
    evid: list[dict] = []

    def ev(tipo, obj):
        if len(evid) < 50:
            evid.append({"tipo": tipo, "objeto": f"{obj.objgen[0]} {obj.objgen[1]}" if obj.is_indirect else "direto"})

    with abrir_pike(path, senha) as pdf:
        root = pdf.Root
        oa = root.get(N.OpenAction)
        if oa is not None and isinstance(oa, pikepdf.Dictionary) and N.S in oa:
            c["openaction_acao"] += 1
            ev(f"openaction {oa.get(N.S)}", root)
        acro = root.get(N.AcroForm)
        if acro is not None and N.XFA in acro:
            c["xfa"] = True
        for obj in pdf.objects:
            if not isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
                continue
            try:
                s = obj.get(N.S)
                if s == N.JavaScript or N.JS in obj:
                    c["javascript"] += 1; ev("javascript", obj)
                elif s == N.Launch:
                    c["launch"] += 1; ev("launch", obj)
                elif s in (N.SubmitForm, N.ImportData):
                    c["submit_import"] += 1; ev(str(s), obj)
                elif s in (N.GoToR, N.GoToE):
                    c["goto_remoto"] += 1; ev(str(s), obj)
                elif s == N.URI:
                    c["uri"] += 1
                if N.AA in obj:
                    c["acoes_automaticas_aa"] += 1; ev("AA", obj)
                if obj.get(N.Subtype) == N.RichMedia or N.RichMediaContent in obj:
                    c["richmedia"] += 1; ev("richmedia", obj)
                if obj.get(N.Type) == N.EmbeddedFile or obj.get(N.Subtype) == N.FileAttachment:
                    c["anexos"] += 1; ev("anexo", obj)
            except Exception:
                continue
    if c["javascript"] or c["launch"] or c["richmedia"]:
        nota = "ALTA"
    elif c["acoes_automaticas_aa"] or c["anexos"] or c["xfa"] or c["submit_import"] or c["goto_remoto"] or c["openaction_acao"]:
        nota = "MEDIA"
    else:
        nota = "BAIXA"
    return {"flags": c, "nota_risco": nota, "evidencias": evid}


def metadados_texto(path: pathlib.Path, senha: str | None = None) -> str:
    """Campos textuais de Info e XMP (para checar dado pessoal em metadados - G10).
    Datas e identificadores tecnicos ficam de fora: 'D:20260916215645' parece CNPJ e nao e dado pessoal."""
    partes = []
    with abrir_pike(path, senha) as pdf:
        if pdf.docinfo is not None:
            partes += [str(v) for k, v in pdf.docinfo.items() if not str(k).endswith("Date")]
        try:
            with pdf.open_metadata() as xmp:
                for k, v in xmp.items():
                    if "Date" in k or k.startswith(("xmpMM:", "pdfaid:", "pdfuaid:", "xmp:CreatorTool")):
                        continue
                    partes.append(" ".join(map(str, v)) if isinstance(v, (list, set, tuple)) else str(v))
        except Exception:
            pass
    return "\n".join(partes)
