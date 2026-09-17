# -*- coding: utf-8 -*-
"""Os 9 hooks Python (.claude/hooks/papiro_hooks.py) executados como o Claude Code executa: JSON no stdin."""
import json, os, pathlib, subprocess, sys, time
from papiro_core import OUT, ROOT, WORK

HOOK = pathlib.Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "papiro_hooks.py"
REPO = pathlib.Path(__file__).resolve().parents[2]


def rodar(nome: str, evento: dict, **env_extra) -> dict | None:
    env = dict(os.environ, PAPIRO_HOME=str(ROOT), CLAUDE_PROJECT_DIR=str(REPO), **env_extra)
    r = subprocess.run([sys.executable, str(HOOK), nome], input=json.dumps(evento), capture_output=True, text=True,
                       env=env, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


def negado(saida) -> bool:
    return bool(saida) and saida.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def test_doctor_e_contexto():
    s = rodar("doctor", {"session_id": "sessao-teste"})
    assert "PAPIRO doctor" in s["hookSpecificOutput"]["additionalContext"]
    assert (ROOT / "logs" / "sessoes" / "sessao-teste.inicio").exists()
    s = rodar("contexto", {"prompt": "oi"})
    assert "entrega so com qa APROVADO" in s["hookSpecificOutput"]["additionalContext"]


def test_guarda_originais():
    assert negado(rodar("guarda-originais", {"tool_name": "Write", "tool_input": {"file_path": str(REPO / "docs" / "x.md")}}))
    assert negado(rodar("guarda-originais", {"tool_name": "Write", "tool_input": {"file_path": "/etc/passwd"}}))
    assert negado(rodar("guarda-originais", {"tool_name": "Edit", "tool_input": {"file_path": str(WORK / "job1" / "in" / "a.pdf")}}))
    assert rodar("guarda-originais", {"tool_name": "Write", "tool_input": {"file_path": str(OUT / "x" / "a.txt")}}) is None
    assert rodar("guarda-originais", {"tool_name": "Edit", "tool_input": {"file_path": str(REPO / "core" / "x.py")}}) is None
    for cmd in ("rm -rf /home/marcio", "rm -r ~/PAPIRO-Soberano/docs", "sudo mkfs.ext4 /dev/sda1",
                "dd if=/dev/zero of=/dev/sda bs=1M", "swapon /dev/sdb2", "cp novo.md docs/PAPIRO_PRD_ORIGINAL.md"):
        assert negado(rodar("guarda-originais", {"tool_name": "Bash", "tool_input": {"command": cmd}})), cmd
    assert rodar("guarda-originais", {"tool_name": "Bash", "tool_input": {"command": f"rm -rf {WORK}/job9"}}) is None
    assert rodar("guarda-originais", {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}) is None
    assert negado(rodar("guarda-originais", {"tool_name": "mcp__papiro__optimize", "tool_input": {"out_dir": "/tmp/x"}}))
    s = rodar("guarda-originais", {"tool_name": "mcp__papiro__optimize",
                                   "tool_input": {"out_dir": str(OUT / "j"), "entrada": str(OUT / "j" / "a.pdf")}})
    assert s and "mesma pasta" in s["hookSpecificOutput"]["additionalContext"]


def test_confirma_sensivel_e_auditoria():
    antes = (ROOT / "logs" / "audit.jsonl").read_text(encoding="utf-8") if (ROOT / "logs" / "audit.jsonl").exists() else ""
    assert negado(rodar("confirma-sensivel", {"tool_name": "mcp__papiro-seguranca__sign", "tool_input": {}}))
    assert rodar("confirma-sensivel", {"tool_name": "mcp__papiro-seguranca__sign", "tool_input": {"confirm": True}}) is None
    assert rodar("confirma-sensivel", {"tool_name": "mcp__papiro-seguranca__verify", "tool_input": {}}) is None
    depois = (ROOT / "logs" / "audit.jsonl").read_text(encoding="utf-8")
    assert depois.count("confirma-sensivel") == antes.count("confirma-sensivel") + 2


def test_soberania():
    web = {"tool_name": "WebFetch", "tool_input": {"url": "https://x.com"}}
    assert rodar("soberania", web) is None
    assert negado(rodar("soberania", web, PAPIRO_SENSIVEL="1"))
    assert negado(rodar("soberania", {"tool_name": "Bash", "tool_input": {"command": "curl https://x"}}, PAPIRO_SENSIVEL="1"))
    assert negado(rodar("soberania", {"tool_name": "mcp__papiro__capture", "tool_input": {"url": "https://x"}}, PAPIRO_SENSIVEL="1"))
    assert rodar("soberania", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, PAPIRO_SENSIVEL="1") is None


def test_valida_saida(pdf_bom, out_dir):
    from papiro_core import mcp_server as M
    env = M.metadata(str(pdf_bom), out_dir, titulo="T", autor="A", qa=False)
    resposta = [{"type": "text", "text": json.dumps(env)}]
    s = rodar("valida-saida", {"tool_name": "mcp__papiro__metadata", "tool_response": resposta})
    texto = s["hookSpecificOutput"]["additionalContext"]
    assert "hash confere" in texto and "qpdf --check ok" in texto
    assert pathlib.Path(env["outputs"][0]["path"]).with_name("metadados.miniatura.png").exists()


def test_pede_revisao_e_salva_estado(pdf_bom, out_dir):
    from papiro_core import mcp_server as M
    M.inspect("risk", str(pdf_bom), out_dir)
    s = rodar("pede-revisao", {"agent_type": "pdf-designer"})
    assert "pdf-revisor-qa" in s["systemMessage"] and (WORK / "_revisao_pendente.flag").exists()
    s = rodar("salva-estado", {})
    assert "snapshot" in s["systemMessage"] and (ROOT / "logs" / "jobs.precompact.db").exists()


def test_portao_final(pdf_bom, pdf_textos, out_dir):
    from papiro_core import mcp_server as M
    ev = {"session_id": "sessao-portao"}
    rodar("doctor", ev)
    time.sleep(1.1)
    M.qa_run(str(pdf_textos[0]), out_dir)            # reprovado
    s = rodar("portao-final", ev)
    assert s["decision"] == "block" and "REPROVADO" in s["reason"]
    assert rodar("portao-final", {**ev, "stop_hook_active": True}) is None
    time.sleep(1.1)
    M.qa_run(str(pdf_bom), out_dir)                  # aprovado por ultimo
    assert rodar("portao-final", ev) is None


def test_hook_desconhecido_ou_evento_ruim_nao_trava():
    r = subprocess.run([sys.executable, str(HOOK), "inexistente"], input="{}", capture_output=True, text=True)
    assert r.returncode == 0
    r = subprocess.run([sys.executable, str(HOOK), "guarda-originais"], input="nao e json", capture_output=True, text=True)
    assert r.returncode == 0 and not r.stdout.strip()
