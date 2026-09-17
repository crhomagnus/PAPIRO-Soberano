# -*- coding: utf-8 -*-
"""Executor de receitas §9.3: validacao, checkpoints e retomada, cache por hash, exige, se/para_cada/paralelo,
confirmacao, delegacao ao pdf-seguranca, sensivel, cancelamento e RF-908 (tarefa vira receita)."""
import json, pathlib
import pytest
import yaml
from papiro_core import RECIPES, WORK, mcp_server as M, mcp_seguranca as S, receitas as REC, templates as TP
from papiro_core.erros import PapiroErro
from conftest import CORPUS, envelope_ok


def receita(nome: str, conteudo: dict) -> str:
    p = CORPUS / f"{nome}.yaml"
    p.write_text(yaml.safe_dump(conteudo, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(p)


def passos(env):
    return [(p["id"], p.get("status")) for p in env["dados"]["passos"]]


def test_receitas_do_repositorio_sao_validas():
    e = envelope_ok(M.recipes("list"))
    nomes = {r["arquivo"]: r for r in e["dados"]["receitas"]}
    assert {"exemplo-receituario-assinado.yaml", "atestado-pdfa.yaml", "lote-certificados.yaml"} <= set(nomes)
    assert not any("invalida" in r for r in nomes.values())


def test_validacao_recusa_receita_ruim():
    ruim = receita("ruim", {"receita": "Ruim", "versao": 0, "passos": [{"id": "a", "ferramenta": "nao_existe"},
                                                                       {"id": "a", "ferramenta": "papiro-seguranca.xyz"}]})
    e = envelope_ok(M.recipes("validate", arquivo=ruim))
    assert e["dados"]["valida"] is False and e["dados"]["erros"]
    erros = REC.validar({"receita": "ok", "versao": 1, "passos": [{"id": "a", "ferramenta": "nao_existe"},
                                                                 {"id": "a", "ferramenta": "papiro-seguranca.xyz", "para_cada": "$dados"}]})
    assert any("repetidos" in x for x in erros) or any("desconhecida" in x for x in erros)
    yaml_ruim = CORPUS / "quebrada.yaml"
    yaml_ruim.write_text("receita: [sem fechar", encoding="utf-8")
    assert envelope_ok(M.recipes("validate", arquivo=str(yaml_ruim)))["dados"]["valida"] is False
    assert envelope_ok(M.recipes("run", arquivo=ruim))["error"]["code"] == "E_ENTRADA"
    assert envelope_ok(M.recipes("run"))["error"]["code"] == "E_ENTRADA"
    assert envelope_ok(M.recipes("xyz"))["error"]["code"] == "E_SEM_SUPORTE"


def test_atestado_completo_e_cache(out_dir):
    dados = json.dumps(TP.exemplo("atestado"))
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=str(RECIPES / "atestado-pdfa.yaml"), dados_json=dados))
    assert e["ok"], e.get("error")
    assert passos(e) == [("compor", "ok"), ("validar", "ok"), ("revisar", "ok")]
    final = pathlib.Path(e["dados"]["saida_final"])
    assert final.exists() and final.name.startswith("atestado-") and "Paciente" not in final.name
    assert not (WORK / "_sensivel.flag").exists()
    e2 = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=str(RECIPES / "atestado-pdfa.yaml"), dados_json=dados))
    assert passos(e2) == [("compor", "cache"), ("validar", "cache"), ("revisar", "cache")]
    assert e2["metrics"]["seconds"] < e["metrics"]["seconds"]


def test_entradas_obrigatorias_e_esquema(out_dir):
    arq = str(RECIPES / "atestado-pdfa.yaml")
    assert envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq))["error"]["code"] == "E_ENTRADA"
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=json.dumps({"medico": {"nome": "x"}})))
    assert e["error"]["code"] == "E_ENTRADA" and "esquema" in e["error"]["message"]
    assert envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json="{x"))["error"]["code"] == "E_ENTRADA"


