---
name: papiro-typst
description: "Padrões do Typst 0.15 no PAPIRO: compose, PDF/A e PDF/UA nativos, fontes embutidas."
---

# papiro-typst

## Uso
- `compose motor=typst markdown=... titulo=... autor=...` → Markdown convertido para Typst com cada trecho de texto
  como string literal (`#"..."`): nenhum caractere do usuário vira marcação.
- Padrões: `padroes="a-2b"` (ou `a-2u`, `a-3b`, `ua-1`, combinados por vírgula) → `typst compile --pdf-standard` e
  o G9 valida no veraPDF. PDF/UA-1 recusa exportar imagem sem texto alternativo (isso é portão, não erro).
- Fontes: só as de `fonts/` (`--font-path fonts --ignore-system-fonts`) - Liberation Sans/Serif/Mono, OFL, fsType 0.
  Isso garante G3 (embutidas com ToUnicode) e o mesmo resultado no Windows e no Linux.
- Metadados: `#set document(title, author)` + `#set text(lang: "pt", region: "br")` → /Lang pt-BR; o PAPIRO grava
  o Producer (G7).
- Hifenização pt-BR repete o hífen na quebra ("FIM-" / "-DA-LINHA") - é a regra do português, não defeito.
- Sem Typst instalado, `motor=auto` cai para PyMuPDF Story e o envelope traz `engine.fallback_from`.
- RNF-05: relatório de 20 páginas em até 3 s.

## Templates RF-307 (templates/<categoria>/<nome>)
- 16 prontos: medico/receituario-a5, atestado-a5, pedido-exame-a5, encaminhamento-a4; negocios/relatorio-a4,
  proposta-a4, contrato-a4, one-pager-a4, cartao-visita; marketing/catalogo-a4, cardapio-a4, folder-a4-3dobras,
  cartaz-a3; editorial/apostila-a4, ebook-a5; eventos/certificado-a4. Lista com metadados: recurso `papiro://templates`.
- Cada um: `template.typ` (função `documento` via `#show`), `schema.json` (dados validados antes de compilar),
  `exemplo.json` (fictício), `meta.toml` (papel, design, padrões, título, notas legais) e `referencia.png` (teste visual).
- Uso: `compose motor=auto template=<id ou prefixo> dados_json=... | dados_arquivo=... | usar_exemplo=true marca=padrao`.
- Brand kit: `brandkits/<marca>/tokens.yaml` (cores, tipografia, logos). Fonte que não está em `fonts/` = erro (nada de
  fallback silencioso).
- Médicos saem em PDF/A-2b + PDF/UA-1 (validados no veraPDF). Peças de design ficam PENDENTE_REVISAO até a nota do revisor.
- Novo template: pasta com os 5 arquivos acima; rode os testes (`core/tests/test_templates.py`) e gere a referência.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
