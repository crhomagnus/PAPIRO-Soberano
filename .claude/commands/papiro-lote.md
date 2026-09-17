---
description: "Processamento em lote com uma receita (para_cada + paralelo) ou uma operação."
argument-hint: "<receita|operação> <pasta>"
---

# /papiro-lote

- Com receita: um passo com `para_cada: $dados.arquivos` e `paralelo: N` (até 8) processa a lista em processos separados,
  com checkpoint por execução (`recipes op=run`, retomada com `execucao=<id>`). Exemplo: `recipes/lote-certificados.yaml`.
- Liste os arquivos da pasta e passe como `dados_json='{"arquivos": [...]}'`; referência no passo: `entrada: $item`.
- Formulários: `forms op=fill_batch`; cartas e documentos: `mail_merge` (1.000 registros sem erro).
- Pastas monitoradas (RF-906): ligue pasta e receita em `papiro.toml` (`[[pastas]]`) e rode `papiro vigiar`
  (contínuo, watchdog) ou `recipes op=watch` / `papiro vigiar --uma-vez` (uma passada). `recipes op=watch_status`
  mostra fila, pendentes e falhas. A pasta nunca assina nem tarja sozinha: passo sensível fica pendente para o usuário.
- Agendamento (RF-907): use o Agendador do Windows chamando `papiro vigiar --uma-vez` (cada execução fica no log).
- Via terminal, sem LLM: `python -m papiro_core.cli chamar recipes '{"op": "run", "arquivo": "...", "dados_json": "..."}'`.