def test_receituario_confirmacao_seguranca_e_retomada(out_dir, pfx_teste):
    arq = str(RECIPES / "exemplo-receituario-assinado.yaml")
    dados = json.dumps(TP.exemplo("receituario"))
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=dados))
    assert e["error"]["code"] == "E_POLITICA" and passos(e)[-1] == ("assinar", "aguardando_confirmacao")
    execucao = e["dados"]["execucao"]
    assert (WORK / "_sensivel.flag").exists()
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=dados, execucao=execucao, confirmados="assinar"))
    assert passos(e)[:3] == [("compor", "retomado (ok)"), ("validar", "retomado (ok)"), ("revisar", "retomado (ok)")]
    pend = e["dados"]["pendente"]
    assert pend["tipo"] == "seguranca" and pend["subagente"] == "pdf-seguranca" and pend["ferramenta"] == "mcp__papiro-seguranca__sign"
    assert any("A3" in o for o in pend["observacoes"])
    # o pdf-seguranca assina de verdade (A1 de teste) fora do executor
    args = {k: v for k, v in pend["argumentos_sugeridos"].items() if k in ("entrada", "out_dir", "confirm")}
    assinado = envelope_ok(S.sign(pfx=str(pfx_teste), senha_ref="env:PAPIRO_TESTE_PFX_SENHA", **args))
    assert assinado["ok"], assinado.get("error")
    caminho = assinado["outputs"][0]["path"]
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=dados, execucao=execucao,
                              confirmados="assinar", externos_json=json.dumps({"assinar": {"saida": caminho}})))
    assert passos(e)[3] == ("assinar", "externo") and passos(e)[4] == ("verificar", "aguardando_seguranca")
    verif = envelope_ok(S.verify(caminho, e["dados"]["pendente"]["argumentos_sugeridos"]["out_dir"]))
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=dados, execucao=execucao, confirmados="assinar",
                              externos_json=json.dumps({"assinar": {"saida": caminho}, "verificar": verif})))
    assert e["ok"], e.get("error")
    final = pathlib.Path(e["dados"]["saida_final"])
    assert final.exists() and "/medico/" in str(final) and final.name.startswith("receita-")
    assert not (WORK / "_sensivel.flag").exists()
    st = envelope_ok(M.recipes("status", execucao=execucao))
    assert st["dados"]["status"] == "concluido"
    assert envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=dados, execucao=execucao))["error"]["code"] == "E_ENTRADA"
    outros = json.dumps({**TP.exemplo("receituario"), "orientacoes": "outra"})
    assert envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=outros, execucao="rec-nao-existe"))["error"]["code"] == "E_ENTRADA"


def test_cancelar_execucao_pausada(out_dir):
    arq = str(RECIPES / "exemplo-receituario-assinado.yaml")
    dados = json.dumps(TP.exemplo("receituario"))
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=dados))
    execucao = e["dados"]["execucao"]
    assert (WORK / "_sensivel.flag").exists()
    assert envelope_ok(M.recipes("cancel", execucao=execucao))["dados"]["status"] == "cancelado"
    assert not (WORK / "_sensivel.flag").exists()
    assert envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, dados_json=dados, execucao=execucao))["error"]["code"] == "E_ENTRADA"
    assert envelope_ok(M.recipes("status", execucao="nao-existe"))["error"]["code"] == "E_ENTRADA"
    with pytest.raises(PapiroErro):
        REC.cancelar("nao-existe")


def test_lote_paralelo_condicao_e_encadeamento(out_dir):
    base = TP.exemplo("certificado")
    lote = {"certificados": [dict(base, participante=n) for n in ("Ana", "Bruno", "Carla")], "juntar": True, "nota_visual": 8.5}
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=str(RECIPES / "lote-certificados.yaml"), dados_json=json.dumps(lote)))
    assert e["ok"], e.get("error")
    gerar = e["dados"]["passos"][0]
    assert gerar["status"] == "ok" and gerar["itens"] == 3 and gerar["paralelo"] == 2
    import fitz
    with fitz.open(e["dados"]["saida_final"]) as d:
        assert d.page_count == 3
    lote["juntar"] = False
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=str(RECIPES / "lote-certificados.yaml"), dados_json=json.dumps(lote)))
    assert passos(e)[1] == ("juntar", "pulado")


def test_exige_reprova_e_falha_de_ferramenta(pdf_helv, out_dir):
    arq = receita("exige", {"receita": "exige-teste", "versao": 1, "passos": [
        {"id": "qa", "ferramenta": "qa_run", "com": {"entrada": str(pdf_helv)}, "exige": {"qa": "APROVADO"}}]})
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq))
    assert e["error"]["code"] == "E_CONFORMIDADE" and passos(e) == [("qa", "reprovado")]
    arq = receita("falha", {"receita": "falha-teste", "versao": 1, "passos": [
        {"id": "otimizar", "ferramenta": "optimize", "com": {"entrada": str(CORPUS / "nao-existe.pdf")}}]})
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq))
    assert e["error"]["code"] == "E_ENTRADA" and passos(e) == [("otimizar", "falhou")]
    arq = receita("sem-entrada", {"receita": "sem-entrada", "versao": 1, "passos": [{"id": "o", "ferramenta": "optimize"}]})
    assert envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq))["error"]["code"] == "E_ENTRADA"
    arq = receita("param-ruim", {"receita": "param-ruim", "versao": 1, "passos": [
        {"id": "o", "ferramenta": "optimize", "com": {"entrada": str(pdf_helv), "nao_existe": 1}}]})
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq))
    assert e["error"]["code"] == "E_ENTRADA" and "nao_existe" in e["error"]["message"]


