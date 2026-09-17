# -*- coding: utf-8 -*-
"""Nivel 2 - edicao RF-201..RF-210 + tarjamento real RF-808 (PyMuPDF + pikepdf).
Texto inserido usa fonte OFL embutida de fonts/ (G3 exige fonte embutida com ToUnicode)."""
from __future__ import annotations
import pathlib, re, tempfile
import fitz, pikepdf
from .. import FONTS
from ..erros import PapiroErro
from .inspect import abrir

FONTE_PADRAO = FONTS / "LiberationSans-Regular.ttf"
FONTE_NEGRITO = FONTS / "LiberationSans-Bold.ttf"
N = pikepdf.Name


def _fonte(page: fitz.Page, arquivo: pathlib.Path = FONTE_PADRAO) -> str:
    if not arquivo.exists():
        raise PapiroErro("E_SEM_SUPORTE", f"fonte {arquivo.name} ausente em fonts/")
    nome = "papiro-" + arquivo.stem.split("-")[-1].lower()
    page.insert_font(fontname=nome, fontfile=str(arquivo))
    return nome


def _ancora(page: fitz.Page, texto: str) -> fitz.Rect | None:
    hits = page.search_for(texto) if texto else []
    return hits[0] if hits else None


def _salvar(doc: fitz.Document, out: pathlib.Path) -> int:
    doc.save(out, garbage=3, deflate=True)
    n = doc.page_count
    doc.close()
    return n


# ---------------- RF-201 / RF-205 ----------------
def carimbo(entrada: pathlib.Path, out: pathlib.Path, texto: str = "", pagina: int = 1, x: float = 72, y: float = 72,
            tamanho: float = 14, cor=(0.75, 0, 0), ancora: str = "", abaixo_pt: float = 14,
            imagem: pathlib.Path | None = None, qr: str = "", largura: float = 120) -> dict:
    """Texto, imagem ou QR em coordenada (pt, origem no topo) ou relativo a uma ancora de texto."""
    doc = abrir(entrada)
    if not 1 <= pagina <= doc.page_count:
        raise PapiroErro("E_ENTRADA", f"pagina {pagina} inexistente")
    page = doc[pagina - 1]
    if ancora:
        r = _ancora(page, ancora)
        if r is None:
            doc.close()
            raise PapiroErro("E_ENTRADA", "texto ancora nao encontrado na pagina")
        x, y = r.x0, r.y1 + abaixo_pt
    if qr:
        import segno
        with tempfile.TemporaryDirectory() as t:
            png = pathlib.Path(t) / "qr.png"
            segno.make(qr, error="m").save(png, scale=10, border=2)
            page.insert_image(fitz.Rect(x, y, x + largura, y + largura), filename=str(png))
    elif imagem:
        with fitz.open(imagem) as im:
            proporcao = im[0].rect.height / max(im[0].rect.width, 1)
        page.insert_image(fitz.Rect(x, y, x + largura, y + largura * proporcao), filename=str(imagem))
    elif texto:
        page.insert_text((x, y + tamanho), texto, fontname=_fonte(page), fontsize=tamanho, color=cor)
    else:
        doc.close()
        raise PapiroErro("E_ENTRADA", "informe texto, imagem ou qr")
    return {"paginas": _salvar(doc, out), "posicao": [round(x, 1), round(y, 1)]}


# ---------------- RF-203 ----------------
def marca_dagua(entrada: pathlib.Path, out: pathlib.Path, texto: str, opacidade: float = 0.18,
                tamanho: float = 60, camada: str = "Marca d'agua") -> dict:
    """Texto diagonal em camada OCG propria (liga e desliga no visualizador)."""
    if not texto:
        raise PapiroErro("E_ENTRADA", "texto da marca d'agua vazio")
    doc = abrir(entrada)
    ocg = doc.add_ocg(camada, on=True)
    for page in doc:
        nome = _fonte(page)
        largura = fitz.get_text_length(texto, fontname="helv", fontsize=tamanho)
        centro = fitz.Point(page.rect.width / 2, page.rect.height / 2)
        inicio = fitz.Point(centro.x - largura / 2, centro.y + tamanho / 3)
        page.insert_text(inicio, texto, fontname=nome, fontsize=tamanho, color=(0.5, 0.5, 0.5),
                         fill_opacity=opacidade, morph=(centro, fitz.Matrix(-45)), oc=ocg)
    return {"paginas": _salvar(doc, out), "camada_ocg": camada}


