# -*- coding: utf-8 -*-
"""Estado de jobs, contador de job-id, estatistica por motor e checkpoints de receita (ADR-04, SQLite)."""
from __future__ import annotations
import datetime, json, sqlite3
from contextlib import contextmanager
from . import LOGS, utcnow_iso

DB = LOGS / "jobs.db"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, ferramenta TEXT, op TEXT, status TEXT, passo INT,
    plano TEXT, criado TEXT, atualizado TEXT, erro TEXT, motor TEXT, segundos REAL);
CREATE TABLE IF NOT EXISTS contador(dia TEXT PRIMARY KEY, seq INT);
CREATE TABLE IF NOT EXISTS motor_stats(tarefa TEXT, motor TEXT, ok INT, total INT, segundos REAL,
    PRIMARY KEY(tarefa, motor));
CREATE TABLE IF NOT EXISTS receita_passos(execucao TEXT, passo TEXT, status TEXT, cache_key TEXT,
    saida TEXT, atualizado TEXT, PRIMARY KEY(execucao, passo));
CREATE TABLE IF NOT EXISTS receita_execucoes(execucao TEXT PRIMARY KEY, receita TEXT, receita_sha TEXT, dados_sha TEXT,
    status TEXT, passo TEXT, sensivel INT, criado TEXT, atualizado TEXT);
