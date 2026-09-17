# -*- coding: utf-8 -*-
"""CLI `papiro` (ADR-01): espelha as ferramentas MCP - mesmas funcoes, mesmo envelope, sem LLM.

  papiro status
  papiro ferramentas
  papiro chamar <ferramenta> '<json de argumentos>'        # qualquer uma das 48
  papiro inspecionar|ocr|otimizar|qa|comparar ...          # atalhos"""
from __future__ import annotations
import json, sys
import typer
from . import OUT
from . import mcp_seguranca as SEG, mcp_server as SRV

app = typer.Typer(add_completion=False, help="PAPIRO SOBERANO - CLI espelho do MCP (envelope JSON na saida)")


def _registro() -> dict:
    ferr = {}
    for modulo in (SRV, SEG):
        for t in modulo.mcp._tool_manager.list_tools():
            ferr[t.name if modulo is SRV else f"seguranca.{t.name}"] = t.fn
    return ferr


def _imprimir(env: dict) -> None:
    typer.echo(json.dumps(env, ensure_ascii=False, indent=2, default=str))
    if isinstance(env, dict) and env.get("ok") is False:
        raise typer.Exit(1)


def _out(out_dir: str) -> str:
    if out_dir:
        return out_dir
    from datetime import date
    return str(OUT / date.today().isoformat())


@app.command()
def status():
    """Saude do ambiente: motores, versoes, idiomas do Tesseract e perfil (/papiro-status)."""
    _imprimir(SRV.engines())


@app.command()
def ferramentas():
    """Lista as ferramentas disponiveis (38 papiro + 10 seguranca)."""
    for nome in sorted(_registro()):
        typer.echo(nome)


@app.command()
def chamar(ferramenta: str, argumentos: str = typer.Argument("{}", help="JSON com os argumentos")):
    """Chama qualquer ferramenta pelo nome com argumentos em JSON."""
    reg = _registro()
    if ferramenta not in reg:
        typer.echo(f"ferramenta desconhecida: {ferramenta}", err=True)
        raise typer.Exit(2)
    try:
        kwargs = json.loads(argumentos)
    except json.JSONDecodeError as e:
        typer.echo(f"JSON invalido: {e.msg}", err=True)
        raise typer.Exit(2)
    _imprimir(reg[ferramenta](**kwargs))


@app.command()
def inspecionar(arquivo: str, out_dir: str = ""):
    """Nivel 0 completo (RF-001..009)."""
    _imprimir(SRV.inspect("all", arquivo, _out(out_dir)))


@app.command()
def ocr(arquivo: str, out_dir: str = "", idioma: str = "por"):
    """RF-601 com PDF/A (so paginas sem texto)."""
    _imprimir(SRV.ocr(arquivo, _out(out_dir), idioma))


@app.command()
def otimizar(arquivo: str, out_dir: str = "", perfil: str = "email", linearizar: bool = False):
    """RF-902/903."""
    _imprimir(SRV.optimize(arquivo, _out(out_dir), perfil, linearizar=linearizar))


@app.command()
def criar(markdown: str, out_dir: str = "", titulo: str = "", saida: str = "documento.pdf"):
    """RF-301: Markdown (arquivo ou texto) -> PDF com QA."""
    from pathlib import Path
    texto = Path(markdown).read_text(encoding="utf-8") if Path(markdown).is_file() else markdown
    _imprimir(SRV.compose("auto", _out(out_dir), markdown=texto, titulo=titulo, saida=saida))


@app.command()
def qa(arquivo: str, out_dir: str = "", design: bool = False, nota_visual: float = typer.Option(None),
       padrao: str = ""):
    """Portoes G1-G11."""
    _imprimir(SRV.qa_run(arquivo, _out(out_dir), design=design, nota_visual=nota_visual, padrao=padrao))


@app.command()
def comparar(a: str, b: str, out_dir: str = ""):
    """RF-607."""
    _imprimir(SRV.compare(a, b, _out(out_dir)))


def app_run():
    app()


if __name__ == "__main__":  # pragma: no cover
    app(sys.argv[1:])
