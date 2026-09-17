# -*- coding: utf-8 -*-
"""RF-906: pastas monitoradas com receita associada (watchdog).

Arquivo novo na pasta -> espera parar de crescer -> roda a receita da pasta -> registra em logs/jobs.db.
O original nunca e alterado: e lido e, so se a pasta pedir, movido para 'processados/' depois de concluir.
Receita com confirmacao ou com passo de seguranca NAO e confirmada aqui - a execucao fica pendente para o
usuario decidir (§12: nada de assinar ou tarjar sozinho). As pastas vem do papiro.toml:

    [[pastas]]
    nome = "recebidos"
    entrada = "watch/recebidos"          # relativa a raiz do PAPIRO; precisa estar dentro dela ou liberada
    receita = "recipes/entrada-ocr-pdfa.yaml"
    campo = "entrada"                    # nome do dado que recebe o caminho do arquivo
    padrao = "*.pdf"
    estavel_s = 3.0                      # segundos sem mudar de tamanho antes de processar
    ao_terminar = "mover"                # nada | mover (processados/ e falhas/)
"""
from __future__ import annotations
import fnmatch, pathlib, queue, shutil, time
from . import REPO, ROOT, sha256_file
from . import caminhos as CAM, config, jobs as JOBS, receitas as REC
from .erros import PapiroErro

SUFIXOS_IGNORADOS = (".tmp", ".part", ".crdownload", ".partial", ".filepart", ".lock", ".swp")
PADRAO_PASTA = {"nome": "", "entrada": "", "receita": "", "campo": "entrada", "padrao": "*.pdf", "estavel_s": 3.0,
                "ao_terminar": "nada", "processados": "", "falhas": "", "saida": "", "recursivo": False, "dados": {}}
PENDENTES = ("aguardando_confirmacao", "aguardando_seguranca")


