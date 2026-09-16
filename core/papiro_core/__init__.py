# -*- coding: utf-8 -*-
"""PAPIRO SOBERANO core - caminhos, job-id, sha256, relogio."""
from __future__ import annotations
import hashlib, datetime, pathlib, os

ROOT = pathlib.Path(os.environ.get("PAPIRO_HOME", r"C:\PAPIRO"))
WORK = ROOT / "work"
OUT = ROOT / "out"
LOGS = ROOT / "logs"
KB = ROOT / "kb"

for d in (WORK, OUT, LOGS, KB):
    d.mkdir(parents=True, exist_ok=True)

def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def new_job_id() -> str:
    now = datetime.datetime.now()
    day = now.strftime("%Y-%m-%d")
    base = OUT / day
    base.mkdir(parents=True, exist_ok=True)
    existing = sorted(base.glob("*"))
    seq = len(existing) + 1
    return f"{day}-{seq:04d}"

def job_dirs(job_id: str) -> tuple[pathlib.Path, pathlib.Path]:
    w = WORK / job_id
    o = OUT / job_id[:10] / job_id[11:]
    w.mkdir(parents=True, exist_ok=True)
    (w / "in").mkdir(exist_ok=True)
    o.mkdir(parents=True, exist_ok=True)
    return w, o

def utcnow_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")
