---
description: "Relatório de nível 0 (RF-001 a RF-009) de um PDF."
argument-hint: "<arquivo.pdf>"
---

# /papiro-inspecionar

1. `inspect op=all entrada=$ARGUMENTS out_dir=out/<data>/<job>`.
2. `render_pages entrada=$ARGUMENTS dpi=60 prancha=true` para a prancha de contato.
3. Resuma: páginas, versão, tags, idioma, fontes não embutidas/sem ToUnicode, imagens abaixo de 150 DPI, páginas
   escaneadas sem OCR, revisões após assinatura e nota de risco com evidências. Nada de alterar o arquivo.
