---
description: "Processamento em lote de uma pasta com uma operação ou receita."
argument-hint: "<receita|operação> <pasta>"
---

# /papiro-lote

Lotes paralelos com retomada (RF-905) e pastas monitoradas (RF-906) ainda não estão implementados. Faça em série:
liste os PDFs da pasta, chame a ferramenta para cada um com `out_dir` próprio, acompanhe com `jobs op=list` e
consolide um relatório com ok/erro por arquivo. Para formulários use `forms op=fill_batch`; para cartas, `mail_merge`.
Via terminal: `python -m papiro_core.cli chamar <ferramenta> '<json>'` roda sem LLM.
