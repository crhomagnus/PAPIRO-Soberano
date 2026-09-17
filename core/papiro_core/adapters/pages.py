# -*- coding: utf-8 -*-
"""Nivel 1 + Nivel 9 - paginas, compressao, reparo e linearizacao. RF-101..RF-110, RF-901..RF-904."""
from __future__ import annotations
import pathlib, shutil, tempfile
import fitz, pikepdf
from .. import binfinder as BF, config, engines as ENG, fidelidade as FID
from ..erros import PapiroErro
from .inspect import abrir, abrir_pike

N = pikepdf.Name
PAPEIS = {"a4": (595.276, 841.89), "carta": (612, 792), "letter": (612, 792), "a3": (841.89, 1190.55),
          "a5": (419.528, 595.276), "oficio": (612, 1008)}


def copiar_metadados(src: pikepdf.Pdf, dst: pikepdf.Pdf) -> None:
    """Info, XMP (via Info) e /Lang do documento de origem no documento novo."""
    if src.docinfo is not None:
        for k, v in src.docinfo.items():
            try:
                dst.docinfo[k] = pikepdf.String(str(v))
            except Exception:
                continue
    lang = src.Root.get(N.Lang)
    if lang is not None:
        dst.Root.Lang = pikepdf.String(str(lang))
    if len(dst.docinfo):
        with dst.open_metadata(set_pikepdf_as_editor=False) as xmp:
            xmp.load_from_docinfo(dst.docinfo)
            if lang is not None:
                xmp["dc:language"] = [str(lang)]


def _paginas_validas(lista: list[int], n: int) -> list[int]:
    for p in lista:
        if p < 1 or p > n:
            raise PapiroErro("E_ENTRADA", f"pagina {p} fora do intervalo 1..{n}")
    return lista


def parse_paginas(expr: str, n: int) -> list[int]:
    """'1,3-5,8-' -> [1,3,4,5,8..n]."""
    out: list[int] = []
    for parte in (expr or "").replace(";", ",").split(","):
        parte = parte.strip()
        if not parte:
            continue
        if "-" in parte:
            a, _, b = parte.partition("-")
            ini, fim = int(a or 1), int(b or n)
            if ini > fim:
                raise PapiroErro("E_ENTRADA", f"intervalo invertido: {parte}")
            out.extend(range(ini, fim + 1))
        else:
            out.append(int(parte))
    return _paginas_validas(out, n)


# ---------------- RF-101 ----------------
def merge(entradas: list[pathlib.Path], out: pathlib.Path, nomes: list[str] | None = None) -> dict:
    """Junta preservando links internos e marcadores de cada origem, sob um marcador por arquivo."""
    if len(entradas) < 2:
        raise PapiroErro("E_ENTRADA", "merge exige ao menos 2 arquivos")
    dst = fitz.open()
    toc: list = []
    for i, e in enumerate(entradas):
        src = abrir(e)
        inicio = dst.page_count + 1
        dst.insert_pdf(src, links=True, annots=True)
        rotulo = (nomes[i] if nomes and i < len(nomes) else pathlib.Path(e).stem.split("_", 1)[-1])
        toc.append([1, rotulo, inicio])
        for nivel, titulo, pag, *_ in src.get_toc(simple=False):
            if pag > 0:
                toc.append([nivel + 1, titulo, pag + inicio - 1])
        src.close()
    dst.set_toc(toc)
    with fitz.open(entradas[0]) as primeiro:
        dst.set_metadata(primeiro.metadata or {})
        if primeiro.language:
            dst.set_language(primeiro.language)
    dst.save(out, garbage=3, deflate=True)
    n = dst.page_count
    dst.close()
    return {"paginas": n, "marcadores": len(toc)}


