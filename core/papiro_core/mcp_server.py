# -*- coding: utf-8 -*-
"""Servidor MCP `papiro` - 38 ferramentas (PRD §8.3), FastMCP stdio.

Contrato §8.1: toda ferramenta de escrita exige out_dir (dentro de work/ ou out/) e nunca altera a entrada;
dry_run devolve o plano; toda resposta e o envelope unico; entregas em PDF passam pelos portoes G1-G11
(qa=false so para passos intermediarios)."""
from __future__ import annotations
import json, pathlib
from mcp.server.fastmcp import FastMCP
from . import KB, OUT, REPO, RECIPES, engines as ENG, jobs as JOBS, roteador as ROT
from .caminhos import nome_seguro, validar_entrada
from .erros import PapiroErro
from .runner import Contexto, Resultado, executar
from .adapters import compare as CMP, conform as CONF, convert as CONV, create as CRE, edit as ED
from .adapters import inspect as INS, intel as INTEL, pages as PAG, qa as QA

mcp = FastMCP("papiro", instructions=(
    "PAPIRO: ferramentas de PDF em pt-BR. out_dir obrigatorio (dentro de work/ ou out/ da raiz); a entrada nunca "
    "e alterada; resposta sempre no envelope {ok, job_id, outputs, engine, metrics, warnings, qa, audit_id}. "
    "Entrega so com qa.status APROVADO."))


