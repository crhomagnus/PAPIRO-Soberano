---
name: papiro-html-print
description: "HTML/CSS para PDF com Chromium headless no PAPIRO (tags, marcadores, mídia paginada)."
---

# papiro-html-print

## Uso
- `compose motor=html html="<html lang='pt-BR'>..."` ou `capture op=web url=...`.
- O Chromium é chamado com `--headless=new --no-pdf-header-footer --generate-pdf-document-outline --print-to-pdf`:
  PDF marcado (tags), marcadores a partir de h1..h6, fontes embutidas com ToUnicode.
- `<html lang="pt-BR">` vira `/Lang` - obrigatório para o G7.
- CSS de mídia paginada: `@page { size: A4; margin: 2cm }`, `break-before/after`, `orphans`/`widows`.
- `capture op=web` acessa a rede: proibido em job sensível (hook soberania) e não remove banners de cookies.
- Recursos remotos no HTML também são baixados: em documento de paciente, use só recursos locais ou data URI.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