# ---------------- RF-102 ----------------
def split(entrada: pathlib.Path, out_dir: pathlib.Path, intervalos: list[str] | None = None,
          a_cada: int = 0, por_marcador: bool = False) -> list[pathlib.Path]:
    with abrir_pike(entrada) as src:
        n = len(src.pages)
        grupos: list[list[int]] = []
        if intervalos:
            grupos = [parse_paginas(iv, n) for iv in intervalos]
        elif a_cada > 0:
            grupos = [list(range(i, min(i + a_cada, n + 1))) for i in range(1, n + 1, a_cada)]
        elif por_marcador:
            with fitz.open(entrada) as d:
                inicios = sorted({p for nivel, _t, p in d.get_toc() if nivel == 1 and p > 0})
            if not inicios:
                raise PapiroErro("E_ENTRADA", "documento sem marcadores de nivel 1")
            if inicios[0] != 1:
                inicios.insert(0, 1)
            limites = inicios + [n + 1]
            grupos = [list(range(limites[i], limites[i + 1])) for i in range(len(inicios))]
        else:
            raise PapiroErro("E_ENTRADA", "informe intervalos, a_cada ou por_marcador")
        outs = []
        for i, g in enumerate(grupos, start=1):
            dst = pikepdf.Pdf.new()
            for pg in g:
                dst.pages.append(src.pages[pg - 1])
            copiar_metadados(src, dst)
            p = out_dir / f"parte{i:03d}_p{g[0]}-{g[-1]}.pdf"
            dst.save(p)
            outs.append(p)
        return outs


# ---------------- RF-103 ----------------
def reordenar(entrada: pathlib.Path, out: pathlib.Path, ordem: list[int]) -> int:
    """Extrair, duplicar, mover, inverter: tudo e uma nova sequencia de paginas (1-based, com repeticao)."""
    with abrir_pike(entrada) as src:
        _paginas_validas(ordem, len(src.pages))
        if not ordem:
            raise PapiroErro("E_ENTRADA", "sequencia de paginas vazia")
        dst = pikepdf.Pdf.new()
        for pg in ordem:
            dst.pages.append(src.pages[pg - 1])
        copiar_metadados(src, dst)
        dst.save(out)
    return len(ordem)


def excluir(entrada: pathlib.Path, out: pathlib.Path, paginas: list[int]) -> int:
    with abrir_pike(entrada) as src:
        n = len(src.pages)
        _paginas_validas(paginas, n)
        manter = [p for p in range(1, n + 1) if p not in set(paginas)]
    if not manter:
        raise PapiroErro("E_ENTRADA", "excluir todas as paginas deixaria o documento vazio")
    return reordenar(entrada, out, manter)


def intercalar(frentes: pathlib.Path, versos: pathlib.Path, out: pathlib.Path, versos_invertidos: bool = True) -> int:
    """Frente e verso digitalizados separadamente (versos normalmente saem em ordem inversa)."""
    with abrir_pike(frentes) as a, abrir_pike(versos) as b:
        if len(a.pages) != len(b.pages):
            raise PapiroErro("E_ENTRADA", "frentes e versos com numero diferente de paginas")
        vb = list(b.pages)[::-1] if versos_invertidos else list(b.pages)
        dst = pikepdf.Pdf.new()
        for fa, fb in zip(a.pages, vb):
            dst.pages.append(fa)
            dst.pages.append(fb)
        copiar_metadados(a, dst)
        dst.save(out)
        return len(dst.pages)


# ---------------- RF-104 ----------------
def detectar_rotacao(entrada: pathlib.Path, pagina: int) -> int | None:
    """Angulo sugerido pelo Tesseract OSD (--psm 0); None se indisponivel ou inconclusivo."""
    exe = BF.qual("tesseract")
    if not exe or "osd" not in ENG.tesseract_idiomas():
        return None
    with fitz.open(entrada) as d, tempfile.TemporaryDirectory() as t:
        img = pathlib.Path(t) / "p.png"
        d[pagina - 1].get_pixmap(dpi=200).save(img)
        r = BF.rodar([exe, str(img), "stdout", "--psm", "0"], timeout=60, checar=False)
    for ln in r.stdout.decode("utf-8", "replace").splitlines():
        if ln.startswith("Rotate:"):
            return int(ln.split(":")[1]) % 360
    return None


def girar(entrada: pathlib.Path, out: pathlib.Path, paginas: list[int], angulo: int | str) -> dict:
    with abrir_pike(entrada) as src:
        n = len(src.pages)
        paginas = _paginas_validas(paginas or list(range(1, n + 1)), n)
        aplicados = {}
        for pg in paginas:
            ang = detectar_rotacao(entrada, pg) if angulo == "auto" else int(angulo)
            if ang is None:
                continue
            if ang % 90:
                raise PapiroErro("E_ENTRADA", "angulo deve ser multiplo de 90")
            src.pages[pg - 1].Rotate = (int(src.pages[pg - 1].obj.get(N.Rotate, 0)) + ang) % 360
            aplicados[pg] = ang
        src.save(out)
    return {"paginas_giradas": aplicados}