# ---------------- auxiliares ----------------
def _json(ctx: Contexto, nome: str, dados) -> pathlib.Path:
    p = ctx.saida(nome)
    p.write_text(json.dumps(dados, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return p


def _com_qa(ctx: Contexto, res: Resultado, pdf: pathlib.Path, qa: bool, **kw) -> Resultado:
    if not qa:
        res.warnings.append("QA nao executado (qa=false): passo intermediario, nao e entrega")
        return res
    q = QA.run(pdf, **kw)
    rep = QA.gravar_relatorio(q, pdf, ctx.saida("qa-report.json"), ctx.job_id)
    res.qa, res.qa_report = q, rep
    res.outputs += [rep, rep.with_suffix(".md")]
    return res


def _lista(texto: str) -> list[str]:
    return [x.strip() for x in (texto or "").replace("\n", ";").split(";") if x.strip()]


def _sem_suporte(ferramenta: str, op: str, motivo: str, out_dir: str = "", entradas=()) -> dict:
    def acao(_ctx):
        raise PapiroErro("E_SEM_SUPORTE", motivo)
    return executar(ferramenta, op, acao, entradas=list(entradas), out_dir=out_dir or None, escreve=False)


# ================= Inspecao (3) =================
@mcp.tool()
def inspect(op: str, entrada: str, out_dir: str, senha: str = "", dry_run: bool = False) -> dict:
    """RF-001..009. op=all|inventory|fonts|images|pages|revisions|risk. JSON em out_dir."""
    funcs = {"inventory": INS.inventario, "fonts": INS.fontes, "images": INS.imagens,
             "pages": INS.classifica_paginas, "revisions": INS.revisoes, "risk": INS.triagem_risco}

    def acao(ctx):
        p, s = ctx.entradas[0], senha or None
        if op == "all":
            d = {k: f(p, s) for k, f in funcs.items()}
            d["fonts_pdffonts"] = INS.fontes_pdffonts(p)
            resumo = {"inventario": d["inventory"], "risco": d["risk"]["nota_risco"]}
        elif op in funcs:
            d = funcs[op](p, s)
            resumo = d if not isinstance(d, list) else {"itens": len(d), "primeiros": d[:20]}
        else:
            raise PapiroErro("E_SEM_SUPORTE", f"inspect.{op}")
        return Resultado(outputs=[_json(ctx, f"inspect_{op}.json", d)], motor="pymupdf+pikepdf", dados=resumo)
    return executar("inspect", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="inspecao", dry_run=dry_run)


@mcp.tool()
def search(entrada: str, out_dir: str, regex: str, ignorar_caixa: bool = False, dry_run: bool = False) -> dict:
    """RF-006: busca texto/regex; devolve pagina e caixa (pt)."""
    def acao(ctx):
        hits = INS.busca(ctx.entradas[0], regex, ignorar_caixa=ignorar_caixa)
        return Resultado(outputs=[_json(ctx, "busca.json", hits)], motor="pymupdf",
                         dados={"ocorrencias": len(hits), "primeiras": hits[:50]})
    return executar("search", "regex", acao, entradas=[entrada], out_dir=out_dir, tarefa="inspecao", dry_run=dry_run)


@mcp.tool()
def render_pages(entrada: str, out_dir: str, dpi: int = 110, prancha: bool = False, dry_run: bool = False) -> dict:
    """RF-005: PNG por pagina (pypdfium2) e prancha de contato opcional."""
    def acao(ctx):
        destino = ctx.saida("render")
        destino.mkdir(parents=True, exist_ok=True)
        return Resultado(outputs=CONV.para_png(ctx.entradas[0], destino, dpi, prancha), motor="pypdfium2")
    return executar("render_pages", "png", acao, entradas=[entrada], out_dir=out_dir, tarefa="inspecao", dry_run=dry_run)


# ================= Paginas (3) =================
@mcp.tool()
def pages(op: str, out_dir: str, entrada: str = "", entradas: str = "", paginas: str = "", angulo: str = "90",
          intervalos: str = "", a_cada: int = 0, por_marcador: bool = False, papel: str = "a4", por_folha: int = 2,
          caixas_json: str = "{}", rotulos_json: str = "[]", limiar_tinta: float = 0.0005,
          versos_invertidos: bool = True, saida: str = "", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-101..110. op=merge|split|extract|delete|move|duplicate|reverse|interleave|rotate|resize|boxes|nup|
    booklet|labels|blank_remove. entradas separadas por ';'. paginas '1,3-5'."""
    lista = ([entrada] if entrada else []) + _lista(entradas)

    def acao(ctx):
        e = ctx.entradas
        nome = saida or f"{op}.pdf"
        n = 0
        if op in ("extract", "delete", "move", "duplicate", "reverse", "rotate", "boxes", "labels", "resize", "nup",
                  "booklet", "blank_remove", "split"):
            with INS.abrir(e[0]) as d:
                n = d.page_count
        if op == "split":
            destino = ctx.saida("partes")
            destino.mkdir(parents=True, exist_ok=True)
            outs = PAG.split(e[0], destino, _lista(intervalos) or None, a_cada, por_marcador)
            return Resultado(outputs=outs, motor="pikepdf", dados={"partes": len(outs)})
        out = ctx.saida(nome)
        dados = None
        if op == "merge":
            dados = PAG.merge(e, out, [pathlib.Path(p).stem for p in ctx.originais])
        elif op in ("extract", "move"):
            dados = {"paginas": PAG.reordenar(e[0], out, PAG.parse_paginas(paginas, n))}
        elif op == "duplicate":
            seq = []
            dup = set(PAG.parse_paginas(paginas, n))
            for p in range(1, n + 1):
                seq += [p, p] if p in dup else [p]
            dados = {"paginas": PAG.reordenar(e[0], out, seq)}
        elif op == "reverse":
            dados = {"paginas": PAG.reordenar(e[0], out, list(range(n, 0, -1)))}
        elif op == "delete":
            dados = {"paginas": PAG.excluir(e[0], out, PAG.parse_paginas(paginas, n))}
        elif op == "interleave":
            if len(e) != 2:
                raise PapiroErro("E_ENTRADA", "interleave exige 2 arquivos: frentes;versos")
            dados = {"paginas": PAG.intercalar(e[0], e[1], out, versos_invertidos)}
        elif op == "rotate":
            dados = PAG.girar(e[0], out, PAG.parse_paginas(paginas, n) if paginas else [], angulo)
        elif op == "resize":
            dados = PAG.redimensionar(e[0], out, papel)
        elif op == "boxes":
            dados = PAG.caixas(e[0], out, json.loads(caixas_json or "{}"), PAG.parse_paginas(paginas, n) if paginas else None)
        elif op == "nup":
            dados = PAG.nup(e[0], out, por_folha, papel)
        elif op == "booklet":
            dados = PAG.livreto(e[0], out, papel)
        elif op == "labels":
            dados = PAG.rotulos(e[0], out, json.loads(rotulos_json or "[]"))
        elif op == "blank_remove":
            dados = PAG.remover_branco(e[0], out, limiar_tinta)
        else:
            raise PapiroErro("E_SEM_SUPORTE", f"pages.{op} (poster: usar nup/resize)")
        res = Resultado(outputs=[out], motor="pymupdf" if op in ("merge", "resize", "nup", "booklet") else "pikepdf",
                        dados=dados)
        return _com_qa(ctx, res, out, qa)
    return executar("pages", op, acao, entradas=lista, out_dir=out_dir, tarefa="paginas", dry_run=dry_run)


@mcp.tool()
def outline(op: str, entrada: str, out_dir: str, toc_json: str = "", dry_run: bool = False) -> dict:
    """RF-108 marcadores. op=get|set. toc_json=[[nivel, titulo, pagina], ...]."""
    def acao(ctx):
        if op == "get":
            with INS.abrir(ctx.entradas[0]) as d:
                toc = d.get_toc()
            return Resultado(outputs=[_json(ctx, "marcadores.json", toc)], motor="pymupdf", dados={"itens": len(toc)})
        if op == "set":
            toc = json.loads(toc_json or "[]")
            out = ctx.saida("marcadores.pdf")
            with INS.abrir(ctx.entradas[0]) as d:
                d.set_toc(toc)
                d.save(out, garbage=3, deflate=True)
            return Resultado(outputs=[out], motor="pymupdf", dados={"itens": len(toc)})
        raise PapiroErro("E_SEM_SUPORTE", f"outline.{op}")
    return executar("outline", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="paginas", dry_run=dry_run)


@mcp.tool()
def attachments(op: str, entrada: str, out_dir: str, anexo: str = "", descricao: str = "", dry_run: bool = False) -> dict:
    """RF-109. op=list|extract|add. Extracao com nome saneado e hash identico."""
    entradas = [entrada] + ([anexo] if anexo else [])

    def acao(ctx):
        import hashlib
        import fitz
        with fitz.open(ctx.entradas[0]) as doc:
            if op == "list":
                itens = [{**doc.embfile_info(n), "nome": n} for n in doc.embfile_names()]
                for it in itens:
                    it.pop("creationDate", None), it.pop("modDate", None)
                return Resultado(outputs=[_json(ctx, "anexos.json", itens)], motor="pymupdf", dados={"anexos": len(itens)})
            if op == "extract":
                outs, hashes = [], []
                for n in doc.embfile_names():
                    dados = doc.embfile_get(n)
                    p = ctx.saida(nome_seguro(doc.embfile_info(n).get("filename") or n, "anexo.bin"))
                    p.write_bytes(dados)
                    if hashlib.sha256(p.read_bytes()).hexdigest() != hashlib.sha256(dados).hexdigest():
                        raise PapiroErro("E_MOTOR", "hash do anexo extraido diverge")
                    outs.append(p)
                    hashes.append({"arquivo": p.name, "sha256": hashlib.sha256(dados).hexdigest()})
                return Resultado(outputs=outs, motor="pymupdf", dados={"extraidos": hashes})
            if op == "add":
                if len(ctx.entradas) < 2:
                    raise PapiroErro("E_ENTRADA", "informe o arquivo em 'anexo'")
                fonte = ctx.entradas[1]
                nome = nome_seguro(ctx.originais[1].name)
                doc.embfile_add(nome, fonte.read_bytes(), filename=nome, desc=descricao or nome)
                out = ctx.saida("com_anexo.pdf")
                doc.save(out, garbage=3, deflate=True)
                return Resultado(outputs=[out], motor="pymupdf", dados={"anexo": nome})
        raise PapiroErro("E_SEM_SUPORTE", f"attachments.{op}")
    return executar("attachments", op, acao, entradas=entradas, out_dir=out_dir, tarefa="paginas", dry_run=dry_run)


# ================= Edicao (6) =================
@mcp.tool()
def stamp(op: str, entrada: str, out_dir: str, texto: str = "", pagina: int = 1, x: float = 72, y: float = 72,
          tamanho: float = 14, ancora: str = "", imagem: str = "", qr: str = "", largura: float = 120,
          opacidade: float = 0.18, modelo: str = "Página {n} de {total}", bates_prefixo: str = "",
          saida: str = "", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-201/203/204/205. op=text|image|qr|watermark|header|footer|bates. Coordenadas em pt a partir do topo;
    ancora = texto de referencia (insere abaixo dele). watermark vai em camada OCG removivel."""
    entradas = [entrada] + ([imagem] if imagem and op == "image" else [])

    def acao(ctx):
        out = ctx.saida(saida or f"{op}.pdf")
        e = ctx.entradas[0]
        if op in ("text", "image", "qr"):
            dados = ED.carimbo(e, out, texto=texto if op == "text" else "", pagina=pagina, x=x, y=y, tamanho=tamanho,
                               ancora=ancora, imagem=ctx.entradas[1] if op == "image" else None,
                               qr=qr if op == "qr" else "", largura=largura)
        elif op == "watermark":
            dados = ED.marca_dagua(e, out, texto, opacidade=opacidade)
        elif op in ("header", "footer", "bates"):
            mod = modelo if op != "bates" else (modelo if "{bates}" in modelo else "{bates}")
            dados = ED.cabecalho_rodape(e, out, mod, "cabecalho" if op == "header" else "rodape",
                                        bates_prefixo=bates_prefixo)
        else:
            raise PapiroErro("E_SEM_SUPORTE", f"stamp.{op}")
        res = Resultado(outputs=[out], motor="pymupdf", dados=dados, warnings=list(dados.get("avisos", [])))
        return _com_qa(ctx, res, out, qa)
    return executar("stamp", op, acao, entradas=entradas, out_dir=out_dir, tarefa="edicao", dry_run=dry_run)


@mcp.tool()
def replace_text(entrada: str, out_dir: str, de: str, para: str, saida: str = "substituido.pdf", qa: bool = True,
                 dry_run: bool = False) -> dict:
    """RF-202: troca texto mantendo corpo, cor e posicao; avisa quando precisa trocar a fonte."""
    def acao(ctx):
        out = ctx.saida(saida)
        r = ED.substituir_texto(ctx.entradas[0], out, de, para)
        res = Resultado(outputs=[out], motor="pymupdf", dados={"trocas": r["trocas"]}, warnings=r["avisos"])
        return _com_qa(ctx, res, out, qa)
    return executar("replace_text", "replace", acao, entradas=[entrada], out_dir=out_dir, tarefa="edicao", dry_run=dry_run)


@mcp.tool()
def annotate(op: str, entrada: str, out_dir: str, texto: str = "", pagina: int = 1, x: float = 72, y: float = 72,
             busca: str = "", url: str = "", qa: bool = False, dry_run: bool = False) -> dict:
    """RF-206/207. op=highlight (busca) | note (x,y,texto) | link (busca -> url) | flatten.
    xfdf_export/xfdf_import de anotacoes: sem suporte nesta versao (formularios: forms export/import_xfdf)."""
    def acao(ctx):
        import fitz
        if op in ("xfdf_export", "xfdf_import"):
            raise PapiroErro("E_SEM_SUPORTE", "XFDF de anotacoes nao implementado; para campos use forms op=export/import_xfdf")
        out = ctx.saida(f"anotado_{op}.pdf")
        with INS.abrir(ctx.entradas[0]) as d:
            if not 1 <= pagina <= d.page_count:
                raise PapiroErro("E_ENTRADA", f"pagina {pagina} inexistente")
            page = d[pagina - 1]
            n = 0
            if op == "highlight":
                for q in page.search_for(busca, quads=True):
                    page.add_highlight_annot(q)
                    n += 1
            elif op == "note":
                page.add_text_annot((x, y), texto).update()
                n = 1
            elif op == "link":
                for r in page.search_for(busca):
                    page.insert_link({"kind": fitz.LINK_URI, "from": r, "uri": url})
                    n += 1
            elif op == "flatten":
                d.bake(annots=True, widgets=False)
                n = -1
            else:
                raise PapiroErro("E_SEM_SUPORTE", f"annotate.{op}")
            d.save(out, garbage=3, deflate=True)
        return _com_qa(ctx, Resultado(outputs=[out], motor="pymupdf", dados={"anotacoes": n}), out, qa)
    return executar("annotate", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="edicao", dry_run=dry_run)


@mcp.tool()
def layers(op: str, entrada: str, out_dir: str, camadas: str = "", dry_run: bool = False) -> dict:
    """RF-208. op=list | show | hide (estado padrao ao abrir). camadas = nomes separados por ';'."""
    def acao(ctx):
        with INS.abrir(ctx.entradas[0]) as d:
            ocgs = d.get_ocgs()
            if op == "list":
                itens = [{"xref": k, **v} for k, v in ocgs.items()]
                return Resultado(outputs=[_json(ctx, "camadas.json", itens)], motor="pymupdf", dados={"camadas": itens})
            if op in ("show", "hide"):
                alvo = set(_lista(camadas))
                xrefs = [k for k, v in ocgs.items() if v["name"] in alvo]
                if not xrefs:
                    raise PapiroErro("E_ENTRADA", "nenhuma camada com esses nomes")
                on = [k for k, v in ocgs.items() if (v["on"] and k not in xrefs) or (op == "show" and k in xrefs)]
                off = [k for k in ocgs if k not in on]
                d.set_layer(-1, on=on, off=off)
                out = ctx.saida("camadas.pdf")
                d.save(out, garbage=3, deflate=True)
                return Resultado(outputs=[out], motor="pymupdf", dados={"ligadas": on, "desligadas": off})
        raise PapiroErro("E_SEM_SUPORTE", f"layers.{op} (remocao de camada com conteudo: nao implementada)")
    return executar("layers", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="edicao", dry_run=dry_run)


@mcp.tool()
def images(op: str, entrada: str, out_dir: str, xref: int = 0, imagem: str = "", perfil: str = "email",
           qa: bool = True, dry_run: bool = False) -> dict:
    """RF-003/RF-209. op=list|extract|replace (xref + imagem)|recompress (perfil)|grayscale."""
    entradas = [entrada] + ([imagem] if imagem else [])

    def acao(ctx):
        import fitz
        e = ctx.entradas[0]
        if op == "list":
            lista = INS.imagens(e)
            return Resultado(outputs=[_json(ctx, "imagens.json", lista)], motor="pymupdf", dados={"imagens": len(lista)})
        if op == "extract":
            outs = []
            with INS.abrir(e) as d:
                vistos = set()
                for page in d:
                    for img in page.get_images(full=True):
                        if img[0] in vistos:
                            continue
                        vistos.add(img[0])
                        info = d.extract_image(img[0])
                        p = ctx.saida(f"img_p{page.number + 1}_x{img[0]}.{info['ext']}")
                        p.write_bytes(info["image"])
                        outs.append(p)
            return Resultado(outputs=outs, motor="pymupdf", dados={"extraidas": len(outs)})
        out = ctx.saida(f"imagens_{op}.pdf")
        if op == "replace":
            if len(ctx.entradas) < 2 or not xref:
                raise PapiroErro("E_ENTRADA", "replace exige xref e imagem")
            with INS.abrir(e) as d:
                pagina = next((p for p in d if any(i[0] == xref for i in p.get_images(full=True))), None)
                if pagina is None:
                    raise PapiroErro("E_ENTRADA", f"xref {xref} nao e imagem de nenhuma pagina")
                pagina.replace_image(xref, filename=str(ctx.entradas[1]))
                d.save(out, garbage=4, deflate=True)
            motor = "pymupdf"
        elif op == "recompress":
            r = PAG.otimizar(e, out, perfil)
            return _com_qa(ctx, Resultado(outputs=[out], motor=r["via"], dados=r, warnings=r["avisos"]), out, qa)
        elif op == "grayscale":
            from . import binfinder as BF
            gs = BF.ghostscript()
            if not gs:
                raise PapiroErro("E_SEM_SUPORTE", "Ghostscript ausente")
            BF.rodar([gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", "-sColorConversionStrategy=Gray",
                      "-dProcessColorModel=/DeviceGray", f"-sOutputFile={out}", str(e)], timeout=600)
            motor = "ghostscript"
        else:
            raise PapiroErro("E_SEM_SUPORTE", f"images.{op}")
        return _com_qa(ctx, Resultado(outputs=[out], motor=motor), out, qa)
    return executar("images", op, acao, entradas=entradas, out_dir=out_dir, tarefa="edicao", dry_run=dry_run)


@mcp.tool()
def metadata(entrada: str, out_dir: str, titulo: str = "", autor: str = "", assunto: str = "", palavras: str = "",
             idioma: str = "pt-BR", saida: str = "metadados.pdf", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-210: Info e XMP sincronizados + /Lang."""
    def acao(ctx):
        out = ctx.saida(saida)
        ED.metadados(ctx.entradas[0], out, titulo, autor, assunto, palavras, idioma)
        return _com_qa(ctx, Resultado(outputs=[out], motor="pikepdf"), out, qa)
    return executar("metadata", "set", acao, entradas=[entrada], out_dir=out_dir, tarefa="edicao", dry_run=dry_run)


# ================= Criacao (5) =================
@mcp.tool()
def compose(motor: str, out_dir: str, markdown: str = "", html: str = "", titulo: str = "", autor: str = "PAPIRO",
            idioma: str = "pt-BR", padroes: str = "", saida: str = "documento.pdf", design: bool = False,
            nota_visual: float | None = None, qa: bool = True, dry_run: bool = False) -> dict:
    """RF-301/302. motor=auto|typst|story (markdown) ou html (Chromium, tags e marcadores).
    padroes='a-2b,ua-1' exige Typst e valida no veraPDF."""
    lista_padroes = [p.strip() for p in padroes.split(",") if p.strip()]

    def acao(ctx):
        out = ctx.saida(saida)
        if motor == "html":
            r = CRE.html_para_pdf(html or markdown, out, titulo, autor, idioma)
        else:
            r = CRE.markdown_para_pdf(markdown, out, titulo, autor, idioma, motor, lista_padroes or None)
        res = Resultado(outputs=[out], motor=r["via"], fallback_from=r.get("fallback_from"), dados={"paginas": r["paginas"]})
        padrao = next((("PDF/" + p.upper()) for p in lista_padroes if p.lower().startswith(("a-", "ua-"))), None)
        return _com_qa(ctx, res, out, qa, eh_design=design, nota_visual=nota_visual, padrao=padrao)
    return executar("compose", motor, acao, out_dir=out_dir, tarefa="criacao_html" if motor == "html" else "criacao",
                    dry_run=dry_run)


@mcp.tool()
def office_to_pdf(entrada: str, out_dir: str, referencia: str = "", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-303: DOCX/XLSX/PPTX/ODT -> PDF (LibreOffice). referencia=PDF para conferir SSIM >= 0,95."""
    entradas = [entrada] + ([referencia] if referencia else [])

    def acao(ctx):
        from . import fidelidade as FID
        r = CRE.office_para_pdf(ctx.entradas[0], ctx.out_dir, ctx.work / "lo_perfil")
        out = r["saida"]
        res = Resultado(outputs=[out], motor="libreoffice")
        if referencia:
            fid = FID.comparar(ctx.entradas[1], out)
            res.dados = {"ssim_medio": fid["ssim_medio"], "ssim_pior_bloco": fid["ssim_pior_bloco"]}
            if fid["ssim_medio"] < 0.95:
                res.warnings.append(f"fidelidade abaixo de 0,95 (SSIM medio {fid['ssim_medio']})")
        return _com_qa(ctx, res, out, qa)
    return executar("office_to_pdf", "convert", acao, entradas=entradas, out_dir=out_dir, tarefa="office", dry_run=dry_run)


@mcp.tool()
def mail_merge(out_dir: str, markdown_tpl: str, dados_json: str = "", dados_arquivo: str = "",
               modo: str = "consolidado", campo_nome: str = "", titulo: str = "Mala direta", qa: bool = True,
               dry_run: bool = False) -> dict:
    """RF-304: modelo Markdown com {{campo}} + dados JSON/CSV/XLSX; modo=consolidado|um_por_registro."""
    def acao(ctx):
        registros = CRE.carregar_dados(ctx.entradas[0] if dados_arquivo else dados_json)
        r = CRE.mala_direta(markdown_tpl, registros, ctx.out_dir, modo, titulo, campo_nome=campo_nome)
        res = Resultado(outputs=list(r["saidas"]), motor=r["via"], dados={"registros": r["registros"], "arquivos": len(r["saidas"])})
        return _com_qa(ctx, res, r["saidas"][0], qa)
    return executar("mail_merge", modo, acao, entradas=[dados_arquivo] if dados_arquivo else [], out_dir=out_dir,
                    tarefa="mala_direta", dry_run=dry_run)


@mcp.tool()
def graphics(tipo: str, out_dir: str, conteudo: str, titulo: str = "", saida: str = "", qa: bool = True,
             dry_run: bool = False) -> dict:
    """RF-305/310/405. tipo=qr (conteudo = dado, decodificacao conferida) | diagram (conteudo = Graphviz DOT, vetorial).
    chart (Vega-Lite) sem suporte: vl-convert nao instalado."""
    def acao(ctx):
        if tipo == "qr":
            out = ctx.saida(saida or "qr.pdf")
            dados = CRE.qr_pdf(conteudo, out)
            motor = "segno"
        elif tipo == "diagram":
            out = ctx.saida(saida or "diagrama.pdf")
            dados = CRE.diagrama_dot(conteudo, out, titulo or "Diagrama")
            motor = "graphviz"
        else:
            raise PapiroErro("E_SEM_SUPORTE", f"graphics.{tipo}: use qr ou diagram (Graphviz DOT)")
        return _com_qa(ctx, Resultado(outputs=[out], motor=motor, dados=dados), out, qa)
    return executar("graphics", tipo, acao, out_dir=out_dir, tarefa="criacao", dry_run=dry_run)


@mcp.tool()
def capture(op: str, out_dir: str, imagens: str = "", url: str = "", retificar: bool = False,
            saida: str = "captura.pdf", titulo: str = "", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-308/309. op=images|photos (retificacao de perspectiva) usa imagens separadas por ';'; op=web usa url
    (acessa a rede: proibido em job sensivel; banners de cookies nao sao removidos)."""
    lista = _lista(imagens) if op in ("images", "photos") else []

    def acao(ctx):
        out = ctx.saida(saida)
        if op in ("images", "photos"):
            r = CRE.imagens_para_pdf(ctx.entradas, out, retificar=retificar or op == "photos")
            if titulo:
                tmp = out.with_suffix(".tmp.pdf")
                out.rename(tmp)
                ED.metadados(tmp, out, titulo=titulo, autor="PAPIRO", produtor="PAPIRO (img2pdf)")
                tmp.unlink()
            res = Resultado(outputs=[out], motor=r["via"], dados={"paginas": r["paginas"]}, warnings=r["avisos"])
        elif op == "web":
            if not url.startswith(("http://", "https://")):
                raise PapiroErro("E_ENTRADA", "url deve comecar com http:// ou https://")
            r = CRE.navegador_para_pdf(url, out, titulo)
            res = Resultado(outputs=[out], motor="chromium", dados=r,
                            warnings=["banners de cookies nao sao removidos automaticamente"])
        else:
            raise PapiroErro("E_SEM_SUPORTE", f"capture.{op}")
        return _com_qa(ctx, res, out, qa)
    return executar("capture", op, acao, entradas=lista, out_dir=out_dir, tarefa="criacao", dry_run=dry_run)


# ================= Conversao (1) =================
@mcp.tool()
def convert(entrada: str, out_dir: str, destino: str = "md", dpi: int = 150, dry_run: bool = False) -> dict:
    """Do PDF para: txt|md|json|png|svg|xlsx|csv. docx/epub/dxf sem suporte nesta versao."""
    def acao(ctx):
        e = ctx.entradas[0]
        stem = ctx.originais[0].stem
        if destino == "txt":
            out = ctx.saida(stem + ".txt"); CONV.para_texto(e, out); motor = "pymupdf"
        elif destino == "md":
            out = ctx.saida(stem + ".md"); motor = CONV.para_markdown(e, out)["via"]
        elif destino == "json":
            out = ctx.saida(stem + ".json"); CONV.para_json(e, out); motor = "pymupdf"
        elif destino in ("xlsx", "csv"):
            out = ctx.saida(f"{stem}.{destino}")
            r = CONV.tabelas(e, out)
            return Resultado(outputs=[out], motor="pdfplumber+pymupdf", dados=r)
        elif destino in ("png", "svg"):
            pasta = ctx.saida(destino)
            pasta.mkdir(parents=True, exist_ok=True)
            outs = CONV.para_png(e, pasta, dpi) if destino == "png" else CONV.para_svg(e, pasta)
            return Resultado(outputs=outs, motor="pypdfium2" if destino == "png" else "pymupdf")
        else:
            raise PapiroErro("E_SEM_SUPORTE", f"convert->{destino}")
        return Resultado(outputs=[out], motor=motor)
    return executar("convert", destino, acao, entradas=[entrada], out_dir=out_dir, tarefa="md_digital", dry_run=dry_run)


# ================= IA documental (6) =================
@mcp.tool()
def ocr(entrada: str, out_dir: str, idioma: str = "por", pdfa: bool = True, forcar: bool = False,
        saida: str = "ocr.pdf", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-601: OCR so nas paginas sem camada de texto (OCRmyPDF; fallback Tesseract direto)."""
    def acao(ctx):
        out = ctx.saida(saida)
        r = INTEL.ocr(ctx.entradas[0], out, idioma, pdfa, forcar)
        res = Resultado(outputs=[out], motor=r["via"], fallback_from=r.get("fallback_from"),
                        dados={"paginas_ocr": r["paginas_ocr"]}, warnings=list(r.get("avisos", [])) + ([r["aviso"]] if r.get("aviso") else []))
        return _com_qa(ctx, res, out, qa)
    return executar("ocr", idioma, acao, entradas=[entrada], out_dir=out_dir, tarefa="ocr", dry_run=dry_run)


@mcp.tool()
def parse(entrada: str, out_dir: str, formato: str = "md", dry_run: bool = False) -> dict:
    """RF-602 (digital): estrutura em Markdown (PyMuPDF4LLM) ou JSON de blocos. Docling/PaddleOCR-VL nao instalados."""
    return convert(entrada, out_dir, formato if formato in ("md", "json") else "md", dry_run=dry_run)


@mcp.tool()
def extract(op: str, entrada: str, out_dir: str, formato: str = "xlsx", dry_run: bool = False) -> dict:
    """RF-603/604/605. op=tables (xlsx|csv, conferencia entre 2 motores) | fields | entities (dados pessoais com pagina)."""
    def acao(ctx):
        e = ctx.entradas[0]
        if op == "tables":
            out = ctx.saida(f"tabelas.{formato if formato in ('xlsx', 'csv') else 'xlsx'}")
            return Resultado(outputs=[out], motor="pdfplumber+pymupdf", dados=CONV.tabelas(e, out))
        if op == "fields":
            d = CONV.listar_campos(e)
            return Resultado(outputs=[_json(ctx, "campos.json", d)], motor="pymupdf", dados={"campos": len(d)})
        if op == "entities":
            from .adapters import pii as PII
            d = PII.detectar_pdf(e)
            motor = "presidio+regex" if any(a["motor"].startswith("presidio") for a in d) else "regex-pii"
            return Resultado(outputs=[_json(ctx, "entidades.json", d)], motor=motor,
                             dados={"achados": len(d), "categorias": sorted({a["categoria"] for a in d})})
        raise PapiroErro("E_SEM_SUPORTE", f"extract.{op}")
    return executar("extract", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="tabela" if op == "tables" else "pii",
                    dry_run=dry_run)


@mcp.tool()
def rag(op: str, out_dir: str, doc_id: str = "", entrada: str = "", pergunta: str = "", evidencias: bool = True,
        limite: int = 5, dry_run: bool = False) -> dict:
    """RF-606. op=index (entrada + doc_id, base em kb/rag.db) | ask (pergunta; cita doc e pagina; PDF de evidencias).
    Busca lexical FTS5/BM25 (sem embeddings)."""
    def acao(ctx):
        if op == "index":
            if not doc_id:
                raise PapiroErro("E_ENTRADA", "doc_id obrigatorio")
            from . import sha256_file
            r = INTEL.rag_index(ctx.entradas[0], doc_id, sha256_file(ctx.originais[0]), str(ctx.originais[0]))
            return Resultado(motor="sqlite-fts5", dados=r)
        if op == "ask":
            resp = INTEL.rag_ask(pergunta, limite=limite)
            outs = [_json(ctx, "respostas.json", resp)]
            if evidencias and resp:
                ev = ctx.saida("evidencias.pdf")
                if INTEL.rag_evidencias(resp, ev):
                    outs.append(ev)
            return Resultado(outputs=outs, motor="sqlite-fts5", dados={"respostas": resp})
        raise PapiroErro("E_SEM_SUPORTE", f"rag.{op}")
    return executar("rag", op, acao, entradas=[entrada] if entrada else [], out_dir=out_dir, tarefa="rag", dry_run=dry_run)


@mcp.tool()
def translate(entrada: str, out_dir: str, idioma: str = "en", dry_run: bool = False) -> dict:
    """RF-608: sem suporte nesta versao (PDFMathTranslate/BabelDOC nao instalados)."""
    return _sem_suporte("translate", idioma, "traducao com layout exige PDFMathTranslate/BabelDOC + Ollama (nao instalados)",
                        out_dir, [entrada])


@mcp.tool()
def alt_text(entrada: str, out_dir: str, dry_run: bool = False) -> dict:
    """RF-609: sem suporte nesta versao (exige modelo de visao local)."""
    return _sem_suporte("alt_text", "gerar", "texto alternativo exige modelo de visao local (nao configurado)",
                        out_dir, [entrada])


# ================= Formularios (1) =================
@mcp.tool()
def forms(op: str, entrada: str, out_dir: str, dados_json: str = "{}", formato: str = "json", dados_arquivo: str = "",
          campo_nome: str = "", xfdf: str = "", qa: bool = False, dry_run: bool = False) -> dict:
    """RF-701..706. op=list|fill|fill_batch (dados_arquivo JSON/CSV/XLSX)|export (json|csv|fdf|xfdf)|import_xfdf|
    flatten (campos deixam de ser editaveis)|detect_xfa."""
    entradas = [entrada] + ([dados_arquivo] if dados_arquivo else []) + ([xfdf] if xfdf else [])

    def acao(ctx):
        e = ctx.entradas[0]
        if op == "list":
            d = CONV.listar_campos(e)
            return Resultado(outputs=[_json(ctx, "campos.json", d)], motor="pymupdf", dados={"campos": d[:100]})
        if op == "detect_xfa":
            return Resultado(motor="pikepdf", dados={"xfa": CONV.detectar_xfa(e)})
        if op == "export":
            out = ctx.saida(f"campos.{formato}")
            return Resultado(outputs=[out], motor="pymupdf", dados=CONV.exportar_campos(e, out))
        if op == "fill":
            out = ctx.saida("preenchido.pdf")
            r = CONV.preencher(e, out, json.loads(dados_json or "{}"))
            return _com_qa(ctx, Resultado(outputs=[out], motor="pymupdf", dados=r, warnings=r["avisos"]), out, qa)
        if op == "fill_batch":
            if not dados_arquivo:
                raise PapiroErro("E_ENTRADA", "fill_batch exige dados_arquivo")
            registros = CRE.carregar_dados(ctx.entradas[1])
            outs, avisos = [], []
            for i, reg in enumerate(registros, start=1):
                base = nome_seguro(str(reg.get(campo_nome, "")) if campo_nome else "", f"formulario-{i:05d}")
                out = ctx.saida(f"{base}.pdf")
                r = CONV.preencher(e, out, reg)
                avisos += r["avisos"][:1]
                outs.append(out)
            return Resultado(outputs=outs, motor="pymupdf", dados={"registros": len(outs)}, warnings=sorted(set(avisos)))
        if op == "import_xfdf":
            if not xfdf:
                raise PapiroErro("E_ENTRADA", "import_xfdf exige xfdf")
            out = ctx.saida("importado.pdf")
            r = CONV.importar_xfdf(e, out, ctx.entradas[-1])
            return Resultado(outputs=[out], motor="pymupdf", dados=r, warnings=r["avisos"])
        if op == "flatten":
            out = ctx.saida("achatado.pdf")
            r = CONV.achatar(e, out)
            return _com_qa(ctx, Resultado(outputs=[out], motor="pymupdf", dados=r), out, qa)
        raise PapiroErro("E_SEM_SUPORTE", f"forms.{op} (create/detect de campos: nao implementado)")
    return executar("forms", op, acao, entradas=entradas, out_dir=out_dir, tarefa="formulario", dry_run=dry_run)


# ================= Conformidade e grafica (5) =================
@mcp.tool()
def conform(op: str, entrada: str, out_dir: str, padrao: str = "PDF/A-2b", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-801. op=pdfa (Ghostscript + veraPDF, aprovado so sem falhas). pdfua/pdfx/remediate: sem suporte
    (para UA-1 gere nativo: compose padroes='ua-1')."""
    def acao(ctx):
        if op != "pdfa":
            raise PapiroErro("E_SEM_SUPORTE", f"conform.{op}: para PDF/UA-1 use compose com padroes='ua-1'")
        out = ctx.saida("pdfa.pdf")
        r = CONF.converter_pdfa(ctx.entradas[0], out, padrao)
        return _com_qa(ctx, Resultado(outputs=[out], motor="ghostscript+verapdf", dados=r), out, qa, padrao=r["padrao"])
    return executar("conform", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="pdfa", dry_run=dry_run)


@mcp.tool()
def validate(entrada: str, out_dir: str, padrao: str = "", dry_run: bool = False) -> dict:
    """Validacao independente: integridade (qpdf + pdfcpu) e, se padrao informado, veraPDF (A/UA) ou preflight (X)."""
    def acao(ctx):
        d = {"integridade": QA._g1(ctx.entradas[0])}
        if padrao:
            d["padrao"] = CONF.validar_padrao(ctx.entradas[0], padrao)
        ok = d["integridade"]["ok"] and d.get("padrao", {}).get("ok", True)
        res = Resultado(outputs=[_json(ctx, "validacao.json", d)], motor="qpdf+pdfcpu" + ("+verapdf" if padrao else ""),
                        dados={"valido": ok, **d})
        if not ok:
            res.qa = {"status": "REPROVADO", "bloqueantes": ["validacao"]}
        return res
    return executar("validate", padrao or "integridade", acao, entradas=[entrada], out_dir=out_dir, tarefa="pdfa",
                    dry_run=dry_run)


@mcp.tool()
def preflight(entrada: str, out_dir: str, padrao: str = "PDF/X-4", limite_tinta: float = 300.0,
              dry_run: bool = False) -> dict:
    """§11.4 preflight proprio: caixas, OutputIntent, cor, tinta, 300 DPI, fontes, transparencia, linhas, texto pequeno."""
    def acao(ctx):
        r = CONF.preflight_x(ctx.entradas[0], padrao, limite_tinta)
        res = Resultado(outputs=[_json(ctx, "preflight.json", r)], motor="preflight-papiro",
                        dados={"aprovado": r["aprovado"], "falhas": r["falhas"][:30]}, warnings=r["avisos"])
        if not r["aprovado"]:
            res.qa = {"status": "REPROVADO", "bloqueantes": sorted({f["regra"] for f in r["falhas"]})}
        return res
    return executar("preflight", padrao, acao, entradas=[entrada], out_dir=out_dir, tarefa="grafica", dry_run=dry_run)


@mcp.tool()
def color(op: str, entrada: str, out_dir: str, qa: bool = True, dry_run: bool = False) -> dict:
    """RF-407 parcial. op=gray|cmyk (Ghostscript; cmyk usa o perfil padrao do Ghostscript, nao FOGRA)."""
    def acao(ctx):
        from . import binfinder as BF
        if op not in ("gray", "cmyk"):
            raise PapiroErro("E_SEM_SUPORTE", f"color.{op}: perfis ICC personalizados nao implementados")
        gs = BF.ghostscript()
        if not gs:
            raise PapiroErro("E_SEM_SUPORTE", "Ghostscript ausente")
        out = ctx.saida(f"cor_{op}.pdf")
        estrategia, modelo = ("Gray", "/DeviceGray") if op == "gray" else ("CMYK", "/DeviceCMYK")
        BF.rodar([gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", f"-sColorConversionStrategy={estrategia}",
                  f"-dProcessColorModel={modelo}", f"-sOutputFile={out}", str(ctx.entradas[0])], timeout=600)
        res = Resultado(outputs=[out], motor="ghostscript",
                        warnings=["CMYK com perfil padrao do Ghostscript; para grafica informe o ICC (FOGRA39/51)"] if op == "cmyk" else [])
        return _com_qa(ctx, res, out, qa)
    return executar("color", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="grafica", dry_run=dry_run)


@mcp.tool()
def impose(op: str, entrada: str, out_dir: str, por_folha: int = 2, papel: str = "a4", qa: bool = False,
           dry_run: bool = False) -> dict:
    """RF-107. op=nup|booklet (livreto grampeado, ordem de dobra)."""
    return pages(op, out_dir, entrada=entrada, por_folha=por_folha, papel=papel, qa=qa, dry_run=dry_run)


# ================= Otimizacao e reparo (3) =================
@mcp.tool()
def optimize(entrada: str, out_dir: str, perfil: str = "email", meta_mb: float | None = None, linearizar: bool = False,
             saida: str = "otimizado.pdf", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-902/903: perfil=tela|email|impressao|arquivo. Entrega o menor candidato com texto identico e SSIM acima do limiar."""
    def acao(ctx):
        out = ctx.saida(saida)
        r = PAG.otimizar(ctx.entradas[0], out, perfil, meta_mb, linearizar)
        res = Resultado(outputs=[out], motor=r["via"], dados={k: v for k, v in r.items() if k != "avisos"},
                        warnings=r["avisos"])
        return _com_qa(ctx, res, out, qa, perfil_tamanho_mb=meta_mb)
    return executar("optimize", perfil, acao, entradas=[entrada], out_dir=out_dir, tarefa="otimizar", dry_run=dry_run)


@mcp.tool()
def repair(entrada: str, out_dir: str, saida: str = "reparado.pdf", qa: bool = True, dry_run: bool = False) -> dict:
    """RF-901: cascata qpdf -> pikepdf -> Ghostscript -> PyMuPDF -> renderizacao."""
    def acao(ctx):
        out = ctx.saida(saida)
        r = PAG.reparar_cascata(ctx.entradas[0], out)
        res = Resultado(outputs=[out], motor=r["via"], fallback_from=r.get("fallback_from"), dados=r)
        return _com_qa(ctx, res, out, qa)
    return executar("repair", "cascata", acao, entradas=[entrada], out_dir=out_dir, tarefa="reparo", dry_run=dry_run)


@mcp.tool()
def fonts(op: str, entrada: str, out_dir: str, qa: bool = True, dry_run: bool = False) -> dict:
    """RF-002/RF-904. op=list | embed (Ghostscript embute e subdivide; confere que nao sobrou fonte nao embutida)."""
    def acao(ctx):
        e = ctx.entradas[0]
        if op == "list":
            d = {"fontes": INS.fontes(e), "pdffonts": INS.fontes_pdffonts(e)}
            return Resultado(outputs=[_json(ctx, "fontes.json", d)], motor="pikepdf+pdffonts",
                             dados={"nao_embutidas": [f["nome"] for f in d["fontes"] if not f["embutida"]]})
        if op == "embed":
            out = ctx.saida("fontes_embutidas.pdf")
            r = PAG.embutir_fontes(e, out)
            restantes = [f["nome"] for f in INS.fontes(out) if not f["embutida"]]
            if restantes:
                raise PapiroErro("E_CONFORMIDADE", f"fontes ainda nao embutidas: {restantes}")
            return _com_qa(ctx, Resultado(outputs=[out], motor="ghostscript", dados=r), out, qa)
        raise PapiroErro("E_SEM_SUPORTE", f"fonts.{op}")
    return executar("fonts", op, acao, entradas=[entrada], out_dir=out_dir, tarefa="reparo", dry_run=dry_run)


# ================= Comparacao (1) =================
@mcp.tool()
def compare(a: str, b: str, out_dir: str, dpi: int = 100, dry_run: bool = False) -> dict:
    """RF-607: texto, estrutura e visual (SSIM), com PDF marcado nas regioes alteradas."""
    def acao(ctx):
        marcado = ctx.saida("comparacao_marcada.pdf")
        r = CMP.comparar(ctx.entradas[0], ctx.entradas[1], marcado, dpi)
        rel = _json(ctx, "comparacao.json", r)
        return Resultado(outputs=[rel, marcado], motor="difflib+opencv",
                         dados={"identicos": r["identicos"], "linhas_diff": r["texto"]["linhas_diff"],
                                "estrutura": r["estrutura"], "ssim_pior_bloco": r["visual"]["ssim_pior_bloco"],
                                "paginas_com_diferenca": r["marcas"]["paginas_com_diferenca"]})
    return executar("compare", "texto+visual+estrutura", acao, entradas=[a, b], out_dir=out_dir, tarefa="comparar",
                    dry_run=dry_run)


# ================= Operacao (4) =================
@mcp.tool()
def qa_run(entrada: str, out_dir: str, design: bool = False, nota_visual: float | None = None, padrao: str = "",
           referencia: str = "", meta_mb: float | None = None, brancas_permitidas: str = "",
           anexos_permitidos: bool = False, dry_run: bool = False) -> dict:
    """§11: portoes G1-G11 + qa-report.json/md. nota_visual = rubrica do pdf-revisor-qa (obrigatoria em design)."""
    entradas = [entrada] + ([referencia] if referencia else [])

    def acao(ctx):
        return _com_qa(ctx, Resultado(motor="qa"), ctx.entradas[0], True, eh_design=design, nota_visual=nota_visual,
                       padrao=padrao or None, exige_ssim_ref=ctx.entradas[1] if referencia else None,
                       perfil_tamanho_mb=meta_mb, anexos_permitidos=anexos_permitidos,
                       brancas_permitidas=[int(x) for x in brancas_permitidas.split(",") if x.strip()])
    return executar("qa_run", "G1-G11", acao, entradas=entradas, out_dir=out_dir, tarefa="qa", dry_run=dry_run)


@mcp.tool()
def jobs(op: str, job_id: str = "", pedido: str = "", limite: int = 20) -> dict:
    """op=status|list|cancel|stats|route (pedido -> tarefa e motores pontuados pelo historico)."""
    def acao(_ctx):
        if op == "status":
            return Resultado(motor="sqlite", dados=JOBS.job_status(job_id))
        if op == "list":
            return Resultado(motor="sqlite", dados=JOBS.jobs_listar(limite))
        if op == "cancel":
            return Resultado(motor="sqlite", dados=JOBS.job_cancelar(job_id))
        if op == "stats":
            return Resultado(motor="sqlite", dados=JOBS.stats_resumo())
        if op == "route":
            tarefa = ROT.classificar(pedido)
            return Resultado(motor="roteador", dados={"tarefa": tarefa, "motores": ROT.ranquear(tarefa, so_disponiveis=False)})
        raise PapiroErro("E_SEM_SUPORTE", f"jobs.{op}")
    return executar("jobs", op, acao, escreve=False)


RECEITA_SCHEMA = {
    "type": "object", "required": ["receita", "versao", "passos"],
    "properties": {
        "receita": {"type": "string", "minLength": 1}, "versao": {"type": "integer", "minimum": 1},
        "descricao": {"type": "string"}, "sensivel": {"type": "boolean"}, "entradas": {"type": "object"},
        "passos": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["id", "ferramenta"],
            "properties": {"id": {"type": "string"}, "ferramenta": {"type": "string"}, "com": {"type": "object"},
                           "exige": {"type": "object"}, "confirmacao": {"enum": ["obrigatoria", "opcional"]},
                           "se": {"type": "string"}, "para_cada": {"type": "string"}, "paralelo": {"type": "integer"}}}},
        "saida": {"type": "object"}}}


@mcp.tool()
def recipes(op: str, out_dir: str = "", arquivo: str = "") -> dict:
    """§9.3. op=list | validate (JSON Schema). run: sem suporte nesta versao (executor de receitas pendente)."""
    def acao(ctx):
        import jsonschema
        import yaml
        if op == "list":
            return Resultado(motor="papiro", dados={"receitas": sorted(p.name for p in RECIPES.glob("*.yaml"))})
        if op == "validate":
            if not ctx.entradas:
                raise PapiroErro("E_ENTRADA", "informe o arquivo da receita")
            rec = yaml.safe_load(ctx.entradas[0].read_text(encoding="utf-8"))
            if not isinstance(rec, dict):
                raise PapiroErro("E_ENTRADA", "receita deve ser um mapa YAML")
            erros = sorted(f"{'/'.join(map(str, e.path)) or '(raiz)'}: {e.message}"
                           for e in jsonschema.Draft202012Validator(RECEITA_SCHEMA).iter_errors(rec))
            ids = [p.get("id") for p in rec.get("passos", []) if isinstance(p, dict)]
            if len(ids) != len(set(ids)):
                erros.append("ids de passo repetidos")
            return Resultado(motor="jsonschema", dados={"valida": not erros, "erros": erros})
        raise PapiroErro("E_SEM_SUPORTE", f"recipes.{op}: executor de receitas ainda nao implementado")
    return executar("recipes", op, acao, entradas=[arquivo] if arquivo else [], out_dir=out_dir or None, escreve=False)


@mcp.tool()
def engines(op: str = "status") -> dict:
    """Motores instalados, versoes, idiomas do Tesseract e perfil de hardware."""
    def acao(_ctx):
        return Resultado(motor="papiro", dados=ENG.status())
    return executar("engines", op, acao, escreve=False)


# ================= Recursos e prompts §8.5 =================
@mcp.resource("papiro://engines")
def recurso_engines() -> str:
    return json.dumps(ENG.status(), ensure_ascii=False, indent=2)


@mcp.resource("papiro://jobs/{job_id}/report")
def recurso_relatorio(job_id: str) -> str:
    candidatos = sorted(OUT.glob("**/qa-report*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in candidatos:
        try:
            if json.loads(c.read_text(encoding="utf-8")).get("job_id") == job_id:
                return c.read_text(encoding="utf-8")
        except Exception:
            continue
    return json.dumps({"erro": "E_ENTRADA", "mensagem": f"relatorio do job {job_id} nao encontrado"})


@mcp.resource("papiro://brandkits")
def recurso_brandkits() -> str:
    return json.dumps(sorted(p.name for p in (REPO / "brandkits").glob("*")) if (REPO / "brandkits").exists() else [])


@mcp.resource("papiro://templates")
def recurso_templates() -> str:
    return json.dumps(sorted(p.name for p in (REPO / "templates").glob("*")) if (REPO / "templates").exists() else [])


@mcp.prompt(name="criar-documento")
def prompt_criar(tipo: str, conteudo: str) -> str:
    return (f"Crie um {tipo} em pt-BR com o PAPIRO: compose (typst), depois qa_run; se reprovar, corrija e repita "
            f"(no maximo 3 ciclos). Conteudo:\n{conteudo}")


@mcp.prompt(name="revisar-visual")
def prompt_revisar(arquivo: str) -> str:
    return (f"Revise {arquivo}: render_pages a 110 DPI, aplique a rubrica papiro-rubrica-visual (nota 0-10) e rode "
            "qa_run com design=true e nota_visual. Devolva APROVADO/REPROVADO com defeitos por pagina. Nao edite.")


@mcp.prompt(name="preparar-grafica")
def prompt_grafica(arquivo: str, padrao: str = "PDF/X-4") -> str:
    return f"Prepare {arquivo} para grafica: preflight ({padrao}), corrija as falhas e valide de novo antes de entregar."


@mcp.prompt(name="emitir-documento-medico")
def prompt_medico(tipo: str, dados_json: str) -> str:
    return (f"Emita {tipo} com os dados abaixo: compose com padroes='a-2b', qa_run ate APROVADO; a assinatura so via "
            f"pdf-seguranca com confirmacao explicita do Dr. Marcio. Dados sensiveis: sem rede.\n{dados_json}")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
