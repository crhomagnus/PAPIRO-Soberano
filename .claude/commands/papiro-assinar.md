---
description: "Assinatura PAdES ICP-Brasil, sempre com confirmação explícita."
argument-hint: "<arquivo>"
---

# /papiro-assinar

Se veio de uma receita pausada (`aguardando_seguranca`), use `dados.pendente.argumentos_sugeridos` e retome a receita
com `externos_json` depois. Delegue ao subagente `pdf-seguranca` (único com o servidor papiro-seguranca). Antes: `qa_run` precisa estar
APROVADO; mostre ao usuário o resumo do documento e peça confirmação explícita. Nunca peça PIN ou senha no chat:
a senha vem por `senha_ref`. Siga a skill `papiro-assinatura-icp`. Depois, `verify` e relatório ao usuário.
