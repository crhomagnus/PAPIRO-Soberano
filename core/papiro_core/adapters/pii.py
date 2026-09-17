# -*- coding: utf-8 -*-
"""Deteccao de dados pessoais PRD §12.3: reconhecedores proprios com digito verificador (CPF, CNPJ, CNS),
RG, CRM, telefone, e-mail, CEP, data de nascimento e nomes (Presidio + spaCy pt quando instalados;
heuristica por rotulo como fallback). Cada achado vem com pagina e caixa, para revisao e tarja."""
from __future__ import annotations
import pathlib, re
from functools import lru_cache
import fitz

CORES = {"CPF": (1, 0, 0), "CNPJ": (1, 0.4, 0), "CNS": (0.8, 0, 0.6), "RG": (0.6, 0.2, 0), "CRM": (0, 0.4, 1),
         "TELEFONE": (0, 0.6, 0.6), "EMAIL": (0, 0.5, 0), "CEP": (0.5, 0.5, 0), "DATA_NASCIMENTO": (0.4, 0, 0.8),
         "NOME": (1, 0, 1)}


def _digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def cpf_valido(s: str) -> bool:
    d = _digitos(s)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def cnpj_valido(s: str) -> bool:
    d = _digitos(s)
    if len(d) != 14 or d == d[0] * 14:
        return False
    for n, pesos in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]), (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        r = sum(int(d[i]) * pesos[i] for i in range(n)) % 11
        if (0 if r < 2 else 11 - r) != int(d[n]):
            return False
    return True


def cns_valido(s: str) -> bool:
    """Cartao Nacional de Saude: soma ponderada (15..1) multipla de 11."""
    d = _digitos(s)
    if len(d) != 15 or d[0] not in "126789":
        return False
    return sum(int(d[i]) * (15 - i) for i in range(15)) % 11 == 0


PADROES = [
    ("CPF", re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"), cpf_valido),
    ("CNPJ", re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"), cnpj_valido),
    ("CNS", re.compile(r"(?<!\d)[126789]\d{2}[ .]?\d{4}[ .]?\d{4}[ .]?\d{4}(?!\d)"), cns_valido),
    ("RG", re.compile(r"(?i)\b(?:RG|R\.G\.|identidade)\s*(?:n[ºo°.]*)?[:\s]*([\dXx][\dXx.\-]{4,13})"), None),
    ("CRM", re.compile(r"\bCRM\s*[-/]?\s*(?:[A-Z]{2}\s*[-/]?\s*)?\d{3,7}\b"), None),
    ("TELEFONE", re.compile(r"(?:\+?55\s?)?\(\d{2}\)\s?9?\d{4}[-\s]?\d{4}(?!\d)|(?<!\d)\d{2}\s9\d{4}-\d{4}(?!\d)"), None),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), None),
    ("CEP", re.compile(r"(?<![\d.])\d{5}-\d{3}(?![\d-])"), None),
    ("DATA_NASCIMENTO", re.compile(r"(?i)(?:nascid[oa]\s+em|nasc\.?|data\s+de\s+nascimento|DN)\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})"), None),
    ("NOME", re.compile(r"(?:Nome|Paciente|Sr\.|Sra\.|Dr\.|Dra\.)\s*:?\s*((?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)(?:\s+(?:d[aeo]s?|e)?\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)+)"), None),
]


@lru_cache(maxsize=1)
def _presidio():
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        conf = {"nlp_engine_name": "spacy", "models": [{"lang_code": "pt", "model_name": "pt_core_news_sm"}]}
        nlp = NlpEngineProvider(nlp_configuration=conf).create_engine()
        return AnalyzerEngine(nlp_engine=nlp, supported_languages=["pt"])
    except Exception:
        return None


def detectar_texto(texto: str, usar_presidio: bool = True) -> list[dict]:
    """[{categoria, texto, inicio, fim, motor}] sem sobreposicao."""
    achados = []
    for cat, rx, validar in PADROES:
        for m in rx.finditer(texto):
            grupo = 1 if m.groups() else 0
            valor = m.group(grupo)
            if validar and not validar(valor):
                continue
            achados.append({"categoria": cat, "texto": valor.strip(), "inicio": m.start(grupo),
                            "fim": m.end(grupo), "motor": "regex+dv" if validar else "regex"})
    motor_nomes = None
    if usar_presidio:
        eng = _presidio()
        if eng is not None:
            motor_nomes = "presidio+spacy-pt"
            for r in eng.analyze(text=texto, language="pt", entities=["PERSON"]):
                valor = texto[r.start:r.end].strip()
                if len(valor.split()) >= 2 and valor[:1].isupper():
                    achados.append({"categoria": "NOME", "texto": valor, "inicio": r.start, "fim": r.end,
                                    "motor": motor_nomes})
    achados.sort(key=lambda a: (a["inicio"], -(a["fim"] - a["inicio"])))
    unicos, fim_atual = [], -1
    for a in achados:
        if a["inicio"] >= fim_atual:
            unicos.append(a)
            fim_atual = a["fim"]
    return unicos


def detectar_pii(texto: str) -> dict:
    """Compatibilidade: categorias -> lista de valores."""
    out: dict[str, list[str]] = {c: [] for c in CORES}
    for a in detectar_texto(texto):
        out[a["categoria"]].append(a["texto"])
    return out


def detectar_pdf(entrada: pathlib.Path) -> list[dict]:
    achados = []
    with fitz.open(entrada) as doc:
        for page in doc:
            texto = page.get_text()
            for a in detectar_texto(texto):
                rects = page.search_for(a["texto"]) or []
                for r in rects:
                    achados.append({"pagina": page.number + 1, "categoria": a["categoria"], "texto": a["texto"],
                                    "motor": a["motor"], "x0": round(r.x0, 2), "y0": round(r.y0, 2),
                                    "x1": round(r.x1, 2), "y1": round(r.y1, 2)})
    return achados


def pdf_revisao(entrada: pathlib.Path, achados: list[dict], out: pathlib.Path) -> None:
    """§12.3 passo 2: caixas coloridas por categoria, sem remover nada (so para conferencia humana)."""
    with fitz.open(entrada) as doc:
        for a in achados:
            page = doc[a["pagina"] - 1]
            annot = page.add_rect_annot(fitz.Rect(a["x0"], a["y0"], a["x1"], a["y1"]))
            annot.set_colors(stroke=CORES.get(a["categoria"], (1, 0, 0)))
            annot.set_border(width=1.2)
            annot.set_info(title=a["categoria"])
            annot.update()
        doc.save(out, garbage=3, deflate=True)