# ---------------- RF-105 ----------------
def caixas(entrada: pathlib.Path, out: pathlib.Path, definicoes: dict, paginas: list[int] | None = None) -> dict:
    """definicoes = {"CropBox": [x0,y0,x1,y1], "TrimBox": [...], "BleedBox": [...], "ArtBox": [...]} em pt."""
    with abrir_pike(entrada) as src:
        n = len(src.pages)
        for pg in _paginas_validas(paginas or list(range(1, n + 1)), n):
            page = src.pages[pg - 1]
            mb = [float(x) for x in page.obj.MediaBox]
            for nome, r in definicoes.items():
                if nome not in ("CropBox", "TrimBox", "BleedBox", "ArtBox"):
                    raise PapiroErro("E_ENTRADA", f"caixa invalida: {nome}")
                x0, y0, x1, y1 = [float(v) for v in r]
                if not (mb[0] <= x0 < x1 <= mb[2] and mb[1] <= y0 < y1 <= mb[3]):
                    raise PapiroErro("E_ENTRADA", f"{nome} fora da MediaBox na pagina {pg}")
                page.obj[N(f"/{nome}")] = pikepdf.Array([x0, y0, x1, y1])
            trim, bleed = page.obj.get(N.TrimBox), page.obj.get(N.BleedBox)
            if trim is not None and bleed is not None:
                t, b = [float(v) for v in trim], [float(v) for v in bleed]
                if not (b[0] <= t[0] and b[1] <= t[1] and t[2] <= b[2] and t[3] <= b[3]):
                    raise PapiroErro("E_ENTRADA", f"TrimBox nao esta dentro da BleedBox na pagina {pg}")
        src.save(out)
    return {"caixas": list(definicoes)}


# ---------------- RF-106 / RF-107 ----------------
def _papel(nome: str) -> tuple[float, float]:
    nome = nome.lower().strip()
    if nome in PAPEIS:
        return PAPEIS[nome]
    if "x" in nome:  # "210x297mm" ou "595x842"
        mm = nome.endswith("mm")
        w, h = [float(v) for v in nome.removesuffix("mm").split("x")]
        return (w * 72 / 25.4, h * 72 / 25.4) if mm else (w, h)
    raise PapiroErro("E_ENTRADA", f"papel desconhecido: {nome}")


def redimensionar(entrada: pathlib.Path, out: pathlib.Path, papel: str = "a4") -> dict:
    """Conteudo escalado proporcionalmente e centralizado, sem corte."""
    w, h = _papel(papel)
    with abrir(entrada) as src, fitz.open() as dst:
        for page in src:
            pw, ph = (h, w) if (page.rect.width > page.rect.height) != (w > h) else (w, h)
            nova = dst.new_page(width=pw, height=ph)
            nova.show_pdf_page(nova.rect, src, page.number, keep_proportion=True)
        dst.set_metadata(src.metadata or {})
        if src.language:
            dst.set_language(src.language)
        dst.save(out, garbage=3, deflate=True)
        return {"paginas": dst.page_count, "papel": [round(w, 2), round(h, 2)]}


def nup(entrada: pathlib.Path, out: pathlib.Path, por_folha: int = 2, papel: str = "a4") -> dict:
    grades = {2: (2, 1), 4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3), 16: (4, 4)}
    if por_folha not in grades:
        raise PapiroErro("E_ENTRADA", f"n-up suportado: {sorted(grades)}")
    cols, lins = grades[por_folha]
    w, h = _papel(papel)
    if por_folha == 2:
        w, h = h, w  # 2-up em paisagem
    with abrir(entrada) as src, fitz.open() as dst:
        for i in range(0, src.page_count, por_folha):
            folha = dst.new_page(width=w, height=h)
            for k in range(por_folha):
                if i + k >= src.page_count:
                    break
                c, l = k % cols, k // cols
                cel = fitz.Rect(c * w / cols, l * h / lins, (c + 1) * w / cols, (l + 1) * h / lins)
                folha.show_pdf_page(cel + (6, 6, -6, -6), src, i + k, keep_proportion=True)
        dst.set_metadata(src.metadata or {})
        if src.language:
            dst.set_language(src.language)
        dst.save(out, garbage=3, deflate=True)
        return {"folhas": dst.page_count}


