# -*- coding: utf-8 -*-
"""RF-906: pastas monitoradas com receita associada (watchdog) - deteccao, receita, dedup e as travas de §12."""
import json, pathlib, threading, time
import pytest
from papiro_core import ROOT, config, mcp_server as M, vigia as VIG
from papiro_core.erros import PapiroErro
from conftest import envelope_ok

RECEITA_LEVE = """receita: triagem-de-entrada
versao: 1
descricao: Triagem de risco do que chega (RF-009)
entradas:
  entrada: {tipo: arquivo, obrigatoria: true}
passos:
  - id: triagem
    ferramenta: inspect
    com: {op: risk, entrada: $dados.entrada}
    exige: {ok: true}
"""
RECEITA_SENSIVEL = """receita: assinar-o-que-chega
versao: 1
descricao: Prova que a pasta monitorada nunca assina sozinha
sensivel: true
entradas:
  entrada: {tipo: arquivo, obrigatoria: true}
passos:
  - id: assinar
    ferramenta: papiro-seguranca.sign
    com: {entrada: $dados.entrada}
    confirmacao: obrigatoria
"""


def _toml(blocos: str):
    (ROOT / "papiro.toml").write_text(blocos, encoding="utf-8")
    config.carregar.cache_clear()


@pytest.fixture
def pasta_vigiada(request):
    """Escreve um papiro.toml com [[pastas]] e desfaz no fim (o resto da suite nao ve essa config)."""
    def montar(nome: str, receita_texto: str, **extra):
        (ROOT / "receitas_teste").mkdir(exist_ok=True)
        receita = ROOT / "receitas_teste" / f"{nome}.yaml"
        receita.write_text(receita_texto, encoding="utf-8")
        entrada = ROOT / "watch" / nome
        entrada.mkdir(parents=True, exist_ok=True)
        opcoes = "\n".join(f"{k} = {json.dumps(v)}" for k, v in extra.items())
        _toml(f'[[pastas]]\nnome = "{nome}"\nentrada = "watch/{nome}"\n'
              f'receita = "receitas_teste/{nome}.yaml"\nestavel_s = 0.3\n{opcoes}\n')
        return entrada
    yield montar
    (ROOT / "papiro.toml").unlink(missing_ok=True)
    config.carregar.cache_clear()


def _soltar(destino: pathlib.Path, nome: str, texto: str = "documento recebido") -> pathlib.Path:
    """Escreve como um scanner faria: arquivo temporario + renomeacao atomica."""
    import fitz
    from conftest import FONTE
    d = fitz.open()
    pg = d.new_page()
    pg.insert_font(fontname="lib", fontfile=str(FONTE))
    pg.insert_text((72, 100), texto, fontname="lib", fontsize=12)
    d.set_metadata({"title": nome, "author": "teste", "producer": "teste"})
    d.set_language("pt-BR")
    parcial = destino / f"{nome}.part"
    d.save(parcial)
    d.close()
    alvo = destino / f"{nome}.pdf"
    parcial.rename(alvo)
    return alvo


def test_configuracao_das_pastas_e_conferida(pasta_vigiada, tmp_path):
    pasta_vigiada("ok1", RECEITA_LEVE)
    assert [p["nome"] for p in VIG.pastas()] == ["ok1"] and VIG.pastas("ok1")[0]["entrada"].is_dir()
    with pytest.raises(PapiroErro) as e:
        VIG.pastas("nao-existe")
    assert e.value.codigo == "E_ENTRADA" and "ok1" in e.value.mensagem
    casos = [('[[pastas]]\nnome = "x"\nreceita = "receitas_teste/ok1.yaml"\n', "E_ENTRADA", "falta 'entrada'"),
             ('[[pastas]]\nnome = "x"\nentrada = "watch/ok1"\n', "E_ENTRADA", "falta 'receita'"),
             ('[[pastas]]\nnome = "x"\nentrada = "watch/ok1"\nreceita = "nao/existe.yaml"\n', "E_ENTRADA", "nao existe"),
             (f'[[pastas]]\nnome = "x"\nentrada = {json.dumps(str(tmp_path))}\n'
              'receita = "receitas_teste/ok1.yaml"\n', "E_POLITICA", "fora do PAPIRO"),
             ('[[pastas]]\nnome = "x"\nentrada = "watch/ok1"\nreceita = "receitas_teste/ok1.yaml"\n'
              'ao_terminar = "apagar"\n', "E_ENTRADA", "ao_terminar"),
             ('[[pastas]]\nnome = "x"\nentrada = "watch/ok1"\nreceita = "receitas_teste/ok1.yaml"\n'
              '[[pastas]]\nnome = "x"\nentrada = "watch/ok1"\nreceita = "receitas_teste/ok1.yaml"\n',
              "E_ENTRADA", "mesmo nome")]
    for texto, codigo, trecho in casos:
        _toml(texto)
        with pytest.raises(PapiroErro) as e:
            VIG.pastas()
        assert e.value.codigo == codigo and trecho in e.value.mensagem, texto