# ---------------- RF-204 ----------------
def cabecalho_rodape(entrada: pathlib.Path, out: pathlib.Path, modelo: str = "Página {n} de {total}",
                     posicao: str = "rodape", tamanho: float = 9, bates_prefixo: str = "", bates_inicio: int = 1,
                     margem: float = 20) -> dict:
    """{n}, {total} e {bates} no modelo. Avisa quando a faixa ja tem conteudo (nao sobrepoe calado)."""
    doc = abrir(entrada)
    total, avisos = doc.page_count, []
    for page in doc:
        n = page.number + 1
        texto = modelo.format(n=n, total=total, bates=f"{bates_prefixo}{bates_inicio + n - 1:06d}")
        nome = _fonte(page)
        largura = fitz.get_text_length(texto, fontname="helv", fontsize=tamanho)
        y = margem + tamanho if posicao == "cabecalho" else page.rect.height - margem
        faixa = fitz.Rect(0, y - tamanho - 2, page.rect.width, y + 3)
        if page.get_text("text", clip=faixa).strip():
            avisos.append(f"pagina {n}: faixa do {posicao} ja tinha conteudo")
            continue
        page.insert_text(((page.rect.width - largura) / 2, y), texto, fontname=nome, fontsize=tamanho, color=(0, 0, 0))
    return {"paginas": _salvar(doc, out), "avisos": avisos}


