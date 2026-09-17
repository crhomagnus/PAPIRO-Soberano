---
description: "Gestão de receitas YAML: listar, validar (e rodar quando o executor existir)."
argument-hint: "listar|validar|rodar [arquivo]"
---

# /papiro-receita

- listar: `recipes op=list`.
- validar: `recipes op=validate arquivo=<receita.yaml>` (JSON Schema).
- rodar: `recipes op=run` ainda é E_SEM_SUPORTE - execute os passos à mão seguindo a skill `papiro-receitas`.
