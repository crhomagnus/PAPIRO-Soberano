# -*- coding: utf-8 -*-
"""Executor de receitas YAML (PRD §9.3).

- Validacao: JSON Schema + ids unicos + ferramentas existentes, antes de rodar.
- Checkpoints: cada passo grava estado em logs/jobs.db; `execucao=<id>` retoma do passo exato.
- Cache por hash: passo com a mesma ferramenta, argumentos e arquivos de entrada nao roda de novo.
- Assercoes: `exige` interrompe a receita quando falha.
- Controle de fluxo: `se`, `para_cada` e `paralelo: N` (processos separados via CLI).
- Confirmacao: `confirmacao: obrigatoria` pausa ate o id do passo vir em `confirmados`.
- Isolamento: passos `papiro-seguranca.*` nunca rodam aqui; a execucao pausa com a instrucao para o pdf-seguranca
  e retoma com o resultado informado em `externos`.
- `sensivel: true` liga work/_sensivel.flag (hook soberania) enquanto a execucao nao termina."""
from __future__ import annotations
import datetime, hashlib, inspect, json, os, pathlib, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import yaml
from . import OUT, WORK, sha256_file
from . import caminhos as CAM, jobs as JOBS
from .erros import PapiroErro

VERSAO_EXECUTOR = "1"

ESQUEMA = {
    "type": "object", "required": ["receita", "versao", "passos"], "additionalProperties": False,
    "properties": {
        "receita": {"type": "string", "pattern": r"^[a-z0-9][a-z0-9-]*$"}, "versao": {"type": "integer", "minimum": 1},
        "descricao": {"type": "string"}, "sensivel": {"type": "boolean"},
        "entradas": {"type": "object", "additionalProperties": {"type": "object", "properties": {
            "tipo": {"type": "string"}, "esquema": {"type": "string"}, "obrigatoria": {"type": "boolean"}}}},
        "passos": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["id", "ferramenta"], "additionalProperties": False,
            "properties": {"id": {"type": "string", "pattern": r"^[a-z0-9_-]+$"}, "ferramenta": {"type": "string"},
                           "com": {"type": "object"}, "exige": {"type": "object"},
                           "confirmacao": {"enum": ["obrigatoria", "opcional"]}, "se": {"type": "string"},
                           "para_cada": {"type": "string"}, "paralelo": {"type": "integer", "minimum": 1, "maximum": 8}}}},
        "saida": {"type": "object", "additionalProperties": False, "properties": {
            "pasta": {"type": "string"}, "nome": {"type": "string"}, "de": {"type": "string"}}}}}


# ---------------- carregamento e validacao ----------------
def ferramentas() -> dict:
    from . import mcp_server
    return {t.name: t.fn for t in mcp_server.mcp._tool_manager.list_tools()}


def validar(rec: dict) -> list[str]:
    import jsonschema
    if not isinstance(rec, dict):
        return ["receita deve ser um mapa YAML"]
    erros = sorted(f"{'/'.join(map(str, e.path)) or '(raiz)'}: {e.message}"
                   for e in jsonschema.Draft202012Validator(ESQUEMA).iter_errors(rec))
    if erros:
        return erros
    ids = [p["id"] for p in rec["passos"]]
    if len(ids) != len(set(ids)):
        erros.append("ids de passo repetidos")
    disponiveis = ferramentas()
    seguranca = {"sign", "certify", "timestamp", "ltv_update", "verify", "encrypt", "decrypt", "redact_detect",
                 "redact_apply", "sanitize"}
    for p in rec["passos"]:
        f = p["ferramenta"]
        if f.startswith("papiro-seguranca."):
            if f.split(".", 1)[1] not in seguranca:
                erros.append(f"passo {p['id']}: ferramenta de seguranca desconhecida: {f}")
            if p.get("para_cada"):
                erros.append(f"passo {p['id']}: para_cada nao e suportado em passo de seguranca")
        elif f not in disponiveis or f == "recipes":
            erros.append(f"passo {p['id']}: ferramenta desconhecida: {f}")
    return erros


