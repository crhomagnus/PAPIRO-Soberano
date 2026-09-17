---
description: "Assinatura PAdES ICP-Brasil, sempre com confirmação explícita."
argument-hint: "<arquivo>"
---

# /papiro-assinar

Se veio de uma receita pausada (`aguardando_seguranca`), use `dados.pendente.argumentos_sugeridos` e retome a receita
com `externos_json` depois. Delegue ao subagente `pdf-seguranca` (único com o servidor papiro-seguranca). Antes: `qa_run` precisa estar
APROVADO; mostre ao usuário o resumo do documento e peça confirmação explícita. Nunca peça PIN ou senha no chat:
a senha do PFX vem por `senha_ref` e o PIN do token por `pin_ref` (`env:`, `keyring:` ou `prompt`, digitado no terminal).
Siga a skill `papiro-assinatura-icp`. Depois, `verify` e relatório ao usuário.

- **A1 (arquivo):** `pfx=<.pfx> senha_ref="env:NOME"`.
- **A3 (token/cartão):** `token="<rótulo>" modulo="<biblioteca PKCS#11>" pin_ref="prompt"`. Não sabe o rótulo?
  Rode `papiro token` (lista tokens e certificados). Um token só conectado dispensa `token=`; vários exigem escolher.
  Erro de PIN gasta tentativa e o token bloqueia depois de poucas — confirme com o usuário antes de repetir.