"""


@contextmanager
def _con():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    try:
        c.executescript(_ESQUEMA)
        colunas = {r[1] for r in c.execute("PRAGMA table_info(jobs)")}
        if "saidas" not in colunas:
            c.execute("ALTER TABLE jobs ADD COLUMN saidas TEXT")
        yield c
    finally:
        c.close()


def novo_job_id() -> str:
    """Id unico AAAA-MM-DD-NNNN, atomico entre processos (BEGIN IMMEDIATE)."""
    dia = datetime.date.today().isoformat()
    with _con() as c:
        c.execute("BEGIN IMMEDIATE")
        r = c.execute("SELECT seq FROM contador WHERE dia=?", (dia,)).fetchone()
        seq = (r[0] if r else 0) + 1
        c.execute("INSERT OR REPLACE INTO contador VALUES(?,?)", (dia, seq))
        c.execute("COMMIT")
    return f"{dia}-{seq:04d}"


def job_criar(job_id: str, ferramenta: str, op: str, plano: dict):
    agora = utcnow_iso()
    with _con() as c:
        c.execute("INSERT OR REPLACE INTO jobs(id, ferramenta, op, status, passo, plano, criado, atualizado, erro, motor, "
                  "segundos, saidas) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (job_id, ferramenta, op, "aberto", 0, json.dumps(plano, ensure_ascii=False), agora, agora,
                   None, None, None, None))


def job_atualizar(job_id: str, status: str, passo: int | None = None, erro: str | None = None,
                  motor: str | None = None, segundos: float | None = None, saidas: list[str] | None = None):
    with _con() as c:
        c.execute("""UPDATE jobs SET status=?, passo=COALESCE(?, passo), erro=?, motor=COALESCE(?, motor),
                     segundos=COALESCE(?, segundos), saidas=COALESCE(?, saidas), atualizado=? WHERE id=?""",
                  (status, passo, erro, motor, segundos, json.dumps(saidas, ensure_ascii=False) if saidas is not None else None,
                   utcnow_iso(), job_id))


def job_status(job_id: str) -> dict:
    with _con() as c:
        r = c.execute("SELECT ferramenta, op, status, passo, plano, criado, atualizado, erro, motor, segundos, saidas "
                      "FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not r:
        return {"existe": False, "job_id": job_id}
    return {"existe": True, "job_id": job_id, "ferramenta": r[0], "op": r[1], "status": r[2], "passo": r[3],
            "plano": json.loads(r[4] or "{}"), "criado": r[5], "atualizado": r[6], "erro": r[7],
            "motor": r[8], "segundos": r[9], "saidas": json.loads(r[10]) if r[10] else []}


def jobs_listar(limite: int = 20, status: str | None = None) -> list[dict]:
    q = "SELECT id FROM jobs" + (" WHERE status=?" if status else "") + " ORDER BY criado DESC, id DESC LIMIT ?"
    args = ((status,) if status else ()) + (limite,)
    with _con() as c:
        ids = [r[0] for r in c.execute(q, args).fetchall()]
    return [job_status(i) for i in ids]


def job_cancelar(job_id: str) -> dict:
    st = job_status(job_id)
    if st["existe"] and st["status"] in ("aberto", "executando"):
        job_atualizar(job_id, "cancelado")
        st = job_status(job_id)
    return st


# ---------- aprendizado continuo §9.4 ----------
def stat_motor(tarefa: str, motor: str, ok: bool, segundos: float = 0.0):
    with _con() as c:
        c.execute("BEGIN IMMEDIATE")
        r = c.execute("SELECT ok, total, segundos FROM motor_stats WHERE tarefa=? AND motor=?", (tarefa, motor)).fetchone()
        if r:
            c.execute("UPDATE motor_stats SET ok=?, total=?, segundos=? WHERE tarefa=? AND motor=?",
                      (r[0] + int(ok), r[1] + 1, (r[2] or 0) + segundos, tarefa, motor))
        else:
            c.execute("INSERT INTO motor_stats VALUES(?,?,?,?,?)", (tarefa, motor, int(ok), 1, segundos))
        c.execute("COMMIT")


def taxa_motor(tarefa: str, motor: str) -> float:
    """Taxa de sucesso suavizada: sem historico = 0,8; converge para a taxa real com o uso."""
    with _con() as c:
        r = c.execute("SELECT ok, total FROM motor_stats WHERE tarefa=? AND motor=?", (tarefa, motor)).fetchone()
    ok, total = (r if r else (0, 0))
    return (ok + 4) / (total + 5)


def stats_resumo() -> list[dict]:
    with _con() as c:
        rows = c.execute("SELECT tarefa, motor, ok, total, segundos FROM motor_stats ORDER BY tarefa, motor").fetchall()
    return [{"tarefa": t, "motor": m, "ok": o, "total": n, "taxa": round(o / n, 3) if n else None,
             "segundos_medio": round((s or 0) / n, 3) if n else None} for t, m, o, n, s in rows]


# ---------- checkpoints do executor de receitas §9.3 ----------
def passo_salvar(execucao: str, passo: str, status: str, cache_key: str, saida: dict):
    with _con() as c:
        c.execute("INSERT OR REPLACE INTO receita_passos VALUES(?,?,?,?,?,?)",
                  (execucao, passo, status, cache_key, json.dumps(saida, ensure_ascii=False), utcnow_iso()))


def passo_ler(execucao: str, passo: str) -> dict | None:
    with _con() as c:
        r = c.execute("SELECT status, cache_key, saida FROM receita_passos WHERE execucao=? AND passo=?",
                      (execucao, passo)).fetchone()
    return {"status": r[0], "cache_key": r[1], "saida": json.loads(r[2])} if r else None


def cache_buscar(cache_key: str) -> dict | None:
    with _con() as c:
        r = c.execute("SELECT saida FROM receita_passos WHERE cache_key=? AND status='ok' "
                      "ORDER BY atualizado DESC LIMIT 1", (cache_key,)).fetchone()
    return json.loads(r[0]) if r else None


def execucao_salvar(execucao: str, receita: str, receita_sha: str, dados_sha: str, status: str, passo: str | None,
                    sensivel: bool):
    agora = utcnow_iso()
    with _con() as c:
        r = c.execute("SELECT criado FROM receita_execucoes WHERE execucao=?", (execucao,)).fetchone()
        c.execute("INSERT OR REPLACE INTO receita_execucoes VALUES(?,?,?,?,?,?,?,?,?)",
                  (execucao, receita, receita_sha, dados_sha, status, passo, int(sensivel), r[0] if r else agora, agora))


def execucao_ler(execucao: str) -> dict | None:
    with _con() as c:
        r = c.execute("SELECT receita, receita_sha, dados_sha, status, passo, sensivel, criado, atualizado "
                      "FROM receita_execucoes WHERE execucao=?", (execucao,)).fetchone()
        passos = c.execute("SELECT passo, status, saida, atualizado FROM receita_passos WHERE execucao=? ORDER BY atualizado",
                           (execucao,)).fetchall() if r else []
    if not r:
        return None
    return {"execucao": execucao, "receita": r[0], "receita_sha": r[1], "dados_sha": r[2], "status": r[3], "passo": r[4],
            "sensivel": bool(r[5]), "criado": r[6], "atualizado": r[7],
            "passos": [{"passo": p, "status": st, "saida": json.loads(sa or "{}"), "atualizado": at} for p, st, sa, at in passos]}
