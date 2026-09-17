# -*- coding: utf-8 -*-
"""Executor unico das ferramentas (PRD §4.2 + §8.1).

Cada chamada: job-id unico -> valida caminhos -> (dry_run devolve o plano) -> copia as entradas
como somente leitura para work/<job>/in -> executa -> QA -> envelope + auditoria + estatistica do motor."""
from __future__ import annotations
import hashlib, inspect as _inspect, os, pathlib, shutil, stat, time
from dataclasses import dataclass, field
from typing import Any, Callable
from . import WORK, sha256_file
from . import audit as AUD, caminhos as CAM, config, engines as ENG, jobs as JOBS, roteador as ROT
from .erros import PapiroErro


@dataclass
class Resultado:
    outputs: list[pathlib.Path] = field(default_factory=list)
    motor: str = "n/a"
    fallback_from: str | None = None
    warnings: list[str] = field(default_factory=list)
    qa: dict | None = None
    qa_report: pathlib.Path | None = None
    dados: Any = None
    erro: PapiroErro | None = None  # operacao terminou com relatorio, mas sem sucesso (ex.: receita pausada)


@dataclass
class Contexto:
    job_id: str
    out_dir: pathlib.Path | None
    work: pathlib.Path
    entradas: list[pathlib.Path]
    originais: list[pathlib.Path]

    def saida(self, nome: str) -> pathlib.Path:
        if self.out_dir is None:
            raise PapiroErro("E_ENTRADA", "out_dir e obrigatorio para esta operacao")
        return CAM.saida_livre(self.out_dir, nome, self.originais)


def versao_motor(motor: str) -> str | None:
    partes = [p for p in motor.replace("+", " ").split() if p]
    vs = []
    for p in partes:
        base = {"pymupdf-story": "pymupdf", "regex-pii": None, "presidio": "presidio-analyzer",
                "opencv": "opencv-python-headless", "render": "pymupdf", "difflib": None}.get(p, p)
        v = ENG.versao(base) if base else None
        if v:
            vs.append(f"{p} {v}" if len(partes) > 1 else v)
    return " + ".join(vs) or None


def _limpar(pasta: pathlib.Path):
    def _on_err(func, path, _exc):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    if pasta.exists():
        shutil.rmtree(pasta, onerror=_on_err)


_CONTEUDO = {"markdown", "html", "dados_json", "markdown_tpl", "texto", "conteudo", "caixas_json", "externos_json",
             "toc_json", "rotulos_json", "caixas_json"}


def _argumentos_do_chamador(frame) -> dict:
    """Parametros da ferramenta que chamou executar (RF-908: salvar tarefa como receita).
    Segredos nunca; conteudo longo vira hash; em modo sensivel, caminhos tambem viram hash."""
    if frame is None:
        return {}
    info = _inspect.getargvalues(frame)
    sensivel = (WORK / "_sensivel.flag").exists() or os.environ.get("PAPIRO_SENSIVEL") == "1"
    args = {}
    for nome in info.args:
        if nome not in info.locals or "senha" in nome or "pin" in nome or nome in ("dry_run",):
            continue
        valor = info.locals[nome]
        if isinstance(valor, str) and (nome in _CONTEUDO or (sensivel and ("/" in valor or "\\" in valor))):
            args[nome] = {"omitido_sha256": hashlib.sha256(valor.encode("utf-8")).hexdigest(), "tamanho": len(valor)} if valor else ""
        elif isinstance(valor, (str, int, float, bool)) or valor is None:
            args[nome] = valor
    return args


def _classificar_excecao(e: Exception) -> PapiroErro:
    if isinstance(e, PapiroErro):
        return e
    nome = type(e).__name__
    try:
        import pikepdf
        if isinstance(e, pikepdf.PasswordError):
            return PapiroErro("E_SENHA")
        if isinstance(e, pikepdf.PdfError):
            return PapiroErro("E_CORROMPIDO", f"pikepdf: {nome}")
    except ImportError:  # pragma: no cover
        pass
    try:
        import fitz
        if isinstance(e, (fitz.FileDataError, fitz.EmptyFileError)):
            return PapiroErro("E_CORROMPIDO", f"pymupdf: {nome}")
    except (ImportError, AttributeError):  # pragma: no cover
        pass
    return PapiroErro("E_MOTOR", f"falha interna ({nome})")