def _resolver(caminho: str, base: pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(caminho).expanduser()
    return (p if p.is_absolute() else base / p).resolve()


def _normalizar(bruta: dict, indice: int) -> dict:
    p = {**PADRAO_PASTA, **{k: v for k, v in bruta.items() if v is not None}}
    p["nome"] = str(p["nome"] or f"pasta{indice + 1}")
    for campo in ("entrada", "receita"):
        if not p[campo]:
            raise PapiroErro("E_ENTRADA", f"pasta monitorada {p['nome']!r}: falta '{campo}' no papiro.toml")
    p["entrada"] = _resolver(p["entrada"], ROOT)
    if not any(CAM._dentro(p["entrada"], r) for r in CAM.raizes_entrada()):
        raise PapiroErro("E_POLITICA", f"pasta monitorada {p['nome']!r}: {p['entrada']} esta fora do PAPIRO; "
                                       "libere em [caminhos] liberadas no papiro.toml")
    receita = _resolver(p["receita"], REPO)
    if not receita.is_file() and ROOT != REPO:      # receita do usuario, ao lado dos dados
        receita = _resolver(p["receita"], ROOT)
    if not receita.is_file():
        raise PapiroErro("E_ENTRADA", f"pasta monitorada {p['nome']!r}: receita {p['receita']} nao existe "
                                      f"(procurei em {REPO} e em {ROOT})")
    p["receita"] = receita
    if p["ao_terminar"] not in ("nada", "mover"):
        raise PapiroErro("E_ENTRADA", f"pasta monitorada {p['nome']!r}: ao_terminar deve ser 'nada' ou 'mover'")
    p["processados"] = _resolver(p["processados"], ROOT) if p["processados"] else p["entrada"] / "processados"
    p["falhas"] = _resolver(p["falhas"], ROOT) if p["falhas"] else p["entrada"] / "falhas"
    p["saida"] = _resolver(p["saida"], ROOT) if p["saida"] else None
    p["estavel_s"] = max(0.0, float(p["estavel_s"]))
    p["recursivo"] = bool(p["recursivo"])
    if not isinstance(p["dados"], dict):
        raise PapiroErro("E_ENTRADA", f"pasta monitorada {p['nome']!r}: 'dados' deve ser uma tabela")
    return p


def pastas(nome: str = "") -> list[dict]:
    """Pastas monitoradas do papiro.toml, ja validadas (caminhos, receita e politica de confinamento)."""
    brutas = config.carregar().get("pastas", [])
    if isinstance(brutas, dict):
        brutas = [brutas]
    itens = [_normalizar(b, i) for i, b in enumerate(brutas)]
    nomes = [p["nome"] for p in itens]
    if len(set(nomes)) != len(nomes):
        raise PapiroErro("E_ENTRADA", "ha pastas monitoradas com o mesmo nome no papiro.toml")
    if nome:
        itens = [p for p in itens if p["nome"] == nome]
        if not itens:
            raise PapiroErro("E_ENTRADA", f"pasta monitorada {nome!r} nao esta no papiro.toml (tem: {', '.join(nomes) or 'nenhuma'})")
    return itens


def _candidatos(pasta: dict) -> list[pathlib.Path]:
    if not pasta["entrada"].is_dir():
        return []
    achados = pasta["entrada"].rglob("*") if pasta["recursivo"] else pasta["entrada"].glob("*")
    saida = []
    for p in sorted(achados):
        if not p.is_file() or p.name.startswith((".", "~$")) or p.suffix.lower() in SUFIXOS_IGNORADOS:
            continue
        if pasta["processados"] in p.parents or pasta["falhas"] in p.parents:
            continue
        if fnmatch.fnmatch(p.name.lower(), str(pasta["padrao"]).lower()):
            saida.append(p)
    return saida


def _estavel(arquivo: pathlib.Path, estavel_s: float) -> bool:
    """Arquivo parado ha tempo suficiente: evita pegar copia pela metade (rede, scanner, navegador)."""
    try:
        st = arquivo.stat()
    except OSError:
        return False
    return st.st_size > 0 and (time.time() - st.st_mtime) >= estavel_s


def _mover(arquivo: pathlib.Path, destino: pathlib.Path) -> str:
    """Move sem nunca sobrescrever (o original e intocavel: no maximo muda de pasta)."""
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / arquivo.name
    seq = 1
    while alvo.exists():
        alvo = destino / f"{arquivo.stem}_{seq}{arquivo.suffix}"
        seq += 1
    shutil.move(str(arquivo), str(alvo))
    return str(alvo)


def processar(pasta: dict, arquivo: pathlib.Path, reprocessar: bool = False) -> dict:
    """Roda a receita da pasta para um arquivo. Dedup por conteudo (SHA-256), estado em logs/jobs.db.

    Conteudo ja visto nao roda de novo, qualquer que tenha sido o resultado: um arquivo que falhou e continua na
    pasta (ao_terminar='nada') seria reprocessado a cada varredura, em laco. Ele fica listado em `estado()['falhas']`
    e so volta a rodar com reprocessar=true - de propriedade do usuario, nao do vigia."""
    sha = sha256_file(arquivo)
    anterior = JOBS.vigia_buscar(pasta["nome"], sha)
    if anterior and not reprocessar:
        return {"arquivo": str(arquivo), "sha256": sha, "status": "repetido", "execucao": anterior["execucao"],
                "visto_em": anterior["criado"], "resultado_anterior": anterior["status"]}
    t0 = time.time()
    JOBS.vigia_registrar(pasta["nome"], sha, str(arquivo), "executando")
    execucao = erro = movido = None
    try:
        rec, receita_sha = REC.carregar(pasta["receita"])
        dados = {**pasta["dados"], pasta["campo"]: str(arquivo)}
        rel = REC.executar(rec, receita_sha, dados=dados, out_base=pasta["saida"])
        status, execucao = rel["status"], rel["execucao"]
        erro = (rel.get("erro") or {}).get("code")
        saida_final, pendente = rel.get("saida_final"), rel.get("pendente")
    except PapiroErro as e:
        status, erro, saida_final, pendente = "falhou", e.codigo, None, None
    if pasta["ao_terminar"] == "mover" and status not in PENDENTES:
        movido = _mover(arquivo, pasta["processados"] if status == "concluido" else pasta["falhas"])
    segundos = round(time.time() - t0, 3)
    JOBS.vigia_registrar(pasta["nome"], sha, str(arquivo), status, execucao, erro, segundos, movido)
    return {"arquivo": str(arquivo), "sha256": sha, "status": status, "execucao": execucao, "erro": erro,
            "segundos": segundos, "movido": movido, "saida_final": saida_final, "pendente": pendente}


def _resumir(itens: list[dict]) -> dict:
    conta = {}
    for i in itens:
        conta[i["status"]] = conta.get(i["status"], 0) + 1
    return conta


def varredura(nome: str = "", reprocessar: bool = False, limite: int = 0) -> dict:
    """Uma passada: processa o que ja esta na pasta e ainda nao foi visto. Nao fica observando."""
    relatorio = {"pastas": [], "total": {}}
    feitos = 0
    for pasta in pastas(nome):
        itens = []
        for arquivo in _candidatos(pasta):
            if limite and feitos >= limite:
                break
            if not _estavel(arquivo, pasta["estavel_s"]):
                itens.append({"arquivo": str(arquivo), "status": "aguardando_copia"})
                continue
            r = processar(pasta, arquivo, reprocessar)
            itens.append(r)
            if r["status"] != "repetido":
                feitos += 1
        relatorio["pastas"].append({"nome": pasta["nome"], "entrada": str(pasta["entrada"]),
                                    "receita": pasta["receita"].name, "arquivos": itens, "resumo": _resumir(itens)})
    relatorio["total"] = _resumir([i for p in relatorio["pastas"] for i in p["arquivos"]])
    return relatorio


def vigiar(nome: str = "", intervalo: float = 5.0, tempo_limite: float = 0.0, ao_criar=None) -> dict:
    """Fica observando as pastas ate Ctrl+C (ou tempo_limite em segundos, usado nos testes).

    watchdog avisa na hora; a varredura periodica e a rede de seguranca para evento perdido ou copia lenta."""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    alvos = pastas(nome)
    fila: queue.Queue = queue.Queue()

    class Ouvinte(FileSystemEventHandler):
        def __init__(self, pasta: dict):
            self.pasta = pasta

        def _anotar(self, caminho: str, e_diretorio: bool):
            if not e_diretorio:
                fila.put((self.pasta, pathlib.Path(caminho)))

        def on_created(self, evento):
            self._anotar(evento.src_path, evento.is_directory)

        def on_modified(self, evento):
            self._anotar(evento.src_path, evento.is_directory)

        def on_moved(self, evento):
            self._anotar(evento.dest_path, evento.is_directory)

    observador = Observer()
    for pasta in alvos:
        pasta["entrada"].mkdir(parents=True, exist_ok=True)
        observador.schedule(Ouvinte(pasta), str(pasta["entrada"]), recursive=pasta["recursivo"])
    observador.start()
    inicio = time.time()
    resumo = {"pastas": [p["nome"] for p in alvos], "processados": [], "interrompido": False}
    espera: dict[tuple[str, str], tuple[dict, pathlib.Path]] = {}
    ultima_varredura = 0.0
    try:
        while not (tempo_limite and time.time() - inicio >= tempo_limite):
            try:
                pasta, arquivo = fila.get(timeout=0.5)
                espera[(pasta["nome"], str(arquivo))] = (pasta, arquivo)
            except queue.Empty:
                pass
            if time.time() - ultima_varredura >= intervalo:
                ultima_varredura = time.time()
                for pasta in alvos:
                    for arquivo in _candidatos(pasta):
                        espera.setdefault((pasta["nome"], str(arquivo)), (pasta, arquivo))
            for chave in list(espera):
                pasta, arquivo = espera[chave]
                if not arquivo.exists():
                    espera.pop(chave, None)
                    continue
                if not _estavel(arquivo, pasta["estavel_s"]):
                    continue
                espera.pop(chave, None)
                r = processar(pasta, arquivo)
                if r["status"] != "repetido":
                    resumo["processados"].append(r)
                    if ao_criar:
                        ao_criar(r)
    except KeyboardInterrupt:  # pragma: no cover - so no uso interativo
        resumo["interrompido"] = True
    finally:
        observador.stop()
        observador.join(timeout=5)
    resumo["segundos"] = round(time.time() - inicio, 3)
    resumo["resumo"] = _resumir(resumo["processados"])
    return resumo


def estado(nome: str = "", limite: int = 50) -> dict:
    """O que cada pasta monitorada ja viu, com as execucoes pendentes em destaque (RF-906 + §11)."""
    configuradas = pastas(nome)
    historico = JOBS.vigia_listar(nome, limite)
    return {"pastas": [{"nome": p["nome"], "entrada": str(p["entrada"]), "receita": p["receita"].name,
                        "padrao": p["padrao"], "ao_terminar": p["ao_terminar"], "existe": p["entrada"].is_dir(),
                        "na_fila": len([a for a in _candidatos(p) if not JOBS.vigia_buscar(p["nome"], sha256_file(a))])}
                       for p in configuradas],
            "historico": historico,
            "pendentes": [h for h in historico if h["status"] in PENDENTES],
            "falhas": [h for h in historico if h["status"] in ("falhou", "reprovado")]}