def test_varredura_processa_move_e_nao_repete(pasta_vigiada):
    entrada = pasta_vigiada("recebidos", RECEITA_LEVE, ao_terminar="mover")
    arquivo = _soltar(entrada, "nota")
    time.sleep(0.4)
    r = VIG.varredura()["pastas"][0]["arquivos"][0]
    assert r["status"] == "concluido" and r["execucao"].startswith("rec-")
    assert not arquivo.exists() and (entrada / "processados" / "nota.pdf").is_file()   # original so mudou de pasta
    assert VIG.varredura()["total"] == {}                                             # nada novo na pasta
    import shutil
    igual = entrada / "nota.pdf"                                                       # o mesmo arquivo, de novo
    shutil.copy2(entrada / "processados" / "nota.pdf", igual)
    time.sleep(0.4)
    assert VIG.varredura()["pastas"][0]["arquivos"][0]["status"] == "repetido"
    assert igual.exists()                                                              # repetido nao e movido
    assert VIG.varredura(reprocessar=True)["pastas"][0]["arquivos"][0]["status"] == "concluido"
    assert (entrada / "processados" / "nota_1.pdf").is_file()                          # nunca sobrescreve


def test_espera_o_arquivo_terminar_de_chegar(pasta_vigiada):
    entrada = pasta_vigiada("chegando", RECEITA_LEVE)
    _soltar(entrada, "fresco")
    assert VIG.varredura()["pastas"][0]["arquivos"][0]["status"] == "aguardando_copia"
    (entrada / "meio.pdf.part").write_bytes(b"%PDF-1.7 pela metade")
    (entrada / ".oculto.pdf").write_bytes(b"%PDF-1.7 oculto")
    (entrada / "planilha.xlsx").write_bytes(b"nao e pdf")
    time.sleep(0.4)
    processados = [i["arquivo"] for i in VIG.varredura()["pastas"][0]["arquivos"]]
    assert [pathlib.Path(p).name for p in processados] == ["fresco.pdf"]


def test_arquivo_ruim_vai_para_falhas(pasta_vigiada):
    entrada = pasta_vigiada("ruins", RECEITA_LEVE, ao_terminar="mover")
    (entrada / "quebrado.pdf").write_bytes(b"%PDF-1.7 isto nao e um PDF de verdade")
    time.sleep(0.4)
    r = VIG.varredura()["pastas"][0]["arquivos"][0]
    assert r["status"] in ("falhou", "reprovado")      # reprovado = a assercao 'exige' do passo barrou
    assert (entrada / "falhas" / "quebrado.pdf").is_file()
    assert VIG.estado()["falhas"][0]["arquivo"].endswith("quebrado.pdf")


def test_arquivo_que_falhou_e_ficou_na_pasta_nao_repete_em_laco(pasta_vigiada):
    """Com ao_terminar='nada' o arquivo continua na pasta: rodar de novo a cada varredura seria um laco."""
    entrada = pasta_vigiada("sem_mover", RECEITA_LEVE)
    (entrada / "quebrado.pdf").write_bytes(b"%PDF-1.7 isto nao e um PDF de verdade")
    time.sleep(0.4)
    primeira = VIG.varredura()["pastas"][0]["arquivos"][0]
    assert primeira["status"] in ("falhou", "reprovado")
    repetida = VIG.varredura()["pastas"][0]["arquivos"][0]
    assert repetida["status"] == "repetido" and repetida["resultado_anterior"] == primeira["status"]
    assert (entrada / "quebrado.pdf").exists()                      # continua la, esperando decisao do usuario
    assert VIG.estado("sem_mover")["falhas"][0]["arquivo"].endswith("quebrado.pdf")
    forcada = VIG.varredura(reprocessar=True)["pastas"][0]["arquivos"][0]
    assert forcada["status"] == primeira["status"]                  # so o usuario manda tentar de novo


