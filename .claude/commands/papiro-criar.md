---
description: "Documento ou mala direta a partir de Markdown/HTML e dados."
argument-hint: "<modelo.md|texto> [dados.json|csv|xlsx]"
---

# /papiro-criar

- Documento: `compose motor=auto markdown=<conteúdo> titulo=... autor=...` (`padroes="a-2b"` para arquivo de longo prazo).
- HTML: `compose motor=html html=...`.
- Mala direta: `mail_merge markdown_tpl=<modelo com {{campo}}> dados_arquivo=<dados> modo=consolidado|um_por_registro`.
- Peça de design: `design=true` e revisão pelo pdf-revisor-qa. Templates RF-307 ainda não existem em `templates/`.