def executar(ferramenta: str, op: str, fn: Callable[[Contexto], Resultado], *,
             entradas: list[str] | tuple = (), out_dir: str | None = None, tarefa: str | None = None,
             escreve: bool = True, dry_run: bool = False, copiar_entradas: bool = True) -> dict:
    t0 = time.time()
    argumentos = _argumentos_do_chamador(_inspect.currentframe().f_back)
    job_id = JOBS.novo_job_id()
    tarefa = tarefa or ferramenta
    res = Resultado()
    erro: PapiroErro | None = None
    descricoes: list[dict] = []
    work = WORK / job_id
    criado = False
    try:
        originais = [CAM.validar_entrada(e) for e in entradas]
        o = CAM.validar_out_dir(out_dir) if (escreve or out_dir) else None
        plano = {"ferramenta": ferramenta, "op": op, "tarefa": tarefa,
                 "entradas_sha256": [sha256_file(p) for p in originais],
                 "motores": ROT.ranquear(tarefa), "argumentos": argumentos}
        JOBS.job_criar(job_id, ferramenta, op, plano)
        criado = True
        if dry_run:
            JOBS.job_atualizar(job_id, "dry_run")
            res.dados = {"plano": plano, "estimativa_bytes_entrada": sum(p.stat().st_size for p in originais)}
            res.motor = (plano["motores"][0]["motor"] if plano["motores"] else "n/a")
        else:
            JOBS.job_atualizar(job_id, "executando")
            copias = []
            if copiar_entradas and originais:
                (work / "in").mkdir(parents=True, exist_ok=True)
                for i, p in enumerate(originais):
                    dst = work / "in" / f"{i:02d}_{CAM.nome_seguro(p.name)}"
                    shutil.copy2(p, dst)
                    os.chmod(dst, stat.S_IREAD)
                    copias.append(dst)
            ctx = Contexto(job_id, o, work, copias or originais, originais)
            res = fn(ctx) or Resultado()
            if res.erro is not None:
                erro = res.erro
            elif res.qa is not None and res.qa.get("status") != "APROVADO":
                erro = PapiroErro("E_CONFORMIDADE",
                                  f"QA {res.qa.get('status')}: {', '.join(res.qa.get('bloqueantes', []))}")
    except Exception as e:  # noqa: BLE001 - todo erro vira envelope
        erro = _classificar_excecao(e)
    finally:
        if not config.jobs("manter_work"):
            _limpar(work)
    for p in res.outputs:
        if p.exists():
            descricoes.append(AUD.descrever(p))
    segundos = time.time() - t0
    ok = erro is None
    if criado and not dry_run:
        JOBS.stat_motor(tarefa, res.motor, ok, segundos)
        JOBS.job_atualizar(job_id, "concluido" if ok else "falhou", erro=erro.codigo if erro else None,
                           motor=res.motor, segundos=round(segundos, 3), saidas=[d["path"] for d in descricoes])
    engine = {"name": res.motor, "version": versao_motor(res.motor), "fallback_from": res.fallback_from}
    qa_env = {}
    if res.qa is not None:
        qa_env = {"status": res.qa.get("status"), "bloqueantes": res.qa.get("bloqueantes", []),
                  "report": str(res.qa_report) if res.qa_report else None}
    audit_id = AUD.registrar({"job_id": job_id, "ferramenta": ferramenta, "op": op, "engine": engine,
                              "outputs": AUD.para_log(descricoes), "segundos": round(segundos, 3),
                              "status": "ok" if ok else "erro", "erro": erro.codigo if erro else None,
                              "qa": qa_env.get("status"), "dry_run": dry_run})
    env = {"ok": ok, "job_id": job_id, "outputs": descricoes, "engine": engine,
           "metrics": {"seconds": round(segundos, 3)}, "warnings": [w for w in res.warnings if w],
           "qa": qa_env, "audit_id": audit_id}
    if res.dados is not None:
        env["dados"] = res.dados
    if erro:
        env["error"] = erro.como_dict()
    return env
