---
description: "OCR com camada invisível e saída PDF/A, pt-BR padrão (RF-601)."
argument-hint: "<arquivo|pasta>"
---

# /papiro-ocr
1. `inspect op=pages entrada=$ARGUMENTS` - veja quais páginas são escaneadas (`tem_camada_texto=false`).
2. `ocr entrada=$ARGUMENTS out_dir=out/<data>/<job> idioma=por pdfa=true` - só as páginas sem texto recebem OCR
   (OCRmyPDF `--skip-text`; fallback: Tesseract direto, palavra a palavra, com fonte embutida).
3. Conferir `dados.paginas_ocr` e `qa.status`. PDF/A: se o OCRmyPDF não fechar o PDF/A, rode `conform op=pdfa`.
4. Pasta inteira: repetir por arquivo (lotes paralelos RF-905 ainda não implementados).
