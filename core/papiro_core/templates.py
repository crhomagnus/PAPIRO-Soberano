# -*- coding: utf-8 -*-
"""Biblioteca de templates RF-307 (Typst) com brand kit (RF-401).

templates/<categoria>/<nome>/{template.typ, meta.toml, schema.json, exemplo.json}; base comum em templates/_base.
Cada render monta um projeto Typst isolado (template, base, tokens, dados.json, imagens) e compila com as fontes
de fonts/. Fonte desconhecida no Typst so gera aviso e cai em fallback silencioso: aqui isso e erro (REGRA 01)."""
from __future__ import annotations
import copy, datetime, json, pathlib, re, shutil, tempfile, tomllib
import fitz, pikepdf
from . import REPO, binfinder as BF, config, engines as ENG
from .erros import PapiroErro

TEMPLATES = REPO / "templates"
BRANDKITS = REPO / "brandkits"
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro")


# ---------------- catalogo ----------------
def listar() -> list[dict]:
    itens = []
    for meta in sorted(TEMPLATES.glob("*/*/meta.toml")):
        m = tomllib.loads(meta.read_text(encoding="utf-8"))
        itens.append({"id": meta.parent.relative_to(TEMPLATES).as_posix(), **m})
    return itens


def resolver(template_id: str) -> pathlib.Path:
    """Aceita o id completo ('medico/receituario-a5') ou um prefixo unico do nome ('receituario')."""
    tid = (template_id or "").strip().strip("/")
    if not tid or ".." in tid:
        raise PapiroErro("E_ENTRADA", "template invalido")
    direto = TEMPLATES / tid
    if (direto / "meta.toml").exists():
        return direto
    candidatos = [p.parent for p in TEMPLATES.glob("*/*/meta.toml") if p.parent.name.startswith(tid.split("/")[-1])]
    if len(candidatos) == 1:
        return candidatos[0]
    nomes = sorted(i["id"] for i in listar())
    if not candidatos:
        raise PapiroErro("E_ENTRADA", f"template '{tid}' nao existe. Disponiveis: {', '.join(nomes)}")
    raise PapiroErro("E_ENTRADA", f"template '{tid}' ambiguo: {', '.join(sorted(c.relative_to(TEMPLATES).as_posix() for c in candidatos))}")


def meta(template_id: str) -> dict:
    d = resolver(template_id)
    return {"id": d.relative_to(TEMPLATES).as_posix(), "pasta": d, **tomllib.loads((d / "meta.toml").read_text(encoding="utf-8"))}


def exemplo(template_id: str) -> dict:
    return json.loads((resolver(template_id) / "exemplo.json").read_text(encoding="utf-8"))


def validar(template_id: str, dados: dict) -> None:
    import jsonschema
    schema = json.loads((resolver(template_id) / "schema.json").read_text(encoding="utf-8"))
    erros = sorted(jsonschema.Draft202012Validator(schema).iter_errors(dados), key=lambda e: list(e.path))
    if erros:
        msgs = [f"{'/'.join(map(str, e.path)) or '(raiz)'}: {e.message}" for e in erros[:8]]
        raise PapiroErro("E_ENTRADA", "dados nao atendem ao template: " + " | ".join(msgs))


# ---------------- numeros por extenso (pt-BR) ----------------
_UNI = ("zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze", "treze",
        "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove")