def carregar(arquivo: pathlib.Path) -> tuple[dict, str]:
    texto = arquivo.read_text(encoding="utf-8")
    try:
        rec = yaml.safe_load(texto)
    except yaml.YAMLError as e:
        raise PapiroErro("E_ENTRADA", f"YAML invalido: {str(e).splitlines()[0]}")
    erros = validar(rec)
    if erros:
        raise PapiroErro("E_ENTRADA", "receita invalida: " + " | ".join(erros[:8]))
    return rec, hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _validar_entradas(rec: dict, dados: dict) -> None:
    import jsonschema
    from . import REPO
    for nome, spec in (rec.get("entradas") or {}).items():
        if nome != "dados":
            continue
        if spec.get("obrigatoria", True) and not dados:
            raise PapiroErro("E_ENTRADA", "a receita exige a entrada 'dados'")
        esquema = spec.get("esquema")
        if esquema and dados:
            arq = (REPO / esquema).resolve()
            if not arq.is_file() or not arq.is_relative_to(REPO.resolve()):
                raise PapiroErro("E_ENTRADA", f"esquema da entrada nao encontrado: {esquema}")
            erros = list(jsonschema.Draft202012Validator(json.loads(arq.read_text(encoding="utf-8"))).iter_errors(dados))
            if erros:
                raise PapiroErro("E_ENTRADA", "dados nao atendem ao esquema da receita: " +
                                 " | ".join(f"{'/'.join(map(str, e.path)) or '(raiz)'}: {e.message}" for e in erros[:6]))


# ---------------- referencias, condicoes e assercoes ----------------
_REF = re.compile(r"^\$([A-Za-z_][\w-]*(?:\.[\w-]+)*)$")


def _resolver_ref(caminho: str, contexto: dict):
    partes = caminho.split(".")
    raiz = partes[0]
    if raiz in ("dados", "item", "execucao", "data", "indice"):
        atual = contexto.get(raiz)
    elif raiz in contexto["passos"]:
        atual = contexto["passos"][raiz]
    else:
        raise PapiroErro("E_ENTRADA", f"referencia desconhecida: ${caminho}")
    for p in partes[1:]:
        if isinstance(atual, dict) and p in atual:
            atual = atual[p]
        elif isinstance(atual, list) and p.isdigit() and int(p) < len(atual):
            atual = atual[int(p)]
        else:
            raise PapiroErro("E_ENTRADA", f"referencia sem valor: ${caminho}")
    return atual


def resolver(valor, contexto: dict):
    if isinstance(valor, str):
        m = _REF.match(valor.strip())
        return _resolver_ref(m.group(1), contexto) if m else valor
    if isinstance(valor, list):
        return [resolver(v, contexto) for v in valor]
    if isinstance(valor, dict):
        return {k: resolver(v, contexto) for k, v in valor.items()}
    return valor


def _literal(txt: str):
    t = txt.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"":
        return t[1:-1]
    if t in ("true", "false"):
        return t == "true"
    if t == "null":
        return None
    try:
        return int(t) if re.fullmatch(r"-?\d+", t) else float(t)
    except ValueError:
        return t


def avaliar_condicao(expr: str, contexto: dict) -> bool:
    """`$ref`, `not $ref`, `$ref == literal`, `$ref != literal` (sem eval)."""
    m = re.fullmatch(r"\s*(not\s+)?\$([\w.-]+)\s*(?:(==|!=)\s*(.+?))?\s*", expr or "")
    if not m:
        raise PapiroErro("E_ENTRADA", f"condicao invalida: {expr!r}")
    try:
        valor = _resolver_ref(m.group(2), contexto)
    except PapiroErro:
        valor = None
    if m.group(3):
        igual = valor == _literal(m.group(4))
        resultado = igual if m.group(3) == "==" else not igual
    else:
        resultado = bool(valor)
    return not resultado if m.group(1) else resultado


def _valor_resultado(chave: str, env: dict):
    if chave == "ok":
        return env.get("ok")
    if chave == "qa":
        return (env.get("qa") or {}).get("status")
    if chave == "erro":
        return (env.get("error") or {}).get("code")
    if chave == "paginas":
        pdfs = [o for o in env.get("outputs", []) if o["path"].lower().endswith(".pdf")]
        return pdfs[0]["pages"] if pdfs else None
    if chave == "verapdf":
        padroes = (env.get("dados") or {}).get("padroes") if isinstance(env.get("dados"), dict) else None
        padroes = padroes if isinstance(padroes, dict) else {}   # validate devolve {padrao: resultado}; compose, uma lista
        avaliados = {k: v for k, v in padroes.items() if not k.lower().replace(" ", "").startswith(("pdf/x", "x"))}
        if avaliados:
            return "aprovado" if all(v.get("ok") for v in avaliados.values()) else "reprovado"
        qa = (env.get("qa") or {}).get("status")
        return "aprovado" if qa == "APROVADO" else ("reprovado" if qa else None)
    atual = env
    for p in chave.split("."):
        atual = atual.get(p) if isinstance(atual, dict) else None
    return atual


