# -*- coding: utf-8 -*-
"""Portoes G1-G11 (PRD §11.1) e relatorio de qualidade (§11.5).

Regra: nenhum portao aprova por omissao. Se a verificacao nao roda, o portao reprova e diz por que;
os unicos 'nao se aplica' sao os que o PRD condiciona (G6 so em design, G9 so com padrao declarado,
G11 so com referencia)."""
from __future__ import annotations
import json, pathlib, re, time
import fitz, pikepdf
from .. import binfinder as BF, config, engines as ENG, fidelidade as FID, sha256_file, utcnow_iso
from ..erros import PapiroErro
from . import conform as CONF
from .inspect import classifica_paginas, fontes, fontes_pdffonts, metadados_texto, triagem_risco
from .pii import detectar_texto

N = pikepdf.Name
CATEGORIAS_SENSIVEIS_METADADOS = {"CPF", "CNPJ", "CNS", "RG", "TELEFONE", "EMAIL", "CEP", "DATA_NASCIMENTO"}


def _g1(arq: pathlib.Path) -> dict:
    det, ok = {}, True
    exe = BF.qual("qpdf")
    if exe:
        r = BF.rodar([exe, "--check", str(arq)], timeout=300, checar=False)
        saida = (r.stdout + r.stderr).decode("utf-8", "replace")
        reparo = re.search(r"(?i)recover|reconstruct|attempting|damaged|xref not found", saida)
        det["qpdf"] = {"exit": r.returncode, "reparo_implicito": bool(reparo)}
        ok &= r.returncode == 0 or (r.returncode == 3 and not reparo)
    else:
        try:
            with pikepdf.open(arq, attempt_recovery=False) as pdf:
                problemas = pdf.check()
            det["pikepdf_check"] = problemas[:5]
            ok &= not problemas
        except Exception as e:
            det["pikepdf_check"] = f"nao abriu sem reparo: {type(e).__name__}"
            ok = False
        det["aviso"] = "qpdf ausente: usado pikepdf.check"
    exe = BF.qual("pdfcpu")
    if exe:
        r = BF.rodar([exe, "validate", "-m", "r", str(arq)], timeout=300, checar=False)
        det["pdfcpu"] = {"exit": r.returncode}
        ok &= r.returncode == 0
    return {"ok": bool(ok), "det": det}


def _tinta(pix_amostras, largura: int, altura: int) -> float:
    escuros = sum(1 for v in pix_amostras if v < 245)
    return escuros / max(largura * altura, 1)


def _g2(arq: pathlib.Path, brancas_permitidas: set[int]) -> tuple[dict, list[int]]:
    brancas, erros = [], []
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(arq))
        try:
            for i in range(len(pdf)):
                try:
                    pagina = pdf[i]
                    tp = pagina.get_textpage()
                    tem_texto = bool(tp.get_text_range().strip())
                    tp.close()
                    img = pagina.render(scale=36 / 72, grayscale=True).to_pil().convert("L")
                    if not tem_texto and _tinta(img.tobytes(), img.width, img.height) <= 0.0005:
                        brancas.append(i + 1)
                except Exception as e:
                    erros.append({"pagina": i + 1, "erro": type(e).__name__})
        finally:
            pdf.close()
        motor = "pypdfium2"
    except ImportError:
        with fitz.open(arq) as d:
            for page in d:
                pix = page.get_pixmap(dpi=36, colorspace=fitz.csGRAY)
                if not page.get_text().strip() and _tinta(pix.samples, pix.width, pix.height) <= 0.0005:
                    brancas.append(page.number + 1)
        motor = "pymupdf"
    inesperadas = [p for p in brancas if p not in brancas_permitidas]
    return ({"ok": not erros and not inesperadas, "det": {"motor": motor, "paginas_em_branco": brancas,
                                                           "brancas_inesperadas": inesperadas, "erros_render": erros}},
            brancas)


def _g3(arq: pathlib.Path) -> dict:
    lista = fontes(arq)
    problemas = [f"{f['nome']}: {'nao embutida' if not f['embutida'] else 'sem ToUnicode'}"
                 for f in lista if not f["embutida"] or not f["to_unicode"]]
    poppler = fontes_pdffonts(arq)
    if poppler is not None:
        for f in poppler:
            if not f["embutida"] or not f["to_unicode"]:
                problemas.append(f"pdffonts {f['nome']}: emb={f['embutida']} uni={f['to_unicode']}")
    return {"ok": not problemas, "det": {"fontes": len(lista), "problemas": sorted(set(problemas))[:20],
                                         "conferido_com_pdffonts": poppler is not None}}