# ---------------- RF-202 ----------------
def _span_em(page: fitz.Page, r: fitz.Rect) -> dict | None:
    for b in page.get_text("dict", clip=r)["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                if fitz.Rect(sp["bbox"]).intersects(r):
                    return sp
    return None


def substituir_texto(entrada: pathlib.Path, out: pathlib.Path, de: str, para: str) -> dict:
    """Remove a ocorrencia (redacao so de texto) e reinsere com o mesmo corpo, cor e origem.
    Usa a propria fonte embutida quando ela tem todos os glifos; senao Liberation Sans e avisa."""
    if not de:
        raise PapiroErro("E_ENTRADA", "texto de busca vazio")
    doc = abrir(entrada)
    trocas, avisos = 0, []
    for page in doc:
        ocorrencias = []
        for r in page.search_for(de):
            sp = _span_em(page, r)
            ocorrencias.append((r, sp))
            page.add_redact_annot(r)
        if not ocorrencias:
            continue
        fontes_pag = {f[3].split("+")[-1]: f[0] for f in page.get_fonts(full=True)}
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        for r, sp in ocorrencias:
            tamanho = sp["size"] if sp else 11
            srgb = sp["color"] if sp else 0
            cor = ((srgb >> 16 & 255) / 255, (srgb >> 8 & 255) / 255, (srgb & 255) / 255)
            nome_fonte = _fonte(page)
            if sp:
                base = sp["font"].split("+")[-1]
                xref = fontes_pag.get(base)
                if xref:
                    try:
                        _n, _e, _t, buf = doc.extract_font(xref)
                        if not buf:
                            avisos.append(f"fonte {base} nao embutida no original: usada Liberation Sans")
                        elif all(fitz.Font(fontbuffer=buf).has_glyph(ord(c)) for c in para if not c.isspace()):
                            nome_fonte = f"orig{xref}"
                            page.insert_font(fontname=nome_fonte, fontbuffer=buf)
                        else:
                            avisos.append(f"fonte {base} sem glifos para o novo texto: usada Liberation Sans")
                    except Exception:
                        avisos.append(f"fonte {base} nao extraivel: usada Liberation Sans")
            origem = fitz.Point(sp["origin"]) if sp else fitz.Point(r.x0, r.y1 - 2)
            page.insert_text(origem, para, fontname=nome_fonte, fontsize=tamanho, color=cor)
            trocas += 1
    return {"trocas": trocas, "paginas": _salvar(doc, out), "avisos": sorted(set(avisos))}


# ---------------- RF-210 ----------------
def metadados(entrada: pathlib.Path, out: pathlib.Path, titulo: str = "", autor: str = "", assunto: str = "",
              palavras: str = "", idioma: str = "pt-BR", produtor: str = "PAPIRO") -> dict:
    """Info e XMP sincronizados + /Lang no catalogo."""
    with pikepdf.open(entrada) as pdf:
        info = {"/Title": titulo, "/Author": autor, "/Subject": assunto, "/Keywords": palavras, "/Producer": produtor}
        for k, v in info.items():
            if v:
                pdf.docinfo[k] = v
        with pdf.open_metadata(set_pikepdf_as_editor=False) as xmp:
            xmp.load_from_docinfo(pdf.docinfo, delete_missing=False)
            if idioma:
                xmp["dc:language"] = [idioma]
        if idioma:
            pdf.Root.Lang = pikepdf.String(idioma)
        pdf.save(out)
    return {"ok": True, "idioma": idioma}


# ---------------- RF-808 ----------------
def tarjar(entrada: pathlib.Path, out: pathlib.Path, caixas: list[dict]) -> dict:
    """Remocao real de texto, pixels de imagem e vetores sob cada caixa; depois extrai de novo e
    confirma a ausencia; limpa metadados, XMP e anexos (§12.3). Falha na verificacao = nada entregue."""
    if not caixas:
        raise PapiroErro("E_ENTRADA", "nenhuma caixa de tarja informada")
    from collections import Counter
    doc = abrir(entrada)
    antes: dict[int, Counter] = {}
    removidos: dict[int, Counter] = {}
    for c in caixas:
        pg = int(c.get("pagina", 1))
        if not 1 <= pg <= doc.page_count:
            raise PapiroErro("E_ENTRADA", f"pagina {pg} inexistente")
        page = doc[pg - 1]
        r = fitz.Rect(float(c["x0"]), float(c["y0"]), float(c["x1"]), float(c["y1"]))
        palavras = page.get_text("words")
        antes.setdefault(pg, Counter(w[4] for w in palavras))
        for w in palavras:
            if fitz.Rect(w[:4]).intersects(r):
                removidos.setdefault(pg, Counter())[w[4]] += 1
        page.add_redact_annot(r, fill=(0, 0, 0))
    for page in doc:
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS, graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
    doc.set_metadata({})
    doc.del_xml_metadata()
    for nome in list(doc.embfile_names()):
        doc.embfile_del(nome)
    tmp = out.with_suffix(".tarja.tmp")
    doc.save(tmp, garbage=4, deflate=True, clean=True)
    doc.close()
    remanescentes = []
    with fitz.open(tmp) as chk:
        for pg, rem in removidos.items():
            depois = Counter(w[4] for w in chk[pg - 1].get_text("words"))
            for palavra, qtd in rem.items():
                if depois[palavra] > antes[pg][palavra] - qtd:
                    remanescentes.append(pg)
    if remanescentes:
        tmp.unlink(missing_ok=True)
        raise PapiroErro("E_CONFORMIDADE", f"texto tarjado ainda extraivel nas paginas {sorted(set(remanescentes))}")
    tmp.replace(out)
    with fitz.open(out) as d:
        n = d.page_count
    return {"tarjas": len(caixas), "paginas": n, "palavras_removidas": sum(sum(c.values()) for c in removidos.values()),
            "verificado": True,
            "verificacao": "texto re-extraido sem as palavras tarjadas; metadados, XMP e anexos removidos"}
