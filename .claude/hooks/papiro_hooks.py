# -*- coding: utf-8 -*-
"""Os 9 hooks do PAPIRO (PRD §7.4) em Python - mesma funcao dos .ps1 do Windows, para Linux (e qualquer SO).

Uso: python papiro_hooks.py <doctor|contexto|guarda-originais|confirma-sensivel|soberania|valida-saida|
                             pede-revisao|salva-estado|portao-final>
Entrada: JSON do Claude Code no stdin. Bloqueio: JSON documentado (permissionDecision deny / decision block),
nunca por excecao - hook com erro nao pode travar a sessao."""
from __future__ import annotations
import datetime, hashlib, json, os, pathlib, re, shutil, sqlite3, subprocess, sys, time

REPO = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parents[2]).resolve()
DADOS = pathlib.Path(os.environ.get("PAPIRO_HOME") or REPO).expanduser().resolve()
WORK, OUT, LOGS = DADOS / "work", DADOS / "out", DADOS / "logs"
SENSIVEIS = {"sign", "certify", "timestamp", "ltv_update", "encrypt", "decrypt", "redact_apply", "sanitize"}


def _entrada() -> dict:
    try:
        bruto = sys.stdin.read()
        return json.loads(bruto) if bruto.strip() else {}
    except Exception:
        return {}


def _emitir(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))


def _negar(motivo: str) -> None:
    _emitir({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                    "permissionDecisionReason": motivo}})


def _contexto(evento: str, texto: str) -> None:
    _emitir({"hookSpecificOutput": {"hookEventName": evento, "additionalContext": texto}})