_DEZ = ("", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa")
_CEM = ("", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos",
        "novecentos")
FEMININOS = {"caixa", "caixas", "ampola", "ampolas", "cápsula", "cápsulas", "capsula", "capsulas", "gota", "gotas",
             "drágea", "drágeas", "dragea", "drageas", "unidade", "unidades", "bisnaga", "bisnagas", "seringa", "seringas",
             "cartela", "cartelas", "bolsa", "bolsas", "lata", "latas", "pomada", "pomadas", "dose", "doses", "semana",
             "semanas", "hora", "horas"}


def _fem(palavra: str, feminino: bool) -> str:
    if not feminino:
        return palavra
    return {"um": "uma", "dois": "duas"}.get(palavra, palavra.replace("entos", "entas"))


def _ate_mil(n: int, feminino: bool) -> str:
    if n == 100:
        return "cem"
    partes = []
    c, r = divmod(n, 100)
    if c:
        partes.append(_fem(_CEM[c], feminino))
    if r:
        if r < 20:
            partes.append(_fem(_UNI[r], feminino))
        else:
            d, u = divmod(r, 10)
            partes.append(_DEZ[d] + (" e " + _fem(_UNI[u], feminino) if u else ""))
    return " e ".join(partes)


def por_extenso(n: int, feminino: bool = False) -> str:
    """0 a 999.999, com concordancia de genero (duas caixas, duzentas unidades)."""
    if not isinstance(n, int) or n < 0 or n > 999_999:
        raise PapiroErro("E_ENTRADA", f"numero fora do intervalo por extenso: {n}")
    if n == 0:
        return "zero"
    mil, resto = divmod(n, 1000)
    partes = []
    if mil:
        partes.append("mil" if mil == 1 else _ate_mil(mil, feminino) + " mil")
    if resto:
        partes.append(_ate_mil(resto, feminino))
    if len(partes) == 2 and (resto < 100 or resto % 100 == 0):
        return partes[0] + " e " + partes[1]
    return " ".join(partes)


def data_extenso(d: datetime.date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


# ---------------- preparacao dos dados ----------------
def _copiar_imagem(caminho: str, destino: pathlib.Path) -> str:
    from .caminhos import nome_seguro, validar_entrada
    origem = validar_entrada(caminho)
    if origem.suffix.lower() not in (".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"):
        raise PapiroErro("E_ENTRADA", f"imagem com formato nao suportado: {origem.suffix}")
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / f"{len(list(destino.iterdir())):03d}_{nome_seguro(origem.name)}"
    shutil.copyfile(origem, alvo)
    return f"assets/{alvo.name}"


def preparar(template_id: str, dados: dict, projeto: pathlib.Path, logos_marca: dict | None = None) -> dict:
    d = copy.deepcopy(dados)
    hoje = datetime.date.today()
    d["_hoje"] = hoje.strftime("%d/%m/%Y")
    d["_hoje_extenso"] = data_extenso(hoje)
    assets = projeto / "assets"

    def percorrer(no):
        if isinstance(no, dict):
            if isinstance(no.get("logo"), str):
                no["_logo"] = _copiar_imagem(no["logo"], assets)
            if isinstance(no.get("imagem"), str):
                no["imagem"] = _copiar_imagem(no["imagem"], assets)
            if isinstance(no.get("quantidade"), int) and not isinstance(no.get("quantidade"), bool):
                unidade = str(no.get("unidade", "")).strip().lower()
                no["quantidade_extenso"] = por_extenso(no["quantidade"], unidade in FEMININOS)
            for v in list(no.values()):
                percorrer(v)
        elif isinstance(no, list):
            for v in no:
                percorrer(v)
    percorrer(d)
    if isinstance(d.get("dias"), int):
        d["dias_extenso"] = por_extenso(d["dias"])
    url = d.get("url_qr") or d.get("url_verificacao")
    if url:
        import segno
        assets.mkdir(parents=True, exist_ok=True)
        segno.make(url, error="m").save(assets / "qr.png", scale=10, border=2)
        d["_qr"] = "assets/qr.png"
    if logos_marca and "_logo" not in d and logos_marca.get("principal"):
        d["_logo"] = logos_marca["principal"]
    return d


def _campo(dados: dict, caminho: str):
    atual = dados
    for parte in caminho.split("."):
        if isinstance(atual, list) and parte.isdigit() and int(parte) < len(atual):
            atual = atual[int(parte)]
        elif isinstance(atual, dict) and parte in atual:
            atual = atual[parte]
        else:
            return None
    return atual


def titulo_documento(m: dict, dados: dict) -> str:
    return re.sub(r"\{([\w.]+)\}", lambda x: str(_campo(dados, x.group(1)) or ""), m["titulo"]).strip() or m["nome"]


# ---------------- renderizacao ----------------
def _tokens(marca: str, projeto: pathlib.Path) -> dict:
    pasta = BRANDKITS / (marca or "padrao")
    arq = pasta / "tokens.yaml"
    if not arq.exists():
        raise PapiroErro("E_ENTRADA", f"brand kit '{marca}' nao existe em brandkits/")
    shutil.copyfile(arq, projeto / "tokens.yaml")
    import yaml
    tokens = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
    logos = {}
    for chave, rel in (tokens.get("logos") or {}).items():
        origem = (pasta / rel).resolve()
        if origem.is_file() and origem.is_relative_to(pasta.resolve()):
            (projeto / "assets").mkdir(exist_ok=True)
            shutil.copyfile(origem, projeto / "assets" / f"marca_{chave}{origem.suffix}")
            logos[chave] = f"assets/marca_{chave}{origem.suffix}"
    return logos


def renderizar(template_id: str, dados: dict, out: pathlib.Path, marca: str = "padrao",
               padroes: list[str] | None = None, idioma: str = "pt-BR") -> dict:
    m = meta(template_id)
    validar(m["id"], dados)
    padroes = list(m.get("padroes", [])) if padroes is None else padroes
    exe = BF.qual("typst")
    if not exe:
        raise PapiroErro("E_SEM_SUPORTE", "Typst ausente: templates RF-307 exigem Typst")
    from . import FONTS
    from .adapters.edit import metadados
    with tempfile.TemporaryDirectory() as t:
        proj = pathlib.Path(t)
        shutil.copyfile(m["pasta"] / "template.typ", proj / "template.typ")
        shutil.copyfile(TEMPLATES / "_base" / "base.typ", proj / "base.typ")
        logos = _tokens(marca, proj)
        pronto = preparar(m["id"], dados, proj, logos)
        (proj / "dados.json").write_text(json.dumps(pronto, ensure_ascii=False), encoding="utf-8")
        titulo = titulo_documento(m, dados)
        autor = str(_campo(dados, m.get("autor_campo", "")) or "PAPIRO")
        lang, _, region = idioma.lower().partition("-")
        esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
        (proj / "main.typ").write_text(
            '#import "template.typ": documento\n'
            f'#set document(title: "{esc(titulo)}", author: "{esc(autor)}")\n'
            f'#set text(lang: "{lang}"' + (f', region: "{region}"' if region else "") + ")\n"
            '#show: documento.with(dados: json("dados.json"), tokens: yaml("tokens.yaml"))\n', encoding="utf-8")
        bruto = proj / "saida.pdf"
        cmd = [exe, "compile", "--root", str(proj), "--font-path", str(FONTS), "--ignore-system-fonts"]
        if padroes:
            cmd += ["--pdf-standard", ",".join(padroes)]
        r = BF.rodar(cmd + [str(proj / "main.typ"), str(bruto)], timeout=config.jobs("timeout_motor_s"), checar=False)
        saida_erro = r.stderr.decode("utf-8", "replace")
        if r.returncode != 0:
            primeira = next((ln for ln in saida_erro.splitlines() if ln.startswith("error")), saida_erro.strip()[:200])
            raise PapiroErro("E_MOTOR", f"typst ({m['id']}): {primeira[:300]}")
        fontes_ausentes = sorted(set(re.findall(r"unknown font family: ([^\n]+)", saida_erro)))
        if fontes_ausentes:
            raise PapiroErro("E_ENTRADA", f"fonte(s) do brand kit nao instalada(s) em fonts/: {', '.join(fontes_ausentes)}")
        produtor = f"PAPIRO (typst {ENG.versao('typst')}, template {m['id']})"
        if padroes:
            with pikepdf.open(bruto) as pdf:
                with pdf.open_metadata(set_pikepdf_as_editor=False) as xmp:
                    xmp["pdf:Producer"] = produtor
                pdf.docinfo["/Producer"] = produtor
                pdf.save(out)
        else:
            metadados(bruto, out, titulo=titulo, autor=autor, idioma=idioma, produtor=produtor)
    with fitz.open(out) as doc:
        paginas = doc.page_count
    return {"via": "typst", "template": m["id"], "paginas": paginas, "padroes": padroes, "design": bool(m.get("design")),
            "titulo": titulo, "marca": marca}