def _g4(arq: pathlib.Path) -> dict:
    classes = classifica_paginas(arq)
    sem_ocr = [c["pagina"] for c in classes if c["classe"] in ("escaneada", "hibrida") and not c["tem_camada_texto"]]
    total = sum(c["chars_visiveis"] + c["chars_ocr_invisivel"] for c in classes)
    vetoriais = [c["pagina"] for c in classes if not c["tem_camada_texto"] and c["cobertura_img"] == 0]
    ok = total > 0 and not sem_ocr
    det = {"chars": total, "escaneadas_sem_ocr": sem_ocr}
    if vetoriais:
        det["aviso_paginas_sem_texto"] = vetoriais
    return {"ok": ok, "det": det}


def _g5(arq: pathlib.Path, margem: float) -> tuple[dict, dict[int, list]]:
    marcas: dict[int, list] = {}
    transbordo = sobreposicao = margem_violada = 0
    with fitz.open(arq) as doc:
        for page in doc:
            area = page.rect
            spans = []
            for sp in page.get_texttrace():
                if sp.get("type") == 3 or sp.get("opacity", 1) < 0.5 or not sp.get("chars"):
                    continue
                horizontal = abs(sp.get("dir", (1, 0))[1]) < 0.01
                # um span pode atravessar varias linhas: medir por linha, a partir da caixa de cada caractere
                linhas: list[list] = []
                for ch in sp["chars"]:
                    if len(ch) < 4 or chr(ch[0]).isspace():
                        continue
                    cx = fitz.Rect(ch[3])
                    if cx.is_empty:
                        continue
                    if linhas and abs(linhas[-1][0] - ch[2][1]) < 0.5 * sp.get("size", 10):
                        linhas[-1][1] |= cx
                    else:
                        linhas.append([ch[2][1], cx])
                for _base, r in linhas:
                    if r.x1 > area.x1 + 1 or r.y1 > area.y1 + 1 or r.x0 < area.x0 - 1 or r.y0 < area.y0 - 1:
                        transbordo += 1
                        marcas.setdefault(page.number + 1, []).append(("transbordo", r))
                    elif (r.x0 < area.x0 + margem or r.y0 < area.y0 + margem or r.x1 > area.x1 - margem
                          or r.y1 > area.y1 - margem):
                        margem_violada += 1
                        marcas.setdefault(page.number + 1, []).append(("margem", r))
                    if horizontal:
                        spans.append(r)
            spans.sort(key=lambda s: s.y0)
            for i, ra in enumerate(spans):
                for rb in spans[i + 1:]:
                    if rb.y0 >= ra.y1:
                        break
                    inter = ra & rb
                    if inter.is_empty:
                        continue
                    if abs(inter) > 0.3 * min(abs(ra), abs(rb)):
                        sobreposicao += 1
                        marcas.setdefault(page.number + 1, []).append(("sobreposicao", inter))
                        break
    ok = transbordo == 0 and sobreposicao == 0 and margem_violada == 0
    return ({"ok": ok, "det": {"transbordo": transbordo, "sobreposicao": sobreposicao,
                               "margem_violada": margem_violada, "margem_minima_pt": margem}}, marcas)


def _g6(eh_design: bool, nota_visual: float | None) -> dict:
    if not eh_design:
        return {"ok": True, "det": "nao se aplica (peca nao e de design)", "aplica": False}
    if nota_visual is None:
        return {"ok": False, "pendente": True, "aplica": True,
                "det": "aguarda rubrica do pdf-revisor-qa (skill papiro-rubrica-visual): informe nota_visual"}
    return {"ok": float(nota_visual) >= 8.0, "aplica": True, "nota": float(nota_visual),
            "det": f"nota {float(nota_visual):.1f} (minimo 8,0)"}


def _g7(arq: pathlib.Path) -> dict:
    with pikepdf.open(arq) as pdf:
        info = pdf.docinfo or {}
        titulo = str(info.get("/Title", "")).strip()
        autor = str(info.get("/Author", "")).strip()
        produtor = str(info.get("/Producer", "")).strip()
        idioma = str(pdf.Root.get(N.Lang, "")).strip()
        xmp_titulo = ""
        try:
            with pdf.open_metadata() as xmp:
                idioma = idioma or " ".join(xmp.get("dc:language", []) or [])
                xmp_titulo = str(xmp.get("dc:title", "") or "")
        except Exception:
            pass
    faltas = [n for n, v in (("titulo", titulo), ("autor", autor), ("produtor", produtor)) if not v]
    if not idioma.lower().startswith("pt"):
        faltas.append(f"idioma pt-BR (encontrado: {idioma or 'nenhum'})")
    det = {"titulo": bool(titulo), "autor": bool(autor), "produtor": bool(produtor), "idioma": idioma, "faltando": faltas}
    if xmp_titulo and titulo and xmp_titulo != titulo:
        det["aviso"] = "titulo divergente entre Info e XMP"
    return {"ok": not faltas, "det": det}