def _dentro(p: pathlib.Path, base: pathlib.Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


def _auditar(entrada: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    linha = {"audit_id": hashlib.sha1(os.urandom(8)).hexdigest()[:12],
             "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), **entrada}
    with open(LOGS / "audit.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def _sessao_arquivo(ev: dict) -> pathlib.Path:
    sid = re.sub(r"[^\w-]", "", str(ev.get("session_id") or "sem-sessao"))[:64]
    return LOGS / "sessoes" / f"{sid}.inicio"


# ---------------- SessionStart ----------------
def doctor(ev: dict) -> None:
    arq = _sessao_arquivo(ev)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(str(time.time()), encoding="utf-8")
    sys.path.insert(0, str(REPO / "core"))
    try:
        from papiro_core import binfinder as BF
        motores = {n: bool(BF.qual(n)) for n in ("typst", "qpdf", "pdfcpu", "tesseract", "soffice", "verapdf",
                                                  "pdffonts", "java")}
        motores["ghostscript"] = bool(BF.ghostscript())
    except Exception as e:  # noqa: BLE001
        motores = {"erro": f"papiro_core indisponivel ({type(e).__name__})"}
    livre = shutil.disk_usage(DADOS).free / 2**30
    perfil = "P1" if shutil.which("nvidia-smi") else "P0"
    ausentes = [n for n, ok in motores.items() if ok is False]
    _contexto("SessionStart", f"PAPIRO doctor: perfil {perfil}; disco livre {livre:.1f} GB; "
                              f"motores ausentes: {', '.join(ausentes) or 'nenhum'}; raiz de dados {DADOS}.")


# ---------------- UserPromptSubmit ----------------
def contexto(ev: dict) -> None:
    perfil = "P0"
    try:
        import tomllib
        with open(REPO / "papiro.toml", "rb") as f:
            perfil = tomllib.load(f).get("perfil", {}).get("ativo", "P0")
    except Exception:
        pass
    kits = sorted((REPO / "brandkits").glob("*/tokens.yaml")) if (REPO / "brandkits").exists() else []
    brandkit = kits[0].parent.name if kits else "padrao (nenhum brand kit em brandkits/)"
    sensivel = (WORK / "_sensivel.flag").exists() or os.environ.get("PAPIRO_SENSIVEL") == "1"
    _contexto("UserPromptSubmit", f"PAPIRO: perfil {perfil}; brand kit {brandkit}; job sensivel: "
                                  f"{'SIM (sem rede)' if sensivel else 'nao'}. Regras: pt-BR, um passo por vez; "
                                  "nunca sobrescrever entradas; escrita em work/ ou out/; entrega so com qa APROVADO.")


# ---------------- PreToolUse: guarda-originais ----------------
_BASH_PERIGOSO = [
    (re.compile(r"\b(mkfs|fdisk|parted|wipefs|shred)\b"), "comando de disco/particao"),
    (re.compile(r"\bdd\b[^|;&]*\bof=/dev/"), "dd gravando em dispositivo"),
    (re.compile(r">\s*/dev/sd[a-z]"), "gravacao direta em disco"),
    (re.compile(r"\bswapon\b"), "swap em disco e proibido nesta maquina"),
]


def _alvos_rm(cmd: str) -> list[str]:
    alvos = []
    for m in re.finditer(r"\brm\s+((?:-[a-zA-Z]*\s+)*)([^;&|]+)", cmd):
        flags = m.group(1)
        if "r" in flags.lower():
            alvos += [a for a in m.group(2).split() if not a.startswith("-")]
    return alvos


def guarda_originais(ev: dict) -> None:
    ferramenta = ev.get("tool_name", "")
    ti = ev.get("tool_input") or {}
    docs = REPO / "docs"
    if ferramenta in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        caminho = ti.get("file_path") or ti.get("notebook_path") or ""
        if not caminho:
            return
        p = pathlib.Path(caminho).expanduser().resolve()
        if _dentro(p, docs):
            return _negar("guarda-originais: docs/ guarda as fontes canonicas verbatim; nao se edita.")
        if _dentro(p, WORK) and "in" in p.relative_to(WORK).parts[1:2]:
            return _negar("guarda-originais: work/<job>/in contem as entradas isoladas somente leitura.")
        permitidos = [REPO, DADOS, pathlib.Path(f"/tmp/claude-{os.getuid()}") if hasattr(os, "getuid") else REPO,
                      pathlib.Path.home() / ".claude" / "projects"]
        if not any(_dentro(p, b.resolve()) for b in permitidos):
            return _negar(f"guarda-originais: escrita fora do projeto PAPIRO ({p}). Grave em work/ ou out/.")
        return
    if ferramenta == "Bash":
        cmd = ti.get("command", "")
        for rx, motivo in _BASH_PERIGOSO:
            if rx.search(cmd):
                return _negar(f"guarda-originais: {motivo}.")
        for alvo in _alvos_rm(cmd):
            alvo_p = pathlib.Path(os.path.expanduser(alvo.strip("'\""))).resolve()
            ok = any(_dentro(alvo_p, b) for b in (WORK, OUT, pathlib.Path(f"/tmp/claude-{os.getuid()}")))
            if not ok or _dentro(docs, alvo_p):
                return _negar(f"guarda-originais: exclusao recursiva so dentro de work/ ou out/ (alvo: {alvo}).")
        if re.search(r"(>|\btee\b|\bmv\b|\bcp\b)[^;&|]*\bdocs/", cmd):
            return _negar("guarda-originais: nao gravar sobre docs/ (fontes canonicas).")
        return
    if ferramenta.startswith("mcp__papiro"):
        out_dir = ti.get("out_dir")
        if out_dir:
            o = pathlib.Path(out_dir).expanduser().resolve()
            if not (_dentro(o, WORK) or _dentro(o, OUT)):
                return _negar("guarda-originais: out_dir deve ficar em work/ ou out/ do PAPIRO.")
            for chave in ("entrada", "a", "b"):
                if ti.get(chave) and pathlib.Path(ti[chave]).expanduser().resolve().parent == o:
                    _contexto("PreToolUse", "guarda-originais: entrada e saida na mesma pasta; o PAPIRO nunca "
                                            "sobrescreve, mas prefira uma pasta de job propria.")
                    return


# ---------------- PreToolUse: confirma-sensivel ----------------
def confirma_sensivel(ev: dict) -> None:
    ferramenta = ev.get("tool_name", "")
    op = ferramenta.rsplit("__", 1)[-1]
    confirmado = bool((ev.get("tool_input") or {}).get("confirm"))
    if op in SENSIVEIS:
        _auditar({"hook": "confirma-sensivel", "ferramenta": op, "confirmado": confirmado})
        if not confirmado:
            return _negar(f"confirma-sensivel: {op} exige confirmacao explicita do usuario (confirm=true).")


# ---------------- PreToolUse: soberania ----------------
def soberania(ev: dict) -> None:
    sensivel = (WORK / "_sensivel.flag").exists() or os.environ.get("PAPIRO_SENSIVEL") == "1"
    if not sensivel:
        return
    ferramenta = ev.get("tool_name", "")
    ti = ev.get("tool_input") or {}
    if ferramenta in ("WebFetch", "WebSearch"):
        return _negar("soberania: job sensivel - servicos on-line bloqueados.")
    if ferramenta == "Bash" and re.search(r"\b(curl|wget|ssh|scp|rsync|nc|ftp)\b|https?://|pip\s+install|npm\s+install",
                                          ti.get("command", "")):
        return _negar("soberania: job sensivel - comando com rede bloqueado.")
    if ferramenta.startswith("mcp__papiro") and ("http://" in json.dumps(ti) or "https://" in json.dumps(ti)):
        if ferramenta.endswith("__capture") or ferramenta.endswith("__compose"):
            return _negar("soberania: job sensivel - captura/composicao com recurso on-line bloqueada.")


# ---------------- PostToolUse: valida-saida ----------------
def _envelopes(obj) -> list[dict]:
    achados = []
    if isinstance(obj, dict):
        if "outputs" in obj and "job_id" in obj:
            achados.append(obj)
        for v in obj.values():
            achados += _envelopes(v)
    elif isinstance(obj, list):
        for v in obj:
            achados += _envelopes(v)
    elif isinstance(obj, str) and '"outputs"' in obj:
        try:
            achados += _envelopes(json.loads(obj))
        except Exception:
            pass
    return achados


def valida_saida(ev: dict) -> None:
    sys.path.insert(0, str(REPO / "core"))
    linhas = []
    for env in _envelopes(ev.get("tool_response")):
        for o in env.get("outputs", []):
            p = pathlib.Path(o.get("path", ""))
            if p.suffix.lower() != ".pdf" or not p.exists():
                continue
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            estado = "hash confere" if h == o.get("sha256") else "HASH DIVERGE do envelope"
            try:
                from papiro_core import binfinder as BF
                qpdf = BF.qual("qpdf")
                if qpdf:
                    r = subprocess.run([qpdf, "--check", str(p)], capture_output=True, timeout=120)
                    estado += "; qpdf --check " + ("ok" if r.returncode in (0, 3) else f"FALHOU ({r.returncode})")
                import fitz
                with fitz.open(p) as d:
                    mini = p.with_name(f"{p.stem}.miniatura.png")
                    if not mini.exists():
                        d[0].get_pixmap(dpi=30).save(mini)
            except Exception as e:  # noqa: BLE001
                estado += f"; validacao parcial ({type(e).__name__})"
            linhas.append(f"{p.name}: {estado}")
    if linhas:
        _contexto("PostToolUse", "valida-saida: " + " | ".join(linhas))


# ---------------- SubagentStop / PreCompact / Stop ----------------
def pede_revisao(ev: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "_revisao_pendente.flag").write_text(json.dumps({
        "agente": ev.get("agent_type"), "quando": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}),
        encoding="utf-8")
    _emitir({"systemMessage": f"pede-revisao: saida de {ev.get('agent_type') or 'subagente'} pendente de pdf-revisor-qa "
                              "(rubrica >= 8 antes de entregar)."})


def salva_estado(ev: dict) -> None:
    db = LOGS / "jobs.db"
    if not db.exists():
        return
    destino = LOGS / "jobs.precompact.db"
    with sqlite3.connect(db) as origem, sqlite3.connect(destino) as copia:
        origem.backup(copia)
        abertos = origem.execute("SELECT id, ferramenta, op, status, passo FROM jobs WHERE status IN "
                                 "('aberto','executando') ORDER BY criado DESC LIMIT 50").fetchall()
    (LOGS / "estado-precompact.json").write_text(json.dumps(
        [dict(zip(("job_id", "ferramenta", "op", "status", "passo"), r)) for r in abertos], ensure_ascii=False),
        encoding="utf-8")
    _emitir({"systemMessage": f"salva-estado: snapshot de jobs.db gravado ({len(abertos)} jobs abertos)."})


def portao_final(ev: dict) -> None:
    if ev.get("stop_hook_active"):
        return
    inicio_arq = _sessao_arquivo(ev)
    try:
        inicio = float(inicio_arq.read_text(encoding="utf-8"))
    except Exception:
        inicio = time.time() - 12 * 3600
    relatorios = [p for p in OUT.glob("**/qa-report*.json") if p.stat().st_mtime >= inicio] if OUT.exists() else []
    if not relatorios:
        return
    ultimo = max(relatorios, key=lambda p: p.stat().st_mtime)
    try:
        status = json.loads(ultimo.read_text(encoding="utf-8")).get("status")
    except Exception:
        status = "ilegivel"
    if status != "APROVADO":
        _emitir({"decision": "block", "reason": f"portao-final: o ultimo qa-report desta sessao ({ultimo.name}, job "
                                                f"{ultimo.parent.name}) esta {status}. Corrija e rode qa_run ate "
                                                "APROVADO (max 3 ciclos) ou explique ao usuario por que nao ha entrega."})


HOOKS = {"doctor": doctor, "contexto": contexto, "guarda-originais": guarda_originais,
         "confirma-sensivel": confirma_sensivel, "soberania": soberania, "valida-saida": valida_saida,
         "pede-revisao": pede_revisao, "salva-estado": salva_estado, "portao-final": portao_final}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in HOOKS:
        sys.stderr.write(f"uso: papiro_hooks.py <{'|'.join(HOOKS)}>\n")
        return 0
    ev = _entrada()
    try:
        HOOKS[argv[1]](ev)
    except Exception as e:  # noqa: BLE001 - hook nunca derruba a sessao
        sys.stderr.write(f"papiro hook {argv[1]}: {type(e).__name__}: {e}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
