# -*- coding: utf-8 -*-
"""N6 - OCR, parsing, RAG minimo, deteccao PII. RF-601/602/604/605/606/608(parcial)."""
from __future__ import annotations
import pathlib, re, shutil, sqlite3, subprocess
import fitz
from .. import binfinder as BF

CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")

CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
TEL = re.compile(r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}")

def ocr(entrada: pathlib.Path, out: pathlib.Path, idioma: str = "por") -> dict:
    """RF-601: OCRmyPDF+Tesseract se presentes; senao verifica camada texto (E_SEM_SUPORTE p/ scan puro)."""
    import os
    ocrmypdf = shutil.which("ocrmypdf")
    tess = BF.qual("tesseract")
    env = dict(os.environ)
    env.update(BF.env_extra())
    if tess:
        env["PATH"] = str(pathlib.Path(tess).parent) + os.pathsep + env.get("PATH", "")
    if ocrmypdf:
        r = subprocess.run([ocrmypdf, "-l", idioma, "--output-type", "pdfa", str(entrada), str(out)],
                           capture_output=True, text=True, timeout=600, env=env)
        if r.returncode == 0:
            return {"ok": True, "via": "ocrmypdf"}
    doc = fitz.open(entrada)
    chars = sum(len(p.get_text().strip()) for p in doc)
    doc.close()
    if chars > 100:
        # ja tem texto: copia e declara camada ok
        shutil.copyfile(entrada, out)
        return {"ok": True, "via": "texto-nativo", "aviso": "sem OCR: PDF ja pesquisavel"}
    raise RuntimeError("E_SEM_SUPORTE: scan sem texto e sem OCRmyPDF/Tesseract instalado.")

def detectar_pii(texto: str) -> dict:
    """Base do RF-808 detectar."""
    return {"cpf": CPF.findall(texto), "cnpj": CNPJ.findall(texto),
            "emails": EMAIL.findall(texto), "telefones": TEL.findall(texto)}

def texto_completo(entrada: pathlib.Path) -> str:
    doc = fitz.open(entrada)
    t = "\n".join(p.get_text() for p in doc)
    doc.close()
    return t

# ---------- RAG minimo (RF-606 simplificado: SQLite FTS, sem embeddings) ----------
def rag_index(db: pathlib.Path, doc_id: str, texto: str, pagina_ini: int = 1):
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS docs(id TEXT, pagina INT, texto TEXT)")
    # chunk por ~2000 chars
    for i in range(0, len(texto), 2000):
        con.execute("INSERT INTO docs VALUES(?,?,?)", (doc_id, pagina_ini, texto[i:i+2000]))
    con.commit()
    con.close()

def rag_ask(db: pathlib.Path, pergunta: str, limite: int = 5) -> list[dict]:
    termos = [t for t in re.findall(r"\w{3,}", pergunta.lower()) if len(t) > 2][:6]
    if not termos or not db.exists():
        return []
    con = sqlite3.connect(db)
    where = " OR ".join("lower(texto) LIKE ?" for _ in termos)
    rows = con.execute(f"SELECT id, pagina, substr(texto,1,400) FROM docs WHERE {where} LIMIT ?",
                       tuple(f"%{t}%" for t in termos) + (limite,)).fetchall()
    con.close()
    return [{"doc": r[0], "pagina": r[1], "trecho": r[2]} for r in rows]