def _g8(arq: pathlib.Path, meta_mb: float | None) -> dict:
    mb = arq.stat().st_size / 1048576
    dentro = meta_mb is None or mb <= meta_mb
    return {"ok": True, "aviso": not dentro, "det": f"{mb:.2f} MB" + (f" (meta {meta_mb} MB)" if meta_mb else "")}


def _g9(arq: pathlib.Path, padrao: str | None) -> dict:
    """Um ou mais padroes separados por virgula ('PDF/A-2b,PDF/UA-1'): todos precisam passar."""
    padroes = [x.strip() for x in (padrao or "").split(",") if x.strip()]
    if not padroes:
        return {"ok": True, "det": "nao se aplica (nenhum padrao declarado)", "aplica": False}
    resultados, ok = {}, True
    for p in padroes:
        try:
            r = CONF.validar_padrao(arq, p)
            resultados[p] = {k: v for k, v in r.items() if k != "ok"} | {"ok": r["ok"]}
            ok &= bool(r["ok"])
        except PapiroErro as e:
            resultados[p] = f"{e.codigo}: {e.mensagem}"
            ok = False
    return {"ok": ok, "aplica": True, "det": resultados}


def _g10(arq: pathlib.Path, anexos_permitidos: bool) -> dict:
    tri = triagem_risco(arq)
    f = tri["flags"]
    so_anexos = tri["nota_risco"] == "MEDIA" and f["anexos"] and not (
        f["acoes_automaticas_aa"] or f["xfa"] or f["submit_import"] or f["goto_remoto"] or f["openaction_acao"])
    risco_ok = tri["nota_risco"] == "BAIXA" or (anexos_permitidos and so_anexos)
    sensiveis = sorted({a["categoria"] for a in detectar_texto(metadados_texto(arq), usar_presidio=False)
                        if a["categoria"] in CATEGORIAS_SENSIVEIS_METADADOS})
    return {"ok": bool(risco_ok and not sensiveis),
            "det": {"nota_risco": tri["nota_risco"], "flags": f, "dados_sensiveis_em_metadados": sensiveis}}


def _g11(arq: pathlib.Path, referencia: pathlib.Path | None) -> dict:
    if referencia is None:
        return {"ok": True, "det": "nao se aplica (sem referencia)", "aplica": False}
    limiar = float(config.qa("limiar_ssim"))
    fid = FID.comparar(referencia, arq)
    txt = FID.similaridade_texto(referencia, arq)
    ok = fid["mesmo_numero_paginas"] and fid["ssim_pior_bloco"] >= limiar and txt >= 0.99
    return {"ok": bool(ok), "aplica": True,
            "det": {"ssim_medio": fid["ssim_medio"], "ssim_pior_bloco": fid["ssim_pior_bloco"], "limiar": limiar,
                    "texto_igual": round(txt, 4), "paginas": [fid["paginas_a"], fid["paginas_b"]]}}