def ordem_livreto(n: int) -> list[tuple[int | None, int | None]]:
    """Pares (esquerda, direita) por face de folha para livreto grampeado; None = branca."""
    total = n + (-n % 4)
    pares, esq, dir_ = [], total, 1
    while dir_ < esq:
        pares.append((esq, dir_))          # frente da folha
        pares.append((dir_ + 1, esq - 1))  # verso da folha
        esq, dir_ = esq - 2, dir_ + 2
    return [(a if a <= n else None, b if b <= n else None) for a, b in pares]


def livreto(entrada: pathlib.Path, out: pathlib.Path, papel: str = "a4") -> dict:
    w, h = _papel(papel)
    w, h = max(w, h), min(w, h)
    with abrir(entrada) as src, fitz.open() as dst:
        pares = ordem_livreto(src.page_count)
        for esq, dir_ in pares:
            face = dst.new_page(width=w, height=h)
            for pos, pg in enumerate((esq, dir_)):
                if pg is not None:
                    face.show_pdf_page(fitz.Rect(pos * w / 2, 0, (pos + 1) * w / 2, h), src, pg - 1, keep_proportion=True)
        dst.set_metadata(src.metadata or {})
        if src.language:
            dst.set_language(src.language)
        dst.save(out, garbage=3, deflate=True)
        return {"faces": dst.page_count, "ordem": pares}


# ---------------- RF-108 ----------------
def rotulos(entrada: pathlib.Path, out: pathlib.Path, faixas: list[dict]) -> dict:
    """faixas=[{"inicio":1,"estilo":"r"},{"inicio":5,"estilo":"D","primeiro":1}] - estilos D r R a A."""
    with abrir_pike(entrada) as pdf:
        nums = pikepdf.Array()
        for f in sorted(faixas, key=lambda x: int(x["inicio"])):
            d = pikepdf.Dictionary()
            if f.get("estilo"):
                d[N.S] = N("/" + f["estilo"])
            if f.get("prefixo"):
                d[N.P] = pikepdf.String(f["prefixo"])
            if f.get("primeiro"):
                d[N.St] = int(f["primeiro"])
            nums.append(int(f["inicio"]) - 1)
            nums.append(d)
        pdf.Root.PageLabels = pikepdf.Dictionary(Nums=nums)
        pdf.save(out)
    return {"faixas": len(faixas)}


# ---------------- RF-110 ----------------
def pagina_em_branco(page: fitz.Page, limiar_tinta: float = 0.0005) -> bool:
    """Branca so se nao tem texto, imagem nem desenho E a renderizacao quase nao tem tinta (zero falso positivo)."""
    if page.get_text().strip() or page.get_images() or page.get_drawings():
        return False
    pix = page.get_pixmap(dpi=40, colorspace=fitz.csGRAY)
    amostras = pix.samples
    escuros = sum(1 for v in amostras if v < 245)
    return escuros / max(len(amostras), 1) <= limiar_tinta


def remover_branco(entrada: pathlib.Path, out: pathlib.Path, limiar_tinta: float = 0.0005) -> dict:
    with abrir(entrada) as doc:
        brancas = [p.number + 1 for p in doc if pagina_em_branco(p, limiar_tinta)]
        manter = [i for i in range(1, doc.page_count + 1) if i not in brancas]
    if not manter:
        raise PapiroErro("E_ENTRADA", "todas as paginas estao em branco")
    reordenar(entrada, out, manter)
    return {"mantidas": len(manter), "removidas": brancas}


# ---------------- RF-901 ----------------
def _valido(p: pathlib.Path) -> int:
    try:
        with fitz.open(p) as d:
            return d.page_count
    except Exception:
        return 0


