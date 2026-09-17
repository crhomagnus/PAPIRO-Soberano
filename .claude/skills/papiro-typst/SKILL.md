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

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