def test_pasta_monitorada_nunca_assina_sozinha(pasta_vigiada):
    """§12: passo sensivel pausa, o arquivo fica onde esta e a decisao volta para o usuario."""
    entrada = pasta_vigiada("assinar", RECEITA_SENSIVEL, ao_terminar="mover")
    arquivo = _soltar(entrada, "sigiloso")
    time.sleep(0.4)
    r = VIG.varredura()["pastas"][0]["arquivos"][0]
    assert r["status"] == "aguardando_confirmacao" and r["movido"] is None and arquivo.exists()
    assert r["pendente"]["ferramenta"] == "papiro-seguranca.sign"
    assert r["pendente"]["como_retomar"]["execucao"] == r["execucao"]
    estado = VIG.estado("assinar")
    assert [p["execucao"] for p in estado["pendentes"]] == [r["execucao"]]
    assert VIG.varredura()["pastas"][0]["arquivos"][0]["status"] == "repetido"   # nao reinicia o que esta pendente


def test_vigiar_pega_arquivo_novo_dentro_do_prazo(pasta_vigiada, monkeypatch):
    """RF-906: o vigia pega o arquivo novo em ate 10 s (watchdog + janela de estabilidade).

    O prazo cobrado aqui e o do vigia: perceber o arquivo, esperar ele parar de crescer e comecar. O tempo da
    receita depois disso e da receita (um OCR leva minutos) e da carga da maquina, entao e so registrado."""
    entrada = pasta_vigiada("ao_vivo", RECEITA_LEVE)
    VIG.estado("ao_vivo")        # aquece: cria logs/jobs.db antes de cronometrar
    marcas = {}
    processar_real = VIG.processar

    def cronometrar(pasta, arquivo, reprocessar=False):
        marcas.setdefault("comecou", time.time())
        return processar_real(pasta, arquivo, reprocessar)
    monkeypatch.setattr(VIG, "processar", cronometrar)

    def soltar_depois():
        time.sleep(1.0)
        _soltar(entrada, "ao_vivo")
        marcas["chegou"] = time.time()
    threading.Thread(target=soltar_depois, daemon=True).start()
    resumo = VIG.vigiar("ao_vivo", intervalo=3.0, tempo_limite=30.0,
                        ao_criar=lambda r: marcas.setdefault("pronto", time.time()))
    assert resumo["resumo"] == {"concluido": 1} and len(resumo["processados"]) == 1
    pegar = marcas["comecou"] - marcas["chegou"]
    total = marcas["pronto"] - marcas["chegou"]
    assert pegar <= 10.0, f"RF-906: o vigia levou {pegar:.1f} s para pegar o arquivo (ciclo todo: {total:.1f} s)"


def test_mcp_watch_e_watch_status(pasta_vigiada):
    entrada = pasta_vigiada("por_mcp", RECEITA_SENSIVEL)
    _soltar(entrada, "um")
    time.sleep(0.4)
    e = envelope_ok(M.recipes("watch"))
    assert e["ok"] and e["dados"]["total"] == {"aguardando_confirmacao": 1}
    assert e["warnings"] and "aguardando_confirmacao" in e["warnings"][0]
    s = envelope_ok(M.recipes("watch_status", nome="por_mcp"))
    assert s["ok"] and s["dados"]["pastas"][0]["nome"] == "por_mcp" and len(s["dados"]["pendentes"]) == 1
    assert envelope_ok(M.recipes("watch", nome="nao-existe"))["error"]["code"] == "E_ENTRADA"


def test_cli_vigiar(pasta_vigiada, capsys):
    from papiro_core import cli
    entrada = pasta_vigiada("pela_cli", RECEITA_LEVE)
    _soltar(entrada, "doc")
    time.sleep(0.4)
    cli.vigiar(uma_vez=True)
    saida = json.loads(capsys.readouterr().out)
    assert saida["ok"] and saida["total"] == {"concluido": 1}
    cli.vigiar(estado=True)
    assert json.loads(capsys.readouterr().out)["pastas"][0]["nome"] == "pela_cli"
