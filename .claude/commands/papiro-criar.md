---
description: "Documento ou mala direta a partir de template RF-307, Markdown ou HTML e dados."
argument-hint: "<template|modelo.md|texto> [dados.json|csv|xlsx]"
---

# /papiro-criar

- Template (16 prontos, ver recurso `papiro://templates`): `compose motor=auto template=<id> dados_json=<dados>`; para
  conhecer os campos, leia `templates/<id>/schema.json` ou gere com `usar_exemplo=true`. Dados inválidos voltam E_ENTRADA
  com o campo exato.
- Documento livre: `compose motor=auto markdown=<conteúdo> titulo=... autor=...` (`padroes="a-2b"` para arquivo).
- HTML: `compose motor=html html=...`.
- Mala direta: `mail_merge template=<id> dados_arquivo=<dados> modo=consolidado|um_por_registro campo_nome=<campo>`
  ou `mail_merge markdown_tpl=<modelo com {{campo}}>`.
- Peça de design (certificado, catálogo, cardápio, one-pager, cartão, folder, cartaz): revisão pelo pdf-revisor-qa com
  nota ≥ 8 (`nota_visual`) antes da entrega.
