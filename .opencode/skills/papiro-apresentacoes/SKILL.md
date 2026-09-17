---
name: papiro-apresentacoes
description: "Apresentações no PAPIRO (PRD §10.6): narrativa, uma ideia por slide, handouts."
---

# papiro-apresentacoes

## Regras (PRD §10.6)
- Uma ideia por slide, título em forma de afirmação, até 30 palavras por slide (ajustável).
- Temas Touying gerados dos tokens; 16:9 padrão e 4:3 opcional.
- Texto mínimo de 18 pt, contraste AA e nada fora da área segura.
- Saídas: PDF de apresentação, PDF de handout, PNG por slide e PPTX de imagens com notas.
- Notas no formato pdfpc, apresentação em dois monitores com pympress.

## Estado real
Touying, pympress e pdfpc não estão instalados: não há ferramenta de deck (RF-501..506 → sem suporte). Alternativa
honesta: `compose motor=typst` com uma página por slide (16:9 via Markdown não é suportado automaticamente) ou
`office_to_pdf` de um PPTX existente (um slide por página). Handout: `pages op=nup por_folha=2|4|6`.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