def run(arquivo: pathlib.Path, perfil_tamanho_mb: float | None = None, exige_ssim_ref: pathlib.Path | None = None,
        eh_design: bool = False, nota_visual: float | None = None, padrao: str | None = None,
        brancas_permitidas: list[int] | None = None, anexos_permitidos: bool = False) -> dict:
    arquivo = pathlib.Path(arquivo)
    tempos, portoes = {}, {}
    try:
        with fitz.open(arquivo) as d:
            paginas = d.page_count
    except Exception as e:
        return {"status": "REPROVADO", "portoes": {"G1": {"ok": False, "det": f"nao abre: {type(e).__name__}"}},
                "bloqueantes": ["G1"], "avisos": [], "arquivo_sha256": sha256_file(arquivo), "marcas": {}}
    marcas: dict = {}
    brancas: list[int] = []
    etapas = [
        ("G1", lambda: _g1(arquivo)),
        ("G2", lambda: _g2(arquivo, set(brancas_permitidas or []))),
        ("G3", lambda: _g3(arquivo)),
        ("G4", lambda: _g4(arquivo)),
        ("G5", lambda: _g5(arquivo, float(config.qa("margem_minima_pt")))),
        ("G6", lambda: _g6(eh_design, nota_visual)),
        ("G7", lambda: _g7(arquivo)),
        ("G8", lambda: _g8(arquivo, perfil_tamanho_mb)),
        ("G9", lambda: _g9(arquivo, padrao)),
        ("G10", lambda: _g10(arquivo, anexos_permitidos)),
        ("G11", lambda: _g11(arquivo, exige_ssim_ref)),
    ]
    for nome, fn in etapas:
        t0 = time.time()
        try:
            r = fn()
            if nome == "G2":
                r, brancas = r
            if nome == "G5":
                r, marcas = r
        except Exception as e:  # noqa: BLE001 - portao que nao roda reprova
            r = {"ok": False, "det": f"verificacao falhou: {type(e).__name__}: {str(e)[:150]}"}
        tempos[nome] = round(time.time() - t0, 3)
        portoes[nome] = r
    bloqueantes = [k for k, v in portoes.items() if k != "G8" and not v["ok"]]
    if not bloqueantes:
        status = "APROVADO"
    elif bloqueantes == ["G6"] and portoes["G6"].get("pendente"):
        status = "PENDENTE_REVISAO"
    else:
        status = "REPROVADO"
    avisos = (["G8: tamanho acima da meta"] if portoes["G8"].get("aviso") else [])
    return {"status": status, "portoes": portoes, "bloqueantes": bloqueantes, "avisos": avisos, "paginas": paginas,
            "tempos_s": tempos, "arquivo_sha256": sha256_file(arquivo), "marcas": marcas, "brancas": brancas,
            "motores": {m: ENG.versao(m) for m in ("qpdf", "pdfcpu", "pypdfium2", "poppler_pdffonts", "verapdf",
                                                   "pymupdf", "pikepdf", "opencv-python-headless")},
            "gerado_em": utcnow_iso()}


def gravar_relatorio(qa: dict, arquivo: pathlib.Path, destino_json: pathlib.Path, job_id: str,
                     max_miniaturas: int = 6) -> pathlib.Path:
    """qa-report.json + .md (mesmo nome) com miniaturas marcadas em <nome>-evidencias/ (vermelho = G5)."""
    out_dir = destino_json.parent
    evid = out_dir / f"{destino_json.stem}-evidencias"
    evid.mkdir(parents=True, exist_ok=True)
    marcas = qa.get("marcas", {})
    alvo = sorted(set(list(marcas)[:max_miniaturas]) | set(qa.get("brancas", [])[:2]) | {1})[:max_miniaturas]
    miniaturas = []
    with fitz.open(arquivo) as doc:
        for pno in alvo:
            if pno > doc.page_count:
                continue
            page = doc[pno - 1]
            shape = page.new_shape()
            for _motivo, r in marcas.get(pno, []):
                shape.draw_rect(r)
            shape.finish(color=(1, 0, 0), width=1.5)
            shape.commit()
            p = evid / f"pag{pno:03d}.png"
            page.get_pixmap(dpi=60).save(p)
            miniaturas.append(p.name)
    serial = {k: v for k, v in qa.items() if k != "marcas"}
    serial["marcas"] = {str(k): [(m, [round(c, 1) for c in r]) for m, r in v] for k, v in marcas.items()}
    serial["job_id"] = job_id
    serial["miniaturas"] = [f"{evid.name}/{m}" for m in miniaturas]
    j = destino_json
    j.write_text(json.dumps(serial, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    linhas = [f"# Relatório de qualidade — job {job_id}", "", f"**Status:** {qa['status']}  ",
              f"**Arquivo (SHA-256):** `{qa['arquivo_sha256']}`  ", f"**Páginas:** {qa.get('paginas')}  ",
              f"**Gerado em:** {qa.get('gerado_em')}", "", "| Portão | Resultado | Detalhe |", "| --- | --- | --- |"]
    for k, v in qa["portoes"].items():
        res = "ok" if v["ok"] else ("pendente" if v.get("pendente") else "REPROVADO")
        det = json.dumps(v.get("det"), ensure_ascii=False, default=str)
        linhas.append(f"| {k} | {res} | {det[:300].replace('|', '/')} |")
    linhas += ["", "## Motores", ""] + [f"- {m}: {v or 'ausente'}" for m, v in qa.get("motores", {}).items()]
    linhas += ["", "## Evidências", ""] + [f"![página]({m})" for m in serial["miniaturas"]]
    j.with_suffix(".md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return j