def _comparar(valor, esperado) -> bool:
    if isinstance(esperado, str):
        m = re.fullmatch(r"\s*(>=|<=|>|<|!=)\s*(-?\d+(?:\.\d+)?)\s*", esperado)
        if m:
            if not isinstance(valor, (int, float)):
                return False
            n = float(m.group(2))
            return {">=": valor >= n, "<=": valor <= n, ">": valor > n, "<": valor < n, "!=": valor != n}[m.group(1)]
        return isinstance(valor, str) and valor.lower() == esperado.lower()
    return valor == esperado


def checar_exige(exige: dict, env: dict) -> list[str]:
    falhas = []
    for chave, esperado in (exige or {}).items():
        valor = _valor_resultado(chave, env)
        if not _comparar(valor, esperado):
            falhas.append(f"{chave}: esperado {esperado!r}, obtido {valor!r}")
    return falhas


# ---------------- apelidos do vocabulario do PRD ----------------
def _normalizar_args(ferramenta: str, args: dict, estado: dict, avisos: list[str]) -> dict:
    a = dict(args)
    if "padroes_pdf" in a:
        lista = a.pop("padroes_pdf")
        a["padroes"] = ",".join(lista) if isinstance(lista, list) else str(lista)
        estado["padroes"] = [p.strip() for p in a["padroes"].split(",") if p.strip()]
    elif ferramenta == "compose" and a.get("padroes"):
        estado["padroes"] = [p.strip() for p in str(a["padroes"]).split(",") if p.strip()]
    if "dados" in a and ferramenta in ("compose", "forms", "mail_merge"):
        valor = a.pop("dados")
        a["dados_json"] = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    if ferramenta == "validate" and "validadores" in a:
        validadores = [str(v).lower() for v in a.pop("validadores")]
        if "verapdf" in validadores and "padrao" not in a:
            a["padrao"] = ",".join("PDF/" + p.upper() for p in estado.get("padroes", []) if p.lower().startswith(("a-", "ua-")))
            if not a["padrao"]:
                avisos.append("validadores inclui verapdf, mas nenhum padrao PDF/A ou PDF/UA foi declarado antes")
    if isinstance(a.get("entradas"), list):
        a["entradas"] = ";".join(str(x) for x in a["entradas"] if str(x).lower().endswith(".pdf") and "qa-report" not in str(x))
    for k, v in list(a.items()):
        if k.endswith("_json") and not isinstance(v, str):
            a[k] = json.dumps(v, ensure_ascii=False)
    if ferramenta == "qa_run":
        if "rubrica" in a:
            avisos.append(f"rubrica '{a.pop('rubrica')}' e aplicada pelo pdf-revisor-qa; qa_run roda os portoes automaticos")
        if "padrao" not in a and estado.get("padroes"):
            a["padrao"] = ",".join("PDF/" + p.upper() for p in estado["padroes"] if p.lower().startswith(("a-", "ua-")))
    return a


def _completar_args(nome: str, fn, args: dict, estado: dict, pasta: pathlib.Path) -> dict:
    parametros = inspect.signature(fn).parameters
    a = dict(args)
    if "out_dir" in parametros and "out_dir" not in a:
        a["out_dir"] = str(pasta)
    if "entrada" in parametros and "entrada" not in a and parametros["entrada"].default is inspect.Parameter.empty:
        if not estado.get("ultima_saida"):
            raise PapiroErro("E_ENTRADA", f"ferramenta {nome} precisa de 'entrada' e nenhum passo anterior gerou PDF")
        a["entrada"] = estado["ultima_saida"]
    aceita_extras = any(spec.kind is inspect.Parameter.VAR_KEYWORD for spec in parametros.values())
    desconhecidos = [] if aceita_extras else sorted(set(a) - set(parametros))
    if desconhecidos:
        raise PapiroErro("E_ENTRADA", f"{nome} nao aceita: {', '.join(desconhecidos)} (aceita: {', '.join(parametros)})")
    faltando = [p for p, spec in parametros.items() if spec.default is inspect.Parameter.empty and p not in a
                and spec.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)]
    if faltando:
        raise PapiroErro("E_ENTRADA", f"{nome} exige: {', '.join(faltando)}")
    return a


