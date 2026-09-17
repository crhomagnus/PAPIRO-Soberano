---
description: "Gestão de receitas YAML: listar, validar, rodar, retomar, cancelar e salvar tarefa como receita."
argument-hint: "listar|validar|rodar|retomar|status|cancelar|salvar [arquivo|execucao|job_ids]"
---

# /papiro-receita

- listar: `recipes op=list` · validar: `recipes op=validate arquivo=<receita.yaml>`.
- rodar: `recipes op=run arquivo=<receita.yaml> dados_json=<dados>`; leia `dados.passos` e `dados.pendente`.
- retomar: `recipes op=run arquivo=... dados_json=<mesmos dados> execucao=<id>`; passo com confirmação só com
  `confirmados=<id>` DEPOIS da confirmação explícita do usuário; passo de segurança: delegue ao `pdf-seguranca` e retome
  com `externos_json`.
- status: `recipes op=status execucao=<id>` · cancelar: `recipes op=cancel execucao=<id>`.
- salvar: `recipes op=save job_ids="<id1>,<id2>" nome=<nome>` (RF-908). Detalhes na skill `papiro-receitas`.