def test_retomada_apos_queda(pdf_bom, out_dir, monkeypatch):
    arq = receita("queda", {"receita": "queda-teste", "versao": 1, "passos": [
        {"id": "meta", "ferramenta": "metadata", "com": {"entrada": str(pdf_bom), "titulo": "T", "autor": "A", "qa": False}},
        {"id": "otim", "ferramenta": "optimize", "com": {"perfil": "arquivo", "qa": False}}]})
    import functools
    reais = REC.ferramentas()
    chamadas = {"n": 0}

    @functools.wraps(reais["optimize"])
    def quebra(*a, **k):
        chamadas["n"] += 1
        raise PapiroErro("E_TEMPO", "queda simulada")
    monkeypatch.setattr(REC, "ferramentas", lambda: {**reais, "optimize": quebra})
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq))
    assert passos(e) == [("meta", "ok"), ("otim", "falhou")] and e["error"]["code"] == "E_TEMPO"
    monkeypatch.setattr(REC, "ferramentas", lambda: reais)
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=arq, execucao=e["dados"]["execucao"]))
    assert e["ok"] and passos(e) == [("meta", "retomado (ok)"), ("otim", "ok")]


def test_tarefa_vira_receita_rf908(pdf_bom, out_dir):
    a = envelope_ok(M.compose("auto", out_dir, template="proposta", usar_exemplo=True, qa=False))
    b = envelope_ok(M.optimize(a["outputs"][0]["path"], out_dir, perfil="arquivo", qa=False))
    assert a["ok"] and b["ok"]
    s = envelope_ok(M.recipes("save", out_dir=out_dir, job_ids=f"{a['job_id']},{b['job_id']}", nome="proposta-otimizada"))
    assert s["ok"], s.get("error")
    rec = yaml.safe_load(pathlib.Path(s["outputs"][0]["path"]).read_text(encoding="utf-8"))
    assert [p["ferramenta"] for p in rec["passos"]] == ["compose", "optimize"]
    assert rec["passos"][1]["com"]["entrada"] == f"${rec['passos'][0]['id']}.saida"
    e = envelope_ok(M.recipes("run", out_dir=out_dir, arquivo=s["outputs"][0]["path"]))
    assert e["ok"], e.get("error")
    with pytest.raises(PapiroErro):
        REC.receita_de_jobs(["nao-existe"], "x")
    with pytest.raises(PapiroErro):
        REC.receita_de_jobs([a["job_id"]], "Nome Invalido")
    assert envelope_ok(M.recipes("save", out_dir=out_dir, nome="x"))["error"]["code"] == "E_ENTRADA"


def test_condicoes_referencias_e_comparacoes():
    ctx = {"dados": {"tipo": "a", "n": 3, "lista": [1, 2], "vazio": ""}, "execucao": "e", "data": "d", "passos": {"p": {"saida": "x.pdf"}}}
    assert REC.avaliar_condicao("$dados.tipo == 'a'", ctx) and REC.avaliar_condicao("$dados.tipo != \"b\"", ctx)
    assert REC.avaliar_condicao("$dados.n == 3", ctx) and REC.avaliar_condicao("not $dados.vazio", ctx)
    assert not REC.avaliar_condicao("$dados.inexistente", ctx)
    with pytest.raises(PapiroErro):
        REC.avaliar_condicao("1 + 1", ctx)
    assert REC.resolver({"a": "$p.saida", "b": ["$dados.lista.1"], "c": "texto $x"}, ctx) == {"a": "x.pdf", "b": [2], "c": "texto $x"}
    for ruim in ("$nada", "$dados.x.y"):
        with pytest.raises(PapiroErro):
            REC.resolver(ruim, ctx)
    assert REC._comparar(5, ">=5") and REC._comparar(5, "<10") and not REC._comparar("5", ">1") and REC._comparar("aprovado", "APROVADO")
    env = {"ok": True, "outputs": [{"path": "a.pdf", "pages": 2}], "qa": {"status": "APROVADO"}, "dados": {"padroes": {"PDF/A-2b": {"ok": True}}}}
    assert REC.checar_exige({"ok": True, "paginas": ">=2", "verapdf": "aprovado", "qa": "APROVADO", "dados.padroes": {"PDF/A-2b": {"ok": True}}}, env) == []
    assert REC.checar_exige({"erro": None}, env) == []
    plano = REC.executar({"receita": "p", "versao": 1, "passos": [{"id": "a", "ferramenta": "engines"}]}, "sha", dry_run=True)
    assert plano["status"] == "planejado"