def _chave_cache(ferramenta: str, args: dict) -> str:
    base = {}
    for k, v in sorted(args.items()):
        if k in ("out_dir", "dry_run", "saida"):
            continue
        if isinstance(v, str) and v and os.path.isfile(v):
            base[k] = {"arquivo_sha256": sha256_file(pathlib.Path(v))}
        else:
            base[k] = v
    return hashlib.sha256(json.dumps({"v": VERSAO_EXECUTOR, "f": ferramenta, "a": base}, sort_keys=True,
                                     ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _saidas_validas(saida: dict) -> bool:
    for s in saida.get("saidas", []):
        p = pathlib.Path(s["path"])
        if not p.is_file() or sha256_file(p) != s["sha256"]:
            return False
    return bool(saida.get("saidas")) or saida.get("resultado", {}).get("ok", False)


def _chamar(nome: str, fn, args: dict, subprocesso: bool) -> dict:
    if not subprocesso:
        return fn(**args)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    r = subprocess.run([sys.executable, "-m", "papiro_core.cli", "chamar", nome, json.dumps(args, ensure_ascii=False)],
                       capture_output=True, text=True, timeout=3600, env=env)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "outputs": [], "error": {"code": "E_MOTOR", "message": f"subprocesso sem envelope ({r.returncode})"}}


def _resumo_env(env: dict, guardar_dados: bool) -> dict:
    saidas = [{"path": o["path"], "sha256": o["sha256"], "pages": o.get("pages", 0)} for o in env.get("outputs", [])]
    resultado = {"ok": env.get("ok"), "qa": (env.get("qa") or {}).get("status"), "erro": (env.get("error") or {}).get("code"),
                 "mensagem": (env.get("error") or {}).get("message"), "job_id": env.get("job_id"),
                 "verapdf": _valor_resultado("verapdf", env)}
    return {"saidas": saidas, "resultado": resultado, "dados": env.get("dados") if guardar_dados else None}


def _primeiro_pdf(saidas: list[dict]) -> str | None:
    return next((s["path"] for s in saidas if s["path"].lower().endswith(".pdf") and "qa-report" not in s["path"]), None)


# ---------------- execucao ----------------
def executar(rec: dict, receita_sha: str, dados: dict | None = None, out_base: pathlib.Path | None = None,
             execucao: str | None = None, confirmados: list[str] | tuple = (), externos: dict | None = None,
             dry_run: bool = False) -> dict:
    t0 = time.time()
    dados = dados or {}
    _validar_entradas(rec, dados)
    dados_sha = hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    sensivel = bool(rec.get("sensivel"))
    retomada = False
    if execucao:
        anterior = JOBS.execucao_ler(execucao)
        if anterior is None:
            raise PapiroErro("E_ENTRADA", f"execucao {execucao} nao existe")
        if anterior["receita_sha"] != receita_sha or anterior["dados_sha"] != dados_sha:
            raise PapiroErro("E_ENTRADA", "receita ou dados diferentes dos da execucao original: nao e possivel retomar")
        if anterior["status"] in ("concluido", "cancelado"):
            raise PapiroErro("E_ENTRADA", f"execucao {execucao} ja foi {anterior['status']}")
        retomada = True
    else:
        execucao = "rec-" + JOBS.novo_job_id()
    hoje = datetime.date.today().isoformat()
    out_base = (out_base or (OUT / hoje)) / f"receita-{execucao}"
    ferr = ferramentas()
    contexto = {"dados": dados, "execucao": execucao, "data": hoje, "passos": {}}
    estado = {"ultima_saida": None, "padroes": []}
    relatorio = {"execucao": execucao, "receita": rec["receita"], "versao": rec["versao"], "retomada": retomada,
                 "status": "executando", "passos": [], "saida_final": None, "pendente": None, "avisos": []}
    confirmados = {c.strip() for c in confirmados if c and c.strip()}
    externos = externos or {}

    if dry_run:
        for p in rec["passos"]:
            relatorio["passos"].append({"id": p["id"], "ferramenta": p["ferramenta"], "status": "planejado",
                                        "confirmacao": p.get("confirmacao"), "se": p.get("se"), "para_cada": p.get("para_cada")})
        relatorio["status"] = "planejado"
        return relatorio

    flag = WORK / "_sensivel.flag"
    if sensivel:
        WORK.mkdir(parents=True, exist_ok=True)
        flag.write_text(execucao, encoding="utf-8")
    JOBS.execucao_salvar(execucao, rec["receita"], receita_sha, dados_sha, "executando", None, sensivel)

    def registrar(passo_id, status, saida, chave=""):
        JOBS.passo_salvar(execucao, passo_id, status, chave, saida)

    def concluir_contexto(passo_id, saida):
        pdf = _primeiro_pdf(saida.get("saidas", []))
        contexto["passos"][passo_id] = {"saida": pdf, "saidas": [s["path"] for s in saida.get("saidas", [])],
                                        "dados": saida.get("dados"), **saida.get("resultado", {})}
        if pdf:
            estado["ultima_saida"] = pdf

    status_final = "concluido"
    try:
        for p in rec["passos"]:
            pid, nome = p["id"], p["ferramenta"]
            item_rel = {"id": pid, "ferramenta": nome}
            relatorio["passos"].append(item_rel)
            anterior = JOBS.passo_ler(execucao, pid) if retomada else None
            if anterior and anterior["status"] in ("ok", "cache", "externo", "pulado") and \
                    (anterior["status"] == "pulado" or _saidas_validas(anterior["saida"])):
                item_rel["status"] = f"retomado ({anterior['status']})"
                if anterior["status"] != "pulado":
                    concluir_contexto(pid, anterior["saida"])
                    if nome == "compose":
                        estado["padroes"] = anterior["saida"].get("padroes", estado["padroes"])
                continue
            if p.get("se") and not avaliar_condicao(p["se"], contexto):
                item_rel["status"] = "pulado"
                registrar(pid, "pulado", {})
                continue
            if p.get("confirmacao") == "obrigatoria" and pid not in confirmados:
                item_rel["status"] = "aguardando_confirmacao"
                relatorio["pendente"] = {"tipo": "confirmacao", "passo": pid, "ferramenta": nome,
                                         "como_retomar": {"execucao": execucao, "confirmados": sorted(confirmados | {pid})}}
                status_final = "aguardando_confirmacao"
                break
            args = resolver(p.get("com") or {}, contexto)

            if nome.startswith("papiro-seguranca."):
                if pid in externos:
                    ext = externos[pid]
                    caminho = ext.get("saida") if isinstance(ext, dict) else ext
                    caminho = caminho or next((o["path"] for o in (ext.get("outputs") or [])), None) if isinstance(ext, dict) else caminho
                    arq = CAM.validar_entrada(str(caminho))
                    saida = {"saidas": [{"path": str(arq), "sha256": sha256_file(arq), "pages": 0}],
                             "resultado": {"ok": True, "externo": True}, "dados": None}
                    registrar(pid, "externo", saida)
                    concluir_contexto(pid, saida)
                    item_rel.update(status="externo", saidas=[str(arq)])
                    continue
                sugeridos = {k: v for k, v in args.items() if k not in ("certificado", "perfil", "carimbo_tempo")}
                if estado["ultima_saida"]:
                    sugeridos.setdefault("entrada", estado["ultima_saida"])
                sugeridos.setdefault("out_dir", str(out_base / pid))
                if nome.endswith((".sign", ".certify", ".encrypt", ".decrypt", ".redact_apply", ".sanitize")):
                    sugeridos["confirm"] = True
                observacoes = []
                if str(args.get("certificado", "")).lower() == "a3":
                    observacoes.append("A3/PKCS#11 ainda sem suporte: use certificado A1 (pfx + senha_ref)")
                item_rel["status"] = "aguardando_seguranca"
                relatorio["pendente"] = {
                    "tipo": "seguranca", "passo": pid, "subagente": "pdf-seguranca",
                    "ferramenta": "mcp__papiro-seguranca__" + nome.split(".", 1)[1], "argumentos_sugeridos": sugeridos,
                    "observacoes": observacoes,
                    "como_retomar": {"execucao": execucao, "confirmados": sorted(confirmados),
                                     "externos_json": {pid: {"saida": "<caminho do arquivo gerado pelo pdf-seguranca>"}}}}
                status_final = "aguardando_seguranca"
                break

            fn = ferr[nome]
            avisos: list[str] = []
            if p.get("para_cada"):
                itens = resolver(p["para_cada"], contexto)
                if not isinstance(itens, list):
                    raise PapiroErro("E_ENTRADA", f"passo {pid}: para_cada deve resultar em lista")
                n_paralelo = int(p.get("paralelo", 1))
                chamadas = []
                for i, item in enumerate(itens):
                    ctx_item = {**contexto, "item": item, "indice": i}
                    a = _normalizar_args(nome, resolver(p.get("com") or {}, ctx_item), estado, avisos)
                    chamadas.append(_completar_args(nome, fn, a, estado, out_base / pid / f"{i:04d}"))
                with ThreadPoolExecutor(max_workers=n_paralelo) as pool:
                    envs = list(pool.map(lambda a: _chamar(nome, fn, a, n_paralelo > 1), chamadas))
                resumos = [_resumo_env(e, not sensivel) for e in envs]
                saida = {"saidas": [s for r in resumos for s in r["saidas"]],
                         "resultado": {"ok": all(e.get("ok") for e in envs), "itens": len(envs),
                                       "falhas": [i for i, e in enumerate(envs) if not e.get("ok")]},
                         "dados": [r["dados"] for r in resumos] if not sensivel else None}
                item_rel.update(itens=len(envs), paralelo=n_paralelo, job_ids=[e.get("job_id") for e in envs])
                falhas_exige = [f"item {i}: {f}" for i, e in enumerate(envs) for f in checar_exige(p.get("exige"), e)]
                if not saida["resultado"]["ok"] and not p.get("exige"):
                    primeiro = next(e for e in envs if not e.get("ok"))
                    falhas_exige.append(f"item {envs.index(primeiro)}: {(primeiro.get('error') or {}).get('message')}")
                    relatorio["erro"] = primeiro.get("error")
            else:
                a = _completar_args(nome, fn, _normalizar_args(nome, args, estado, avisos), estado, out_base / pid)
                chave = _chave_cache(nome, a)
                cache = JOBS.cache_buscar(chave)
                if cache and _saidas_validas(cache):
                    registrar(pid, "cache", cache, chave)
                    concluir_contexto(pid, cache)
                    item_rel.update(status="cache", saidas=[s["path"] for s in cache.get("saidas", [])])
                    relatorio["avisos"] += avisos
                    continue
                env = _chamar(nome, fn, a, False)
                saida = _resumo_env(env, not sensivel)
                if nome == "compose":
                    saida["padroes"] = estado.get("padroes", [])
                item_rel.update(job_id=env.get("job_id"), ok=env.get("ok"))
                falhas_exige = checar_exige(p.get("exige"), env)
                if not env.get("ok") and not p.get("exige"):
                    falhas_exige.append(f"{(env.get('error') or {}).get('code')}: {(env.get('error') or {}).get('message')}")
                    relatorio["erro"] = env.get("error")
            relatorio["avisos"] += avisos
            item_rel["saidas"] = [s["path"] for s in saida["saidas"]]
            if falhas_exige:
                ok_ferramenta = saida["resultado"].get("ok")
                item_rel.update(status="reprovado" if (p.get("exige") or ok_ferramenta) else "falhou", falhas=falhas_exige)
                registrar(pid, item_rel["status"], saida)
                status_final = item_rel["status"]
                break
            chave_ok = "" if p.get("para_cada") else chave
            registrar(pid, "ok", saida, chave_ok)
            concluir_contexto(pid, saida)
            item_rel["status"] = "ok"

        if status_final == "concluido" and rec.get("saida"):
            relatorio["saida_final"] = _copiar_saida_final(rec["saida"], contexto, estado, dados, execucao, rec["receita"])
    except PapiroErro as e:
        status_final = "falhou"
        relatorio["erro"] = e.como_dict()
        if relatorio["passos"]:
            relatorio["passos"][-1].setdefault("status", "falhou")
    finally:
        passo_atual = relatorio["pendente"]["passo"] if relatorio["pendente"] else None
        JOBS.execucao_salvar(execucao, rec["receita"], receita_sha, dados_sha, status_final, passo_atual, sensivel)
        if sensivel and status_final not in ("aguardando_confirmacao", "aguardando_seguranca") and flag.exists() \
                and flag.read_text(encoding="utf-8").strip() == execucao:
            flag.unlink()
    relatorio["status"] = status_final
    relatorio["segundos"] = round(time.time() - t0, 3)
    out_base.mkdir(parents=True, exist_ok=True)
    rel = CAM.saida_livre(out_base, "execucao.json")
    rel.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    relatorio["relatorio"] = str(rel)
    return relatorio


def _copiar_saida_final(spec: dict, contexto: dict, estado: dict, dados: dict, execucao: str, receita: str) -> str | None:
    origem = contexto["passos"].get(spec["de"], {}).get("saida") if spec.get("de") else estado.get("ultima_saida")
    if not origem:
        return None
    pseudo = str(dados.get("id_pseudonimo") or hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()[:10])
    trocas = {"data": contexto["data"], "execucao": execucao, "receita": receita, "id_pseudonimo": pseudo}

    def formatar(txt: str) -> str:
        return re.sub(r"\{(\w+)\}", lambda m: trocas.get(m.group(1), m.group(0)), txt)
    from . import ROOT
    pasta_rel = formatar(spec.get("pasta", f"out/{contexto['data']}"))
    pasta = CAM.validar_out_dir(str((ROOT / pasta_rel) if not os.path.isabs(pasta_rel) else pasta_rel))
    destino = CAM.saida_livre(pasta, CAM.nome_seguro(formatar(spec.get("nome", pathlib.Path(origem).name)), "saida.pdf"))
    shutil.copyfile(origem, destino)
    return str(destino)


# ---------------- RF-908: tarefa concluida vira receita ----------------
def receita_de_jobs(job_ids: list[str], nome: str) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", nome or ""):
        raise PapiroErro("E_ENTRADA", "nome da receita: minusculas, numeros e hifens")
    passos, entradas, saidas_por_passo = [], {}, {}
    for n, jid in enumerate(job_ids, start=1):
        job = JOBS.job_status(jid)
        if not job["existe"]:
            raise PapiroErro("E_ENTRADA", f"job {jid} nao existe")
        if job["status"] != "concluido":
            raise PapiroErro("E_ENTRADA", f"job {jid} nao esta concluido ({job['status']})")
        if job["ferramenta"] == "recipes":
            raise PapiroErro("E_ENTRADA", "jobs de receita nao podem virar passo de receita")
        args = dict(job["plano"].get("argumentos") or {})
        args.pop("out_dir", None)
        for k, v in list(args.items()):
            if isinstance(v, dict) and "omitido_sha256" in v:
                args[k] = f"${'dados' if k == 'dados_json' else 'dados.' + k}"
                entradas["dados"] = {"tipo": "json"}
            elif isinstance(v, str):
                for pid_ant, saidas in saidas_por_passo.items():
                    if v in saidas:
                        args[k] = f"${pid_ant}.saida"
        pid = f"p{n}-{job['ferramenta']}".replace("_", "-")
        passos.append({"id": pid, "ferramenta": job["ferramenta"], "com": args})
        saidas_por_passo[pid] = job.get("saidas") or []
    rec = {"receita": nome, "versao": 1, "descricao": f"Gerada dos jobs {', '.join(job_ids)}", "passos": passos}
    if entradas:
        rec["entradas"] = entradas
    erros = validar(rec)
    if erros:
        raise PapiroErro("E_ENTRADA", "receita gerada invalida: " + " | ".join(erros[:5]))
    return rec


def cancelar(execucao: str) -> dict:
    """Encerra uma execucao pausada: nao roda mais nada e desliga a trava de job sensivel dela."""
    st = JOBS.execucao_ler(execucao)
    if st is None:
        raise PapiroErro("E_ENTRADA", f"execucao {execucao} nao existe")
    if st["status"] in ("concluido", "cancelado"):
        return st
    JOBS.execucao_salvar(execucao, st["receita"], st["receita_sha"], st["dados_sha"], "cancelado", st["passo"], st["sensivel"])
    flag = WORK / "_sensivel.flag"
    if flag.exists() and flag.read_text(encoding="utf-8").strip() == execucao:
        flag.unlink()
    return JOBS.execucao_ler(execucao)
