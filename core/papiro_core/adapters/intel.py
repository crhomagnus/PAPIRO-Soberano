# -*- coding: utf-8 -*-
"""Nivel 6 - OCR por pagina (RF-601), texto, RAG lexical com citacao de pagina e evidencias (RF-606)."""
from __future__ import annotations
import os, pathlib, re, shutil, sqlite3, subprocess, sys, tempfile
import fitz
from .. import FONTS, KB, binfinder as BF, config, engines as ENG
from ..erros import PapiroErro
from .inspect import abrir, classifica_paginas
from .pii import detectar_pii  # noqa: F401  (reexportado)


def texto_completo(entrada: pathlib.Path) -> str:
    with abrir(entrada) as doc:
        return "\n".join(p.get_text() for p in doc)


# ---------------- RF-601 ----------------
def paginas_para_ocr(entrada: pathlib.Path, forcar: bool = False) -> list[int]:
    classes = classifica_paginas(entrada)
    if forcar:
        return [c["pagina"] for c in classes]
    return [c["pagina"] for c in classes if not c["tem_camada_texto"] and c["cobertura_img"] > 0.05]


def _paralelo() -> int:
    """Processos de OCR: papiro.toml [jobs] ocr_paralelo; padrao = metade dos nucleos, no maximo 4 (RAM de 16 GB)."""
    valor = config.carregar()["jobs"].get("ocr_paralelo")
    return max(1, int(valor)) if valor else max(1, min(4, (os.cpu_count() or 2) // 2))


def _ocr_ocrmypdf(entrada: pathlib.Path, out: pathlib.Path, idioma: str, pdfa: bool, forcar: bool) -> dict:
    if not ENG.disponivel("ocrmypdf"):
        raise PapiroErro("E_SEM_SUPORTE", "OCRmyPDF nao instalado")
    cmd = [sys.executable, "-m", "ocrmypdf", "-l", idioma, "--output-type", "pdfa" if pdfa else "pdf",
           "--force-ocr" if forcar else "--skip-text", "--jobs", str(_paralelo()), "--quiet", str(entrada), str(out)]
    env = dict(os.environ)
    env.update(BF.env_extra())
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=config.jobs("timeout_motor_s"), env=env)
    except subprocess.TimeoutExpired:
        raise PapiroErro("E_TEMPO", "OCRmyPDF excedeu o tempo")
    if r.returncode == 10 and out.exists():
        return {"aviso": "OCR concluido, mas a conversao para PDF/A falhou (saida em PDF comum)"}
    if r.returncode != 0 or not out.exists():
        ultima = (r.stderr.decode("utf-8", "replace").strip().splitlines() or [""])[-1]
        raise PapiroErro("E_MOTOR", f"OCRmyPDF saiu com {r.returncode}: {ultima[:200]}")
    return {}


def _ocr_tesseract(entrada: pathlib.Path, out: pathlib.Path, idioma: str, paginas: list[int]) -> dict:
    """Camada invisivel direto do Tesseract (TSV): palavra a palavra, escalada a caixa, fonte embutida."""
    exe = BF.qual("tesseract")
    if not exe:
        raise PapiroErro("E_SEM_SUPORTE", "Tesseract nao instalado")
    if idioma.split("+")[0] not in ENG.tesseract_idiomas():
        raise PapiroErro("E_SEM_SUPORTE", f"dados de idioma '{idioma}' ausentes no Tesseract")
    fonte_arq = FONTS / "LiberationSans-Regular.ttf"
    fonte = fitz.Font(fontfile=str(fonte_arq))
    palavras_total = 0
    from concurrent.futures import ThreadPoolExecutor
    with abrir(entrada) as doc, tempfile.TemporaryDirectory() as t:
        dims = {}
        for pg in paginas:
            pix = doc[pg - 1].get_pixmap(dpi=300)
            pix.save(pathlib.Path(t) / f"p{pg}.png")
            dims[pg] = (pix.width, pix.height)
        os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # um nucleo por processo; o paralelismo vem dos processos

        def reconhecer(pg):
            return pg, BF.rodar([exe, str(pathlib.Path(t) / f"p{pg}.png"), "stdout", "-l", idioma, "tsv"], timeout=300)
        with ThreadPoolExecutor(max_workers=_paralelo()) as pool:
            resultados = dict(pool.map(reconhecer, paginas))
        for pg in paginas:
            page = doc[pg - 1]
            r = resultados[pg]
            sx, sy = page.rect.width / dims[pg][0], page.rect.height / dims[pg][1]
            page.insert_font(fontname="papiro-ocr", fontfile=str(fonte_arq))
            for ln in r.stdout.decode("utf-8", "replace").splitlines()[1:]:
                c = ln.split("\t")
                if len(c) < 12 or c[0] != "5" or not c[11].strip() or float(c[10]) < 0:
                    continue
                x, y, w, h = (int(c[6]) * sx, int(c[7]) * sy, int(c[8]) * sx, int(c[9]) * sy)
                palavra = c[11]
                corpo = max(h * 0.9, 1)
                comp = fonte.text_length(palavra, fontsize=corpo) or 1
                ponto = fitz.Point(x, y + h * 0.85)
                page.insert_text(ponto, palavra, fontname="papiro-ocr", fontsize=corpo, render_mode=3,
                                 morph=(ponto, fitz.Matrix(w / comp, 0, 0, 1, 0, 0)))
                palavras_total += 1
        doc.save(out, garbage=3, deflate=True)
    return {"palavras": palavras_total}


def ocr(entrada: pathlib.Path, out: pathlib.Path, idioma: str = "por", pdfa: bool = True, forcar: bool = False) -> dict:
    alvo = paginas_para_ocr(entrada, forcar)
    if not alvo:
        shutil.copyfile(entrada, out)
        return {"via": "texto-nativo", "paginas_ocr": [], "aviso": "todas as paginas ja tem camada de texto"}
    tentativas, via, extra = [], None, {}
    for nome, fn in (("ocrmypdf", lambda: _ocr_ocrmypdf(entrada, out, idioma, pdfa, forcar)),
                     ("tesseract", lambda: _ocr_tesseract(entrada, out, idioma, alvo))):
        try:
            out.unlink(missing_ok=True)
            extra = fn() or {}
            via = nome
            break
        except PapiroErro as e:
            tentativas.append(f"{nome}: {e.codigo} {e.mensagem}")
    if via is None:
        raise PapiroErro("E_SEM_SUPORTE", "nenhum motor de OCR disponivel: " + " | ".join(tentativas))
    faltando = [c["pagina"] for c in classifica_paginas(out) if c["pagina"] in alvo and not c["tem_camada_texto"]]
    if faltando:
        raise PapiroErro("E_MOTOR", f"OCR nao produziu texto nas paginas {faltando}")
    avisos = [extra.pop("aviso")] if extra.get("aviso") else []
    if via == "tesseract" and pdfa:
        avisos.append("saida sem PDF/A (OCRmyPDF indisponivel): use conform pdfa")
    return {"via": via, "paginas_ocr": alvo, "fallback_from": "ocrmypdf" if via == "tesseract" else None,
            "tentativas": tentativas, "avisos": avisos, **extra}


# ---------------- RF-606 ----------------
RAG_DB = KB / "rag.db"


def _rag_con(db: pathlib.Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS trechos USING fts5(doc_id UNINDEXED, pagina UNINDEXED, "
                "sha256 UNINDEXED, texto, tokenize='unicode61 remove_diacritics 2')")
    con.execute("CREATE TABLE IF NOT EXISTS documentos(doc_id TEXT PRIMARY KEY, sha256 TEXT, caminho TEXT, paginas INT)")
    return con


def rag_index(entrada: pathlib.Path, doc_id: str, sha256: str, caminho_original: str, db: pathlib.Path = RAG_DB,
              tamanho: int = 1200, sobreposicao: int = 200) -> dict:
    con = _rag_con(db)
    con.execute("DELETE FROM trechos WHERE doc_id=?", (doc_id,))
    n_trechos = 0
    with abrir(entrada) as doc:
        for page in doc:
            texto = page.get_text()
            passo = max(tamanho - sobreposicao, 1)
            for i in range(0, max(len(texto), 1), passo):
                trecho = texto[i:i + tamanho]
                if trecho.strip():
                    con.execute("INSERT INTO trechos VALUES(?,?,?,?)", (doc_id, page.number + 1, sha256, trecho))
                    n_trechos += 1
        paginas = doc.page_count
    con.execute("INSERT OR REPLACE INTO documentos VALUES(?,?,?,?)", (doc_id, sha256, caminho_original, paginas))
    con.commit()
    con.close()
    return {"doc_id": doc_id, "paginas": paginas, "trechos": n_trechos}


def rag_ask(pergunta: str, db: pathlib.Path = RAG_DB, limite: int = 5) -> list[dict]:
    termos = [t for t in re.findall(r"\w{3,}", pergunta.lower())][:12]
    if not termos or not db.exists():
        return []
    con = _rag_con(db)
    consulta = " OR ".join('"' + t.replace('"', "") + '"' for t in termos)
    rows = con.execute("SELECT t.doc_id, t.pagina, snippet(trechos, 3, '[', ']', ' ... ', 24), bm25(trechos), d.caminho "
                       "FROM trechos t LEFT JOIN documentos d ON d.doc_id = t.doc_id "
                       "WHERE trechos MATCH ? ORDER BY bm25(trechos) LIMIT ?", (consulta, limite)).fetchall()
    con.close()
    return [{"doc": r[0], "pagina": int(r[1]), "trecho": r[2], "relevancia": round(-r[3], 4), "caminho": r[4],
             "termos": termos} for r in rows]


def rag_evidencias(respostas: list[dict], out: pathlib.Path) -> int:
    """PDF so com as paginas citadas, termos destacados e nota com a origem (doc e pagina)."""
    final = fitz.open()
    for r in respostas:
        caminho = pathlib.Path(r.get("caminho") or "")
        if not caminho.is_file():
            continue
        with fitz.open(caminho) as src:
            final.insert_pdf(src, from_page=r["pagina"] - 1, to_page=r["pagina"] - 1)
        page = final[-1]
        for termo in r["termos"]:
            for q in page.search_for(termo, quads=True):
                page.add_highlight_annot(q)
        nota = page.add_text_annot((12, 12), f"{r['doc']} - pagina {r['pagina']}")
        nota.update()
    n = final.page_count
    if n:
        final.save(out, garbage=3, deflate=True)
    final.close()
    return n
