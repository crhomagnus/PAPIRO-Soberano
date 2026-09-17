# -*- coding: utf-8 -*-
"""CLI `papiro` (ADR-01): espelha as ferramentas MCP - mesmas funcoes, mesmo envelope, sem LLM.

  papiro status
  papiro ferramentas
  papiro chamar <ferramenta> '<json de argumentos>'        # qualquer uma das 48
  papiro inspecionar|ocr|otimizar|qa|comparar ...          # atalhos"""
from __future__ import annotations
import json, pathlib, sys
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
def vigiar(pasta: str = "", uma_vez: bool = False, intervalo: float = 5.0, tempo_limite: float = 0.0,
           reprocessar: bool = False, estado: bool = False):
    """RF-906: fica observando as pastas do papiro.toml e roda a receita de cada uma no arquivo que chegar.

    --uma-vez processa o que ja esta la e sai (bom para o Agendador do Windows, RF-907); --estado so mostra a situacao."""
    from . import vigia as VIG
    if estado:
        _imprimir({"ok": True, **VIG.estado(pasta)})
    elif uma_vez:
        _imprimir({"ok": True, **VIG.varredura(pasta, reprocessar=reprocessar)})
    else:
        typer.echo(f"vigiando (Ctrl+C para parar; varredura de seguranca a cada {intervalo:g}s)...", err=True)
        _imprimir({"ok": True, **VIG.vigiar(pasta, intervalo=intervalo, tempo_limite=tempo_limite,
                                            ao_criar=lambda r: typer.echo(
                                                f"  {r['status']:22} {pathlib.Path(r['arquivo']).name}", err=True))})


@app.command()
def token(modulo: str = "", pin_ref: str = "prompt", certificados: bool = True):
    """Token A3: lista os tokens conectados e os certificados gravados (para saber o que usar em `sign`).

    O PIN e pedido no ato (pin_ref='prompt') e nunca e gravado. Sem --certificados, nem pede PIN."""
    lib = SEG._modulo_pkcs11(modulo)
    saida = {"ok": True, "modulo": lib, "tokens": SEG.tokens_conectados(lib)}
    if certificados:
        from pyhanko.sign import pkcs11 as p11
        for t in saida["tokens"]:
            sessao = p11.open_pkcs11_session(lib, token_criteria=SEG._criterio_token(lib, t["rotulo"], None),
                                             user_pin=SEG._pin(pin_ref))
            try:
                t["certificados"] = SEG.certificados_do_token(sessao)
            finally:
                sessao.close()
    _imprimir(saida)


@app.command()
def comparar(a: str, b: str, out_dir: str = ""):
    """RF-607."""
    _imprimir(SRV.compare(a, b, _out(out_dir)))


def app_run():
    app()


if __name__ == "__main__":  # pragma: no cover
    app(sys.argv[1:])
