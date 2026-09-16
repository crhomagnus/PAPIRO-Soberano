# -*- coding: utf-8 -*-
"""Servidor MCP papiro-seguranca - 10 tools isoladas §8.4. Exige confirmacao explicita."""
from __future__ import annotations
import json, os, time, pathlib
from mcp.server.fastmcp import FastMCP
from . import new_job_id
from .audit import envelope, err, out_entry
from .adapters import edit as ED
from .adapters import convert as CONV
from .adapters import intel as INTEL

mcp = FastMCP("papiro-seguranca")

def _need_confirm(confirm: bool):
    if not (confirm or os.environ.get("PAPIRO_CONFIRM") == "1"):
        return err("E_POLITICA", "operacao sensivel exige confirmacao explicita (confirm=true)")
    return None

def _ctx(out_dir: str):
    jid = new_job_id()
    o = pathlib.Path(out_dir)
    o.mkdir(parents=True, exist_ok=True)
    return jid, o, time.time()

@mcp.tool()
def sign(entrada: str, out_dir: str, confirm: bool = False) -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    return {"ok": False, "error": err("E_SEM_SUPORTE", "sign PAdES exige pyHanko + certificado ICP-Brasil (fase 2). Homologar ITI/CFM.")}

@mcp.tool()
def certify(entrada: str, out_dir: str, confirm: bool = False) -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    return {"ok": False, "error": err("E_SEM_SUPORTE", "certify DocMDP exige pyHanko (fase 2)")}

@mcp.tool()
def timestamp(entrada: str, out_dir: str, confirm: bool = False) -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    return {"ok": False, "error": err("E_SEM_SUPORTE", "timestamp RFC3161 exige TSA configurada (fase 2)")}

@mcp.tool()
def ltv_update(entrada: str, out_dir: str, confirm: bool = False) -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    return {"ok": False, "error": err("E_SEM_SUPORTE", "ltv B-LT/B-LTA exige pyHanko (fase 2)")}

@mcp.tool()
def verify(entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    d = {"assinaturas": CONV.listar_campos(pathlib.Path(entrada)), "nota": "validacao criptografica total exige pyHanko (fase 2)"}
    f = o / "verify.json"
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "fitz-campos"}, time.time() - t0)

@mcp.tool()
def encrypt(entrada: str, out_dir: str, senha: str, confirm: bool = False, saida: str = "enc.pdf") -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    CONV.criptografar(pathlib.Path(entrada), out, senha)
    return envelope(jid, [out_entry(out)], {"name": "pikepdf-AES256"}, time.time() - t0)

@mcp.tool()
def decrypt(entrada: str, out_dir: str, senha: str, confirm: bool = False, saida: str = "dec.pdf") -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    jid, o, t0 = _ctx(out_dir)
    import pikepdf
    out = o / saida
    with pikepdf.open(entrada, password=senha) as pdf:
        pdf.save(out)
    return envelope(jid, [out_entry(out)], {"name": "pikepdf"}, time.time() - t0)

@mcp.tool()
def redact_detect(entrada: str, out_dir: str) -> dict:
    jid, o, t0 = _ctx(out_dir)
    t = INTEL.texto_completo(pathlib.Path(entrada))
    d = INTEL.detectar_pii(t)
    f = o / "pii.json"
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return envelope(jid, [out_entry(f)], {"name": "regex-pii"}, time.time() - t0)

@mcp.tool()
def redact_apply(entrada: str, out_dir: str, caixas_json: str, confirm: bool = False, saida: str = "tarjado.pdf") -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    r = ED.tarjar(pathlib.Path(entrada), out, json.loads(caixas_json))
    return envelope(jid, [out_entry(out, r["paginas"])], {"name": "fitz-redact-real"}, time.time() - t0)

@mcp.tool()
def sanitize(entrada: str, out_dir: str, confirm: bool = False, saida: str = "san.pdf") -> dict:
    e = _need_confirm(confirm)
    if e: return {"ok": False, "error": e}
    jid, o, t0 = _ctx(out_dir)
    out = o / saida
    CONV.sanitizar(pathlib.Path(entrada), out)
    return envelope(jid, [out_entry(out)], {"name": "pikepdf+fitz"}, time.time() - t0)

def main():
    mcp.run()

if __name__ == "__main__":
    main()