def reparar_cascata(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    """qpdf -> pikepdf -> Ghostscript -> PyMuPDF (garbage) -> reconstrucao por renderizacao."""
    tentativas: list[dict] = []
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t) / "rep.pdf"

        def via_qpdf():
            exe = BF.qual("qpdf")
            if not exe:
                raise PapiroErro("E_SEM_SUPORTE", "qpdf ausente")
            r = BF.rodar([exe, str(entrada), str(tmp)], timeout=300, checar=False)
            if r.returncode not in (0, 3):
                raise PapiroErro("E_MOTOR", f"qpdf saiu com {r.returncode}")

        def via_pikepdf():
            with pikepdf.open(entrada) as pdf:
                pdf.save(tmp)

        def via_gs():
            gs = BF.ghostscript()
            if not gs:
                raise PapiroErro("E_SEM_SUPORTE", "Ghostscript ausente")
            BF.rodar([gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", f"-sOutputFile={tmp}", str(entrada)],
                     timeout=600)

        def via_pymupdf():
            with fitz.open(entrada) as d:
                d.save(tmp, garbage=4, deflate=True, clean=True)

        def via_render():
            with fitz.open(entrada) as d, fitz.open() as novo:
                for page in d:
                    pix = page.get_pixmap(dpi=200)
                    np_ = novo.new_page(width=page.rect.width, height=page.rect.height)
                    np_.insert_image(np_.rect, pixmap=pix)
                novo.save(tmp, garbage=3, deflate=True)

        for nome, fn in (("qpdf", via_qpdf), ("pikepdf", via_pikepdf), ("ghostscript", via_gs),
                         ("pymupdf", via_pymupdf), ("render", via_render)):
            try:
                tmp.unlink(missing_ok=True)
                fn()
                paginas = _valido(tmp)
                if paginas > 0:
                    shutil.copyfile(tmp, out)
                    return {"via": nome, "paginas": paginas, "tentativas": tentativas,
                            "fallback_from": tentativas[0]["motor"] if tentativas else None}
                tentativas.append({"motor": nome, "erro": "saida sem paginas"})
            except Exception as e:  # noqa: BLE001
                tentativas.append({"motor": nome, "erro": f"{type(e).__name__}: {str(e)[:120]}"})
    raise PapiroErro("E_CORROMPIDO", f"nenhum motor recuperou o arquivo ({len(tentativas)} tentativas)")


# ---------------- RF-902 / RF-903 ----------------
DPI_ALVO = {"tela": 96, "email": 150, "impressao": 300, "arquivo": None}
QUALIDADE_JPEG = {"tela": 60, "email": 75, "impressao": 90, "arquivo": None}
GS_PERFIL = {"tela": "/screen", "email": "/ebook", "impressao": "/printer", "arquivo": "/prepress"}


def _candidato_pymupdf(entrada: pathlib.Path, out: pathlib.Path, perfil: str) -> dict:
    alvo, q = DPI_ALVO[perfil], QUALIDADE_JPEG[perfil]
    trocadas, puladas = 0, 0
    with fitz.open(entrada) as doc:
        mapa: dict[int, dict] = {}
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                info = mapa.setdefault(xref, {"pagina": page.number, "smask": img[1], "w": img[2], "h": img[3],
                                              "bpc": img[4], "filtro": img[8], "rects": []})
                info["rects"].extend(r for r in page.get_image_rects(xref) if not r.is_empty)
        for xref, info in mapa.items():
            if alvo is None or not info["rects"]:
                continue
            if info["smask"] or info["bpc"] != 8 or info["filtro"] in ("JBIG2Decode", "CCITTFaxDecode", "JPXDecode"):
                puladas += 1
                continue
            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception:
                puladas += 1
                continue
            if pix.alpha or pix.n not in (1, 3, 4):
                puladas += 1
                continue
            if pix.n == 4:
                if perfil not in ("tela", "email"):
                    puladas += 1
                    continue
                pix = fitz.Pixmap(fitz.csRGB, pix)
            maior_w = max(r.width for r in info["rects"])
            dpi = info["w"] / max(maior_w / 72.0, 1e-6)
            escala = min(1.0, alvo / dpi) if dpi > 0 else 1.0
            if escala < 0.85:
                pix = fitz.Pixmap(pix, max(1, round(pix.width * escala)), max(1, round(pix.height * escala)), None)
            novo = pix.tobytes("jpg", jpg_quality=q)
            antigo = len(doc.xref_stream_raw(xref) or b"")
            if len(novo) < 0.9 * antigo:
                doc[info["pagina"]].replace_image(xref, stream=novo)
                trocadas += 1
        doc.save(out, garbage=4, deflate=True, use_objstms=1)
    return {"imagens_recomprimidas": trocadas, "imagens_preservadas": puladas}


def _candidato_gs(entrada: pathlib.Path, out: pathlib.Path, perfil: str) -> dict:
    gs = BF.ghostscript()
    if not gs:
        raise PapiroErro("E_SEM_SUPORTE", "Ghostscript ausente")
    BF.rodar([gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.7",
              f"-dPDFSETTINGS={GS_PERFIL[perfil]}", "-dDetectDuplicateImages=true", f"-sOutputFile={out}", str(entrada)],
             timeout=config.jobs("timeout_motor_s"))
    return {}


def _gs_seguro(entrada: pathlib.Path) -> bool:
    """Ghostscript reescreve o arquivo: nao usar em PDF com formulario, assinatura, tags ou anexos."""
    with pikepdf.open(entrada) as pdf:
        root = pdf.Root
        return not (root.get(N.AcroForm) is not None or root.get(N.StructTreeRoot) is not None
                    or len(pdf.attachments) > 0)


def otimizar(entrada: pathlib.Path, out: pathlib.Path, perfil: str = "email", meta_mb: float | None = None,
             linearizar: bool = False) -> dict:
    """Gera candidatos (PyMuPDF e, quando seguro, Ghostscript) e entrega o menor que preserva texto
    identico e SSIM (pior bloco) acima do limiar do perfil. Sem candidato fiel e menor: copia sem perda."""
    if perfil not in DPI_ALVO:
        raise PapiroErro("E_ENTRADA", f"perfil invalido: {perfil} (tela|email|impressao|arquivo)")
    limiar = float(config.qa("ssim_otimizar")[perfil])
    antes = entrada.stat().st_size
    avaliados = []
    with tempfile.TemporaryDirectory() as t:
        tdir = pathlib.Path(t)
        geradores = [("pymupdf", _candidato_pymupdf)]
        if BF.ghostscript() and _gs_seguro(entrada):
            geradores.append(("ghostscript", _candidato_gs))
        for nome, gerar in geradores:
            cand = tdir / f"{nome}.pdf"
            try:
                extra = gerar(entrada, cand, perfil)
                fid = FID.comparar(entrada, cand)
                txt = FID.similaridade_texto(entrada, cand)
                fiel = fid["mesmo_numero_paginas"] and fid["ssim_pior_bloco"] >= limiar and txt >= 0.999
                avaliados.append({"motor": nome, "bytes": cand.stat().st_size, "ssim_medio": fid["ssim_medio"],
                                  "ssim_pior_bloco": fid["ssim_pior_bloco"], "texto_igual": round(txt, 4),
                                  "fiel": fiel, "arquivo": cand, **extra})
            except Exception as e:  # noqa: BLE001
                avaliados.append({"motor": nome, "erro": f"{type(e).__name__}: {str(e)[:150]}", "fiel": False})
        validos = sorted((c for c in avaliados if c["fiel"] and c["bytes"] < antes), key=lambda c: c["bytes"])
        avisos = []
        if validos:
            escolhido = validos[0]
            shutil.copyfile(escolhido["arquivo"], out)
            via = escolhido["motor"]
        else:
            with pikepdf.open(entrada) as pdf:
                pdf.save(out, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
            via = "pikepdf-sem-perda"
            avisos.append(f"nenhum candidato com perda ficou menor e fiel (limiar SSIM {limiar}); entregue versao sem perda")
    if linearizar:
        linearizar_arquivo(out)
    depois = out.stat().st_size
    if meta_mb is not None and depois > meta_mb * 1024 * 1024:
        avisos.append(f"meta de {meta_mb} MB nao atingida ({depois / 1048576:.2f} MB) sem perder fidelidade")
    for c in avaliados:
        c.pop("arquivo", None)
    return {"via": via, "paginas": _valido(out), "antes": antes, "depois": depois,
            "reducao_pct": round(100 * (1 - depois / max(antes, 1)), 1), "limiar_ssim": limiar,
            "candidatos": avaliados, "avisos": avisos, "linearizado": linearizar}


def linearizar_arquivo(p: pathlib.Path) -> dict:
    """RF-903: lineariza no lugar (arquivo de saida, nunca entrada) e confere com qpdf quando presente."""
    tmp = p.with_suffix(".lin.tmp")
    with pikepdf.open(p) as pdf:
        pdf.save(tmp, linearize=True)
    tmp.replace(p)
    exe = BF.qual("qpdf")
    if exe:
        r = BF.rodar([exe, "--check-linearization", str(p)], timeout=120, checar=False)
        if r.returncode != 0:
            raise PapiroErro("E_CONFORMIDADE", "qpdf --check-linearization reprovou")
        return {"verificado_por": "qpdf"}
    return {"verificado_por": None}


# ---------------- RF-904 ----------------
_ENCODINGS_PY = {"/WinAnsiEncoding": "cp1252", "/MacRomanEncoding": "mac_roman", "/StandardEncoding": "latin-1",
                 "/PDFDocEncoding": "latin-1"}


def _cmap_tounicode(mapa: dict[int, str]) -> bytes:
    linhas = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
              "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
              "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def", "1 begincodespacerange", "<00> <FF>",
              "endcodespacerange"]
    itens = sorted(mapa.items())
    for i in range(0, len(itens), 100):
        bloco = itens[i:i + 100]
        linhas.append(f"{len(bloco)} beginbfchar")
        linhas += [f"<{c:02X}> <{''.join(f'{ord(ch):04X}' if ord(ch) < 0x10000 else ch.encode('utf-16-be').hex().upper() for ch in u)}>"
                   for c, u in bloco]
        linhas.append("endbfchar")
    linhas += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(linhas).encode("ascii")


def adicionar_tounicode(pdf: pikepdf.Pdf) -> int:
    """ToUnicode para fontes simples (Type1/TrueType/Type1C) a partir da codificacao e de /Differences (AGL)."""
    from fontTools import agl
    feitas = 0
    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Dictionary) or obj.get(N.Type) != N.Font:
            continue
        if obj.get(N.Subtype) not in (N.Type1, N.TrueType, N.MMType1) or N.ToUnicode in obj:
            continue
        enc = obj.get(N.Encoding)
        base, diffs = "/StandardEncoding", None
        if isinstance(enc, pikepdf.Name):
            base = str(enc)
        elif isinstance(enc, pikepdf.Dictionary):
            base = str(enc.get(N.BaseEncoding, "/StandardEncoding"))
            diffs = enc.get(N.Differences)
        codec = _ENCODINGS_PY.get(base, "latin-1")
        mapa = {}
        for c in range(32, 256):
            try:
                ch = bytes([c]).decode(codec)
                if ch.isprintable():
                    mapa[c] = ch
            except UnicodeDecodeError:
                continue
        if diffs is not None:
            codigo = 0
            for item in diffs:
                if isinstance(item, (int, pikepdf.Object)) and not isinstance(item, pikepdf.Name):
                    try:
                        codigo = int(item)
                        continue
                    except (TypeError, ValueError):
                        pass
                if isinstance(item, pikepdf.Name):
                    u = agl.toUnicode(str(item)[1:])
                    if u:
                        mapa[codigo] = u
                    codigo += 1
        obj[N.ToUnicode] = pdf.make_stream(_cmap_tounicode(mapa))
        feitas += 1
    return feitas


def embutir_fontes(entrada: pathlib.Path, out: pathlib.Path) -> dict:
    """Ghostscript com NeverEmbed vazio (senao as 14 fontes base nunca sao embutidas) + ToUnicode."""
    gs = BF.ghostscript()
    if not gs:
        raise PapiroErro("E_SEM_SUPORTE", "Ghostscript ausente")
    with tempfile.TemporaryDirectory() as t:
        bruto = pathlib.Path(t) / "gs.pdf"
        BF.rodar([gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", "-dEmbedAllFonts=true",
                  "-dSubsetFonts=true", "-dCompressFonts=true", f"-sOutputFile={bruto}",
                  "-c", "<< /NeverEmbed [ ] >> setdistillerparams", "-f", str(entrada)],
                 timeout=config.jobs("timeout_motor_s"))
        with pikepdf.open(bruto) as pdf, pikepdf.open(entrada) as orig:
            copiar_metadados(orig, pdf)
            n = adicionar_tounicode(pdf)
            pdf.save(out)
    return {"tounicode_gerados": n}
