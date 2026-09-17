---
name: papiro-ocr
description: "OCR no PAPIRO: motor por perfil, camada invisível, PDF/A e comando /papiro-ocr <arquivo>."
---

# papiro-ocr

## Comando /papiro-ocr $ARGUMENTS
1. `inspect op=pages entrada=$ARGUMENTS` - veja quais páginas são escaneadas (`tem_camada_texto=false`).
2. `ocr entrada=$ARGUMENTS out_dir=out/<data>/<job> idioma=por pdfa=true` - só as páginas sem texto recebem OCR
   (OCRmyPDF `--skip-text`; fallback: Tesseract direto, palavra a palavra, com fonte embutida).
3. Conferir `dados.paginas_ocr` e `qa.status`. PDF/A: se o OCRmyPDF não fechar o PDF/A, rode `conform op=pdfa`.
4. Pasta inteira: repetir por arquivo (lotes paralelos RF-905 ainda não implementados).

## Motor por perfil (PRD §9.2, linhas de OCR)
| Situação | Motor | Fallback |
| --- | --- | --- |
| Escaneado simples, perfil P0 | OCRmyPDF + Tesseract | Tesseract direto (RapidOCR não instalado) |
| Escaneado com tabelas e fórmulas | PaddleOCR-VL (P1-P3) / Docling (P0) | não instalados: E_SEM_SUPORTE |

## Estado real
Linux: Tesseract 4.1.1 com por, eng e osd; OCRmyPDF 17.12.1. Pré-processamento (deskew/clean) não é exposto pela
ferramenta. `forcar=true` refaz OCR em todas as páginas. RNF-04: A4 a 300 DPI em até 4 s por página.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
