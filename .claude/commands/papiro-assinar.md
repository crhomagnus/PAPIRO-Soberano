---
description: "Assinatura PAdES ICP-Brasil, sempre com confirmação explícita."
argument-hint: "<arquivo>"
---

# /papiro-assinar

Delegue ao subagente `pdf-seguranca` (único com o servidor papiro-seguranca). Antes: `qa_run` precisa estar
APROVADO; mostre ao usuário o resumo do documento e peça confirmação explícita. Nunca peça PIN ou senha no chat:
a senha vem por `senha_ref`. Siga a skill `papiro-assinatura-icp`. Depois, `verify` e relatório ao usuário.
