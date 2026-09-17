---
name: papiro-pdfa-pdfua
description: "PDF/A e PDF/UA no PAPIRO: requisitos, fluxo, validação veraPDF e falhas comuns (PRD §11.2/§11.3)."
---

# papiro-pdfa-pdfua

## PDF/A (PRD §11.2)
- **Padrões por uso:** PDF/A-2b para arquivo geral; 2u quando a busca por texto precisa de Unicode garantido; 3b quando há anexo, como XML; PDF/A-4 para PDF 2.0.
- **Fluxo:** gerar nativo quando possível, já que o Typst cobre todas as partes do PDF/A ([docs do Typst](https://typst.app/docs/reference/pdf/)); converter os existentes via Ghostscript; validar sempre no veraPDF.
- **Correções automáticas:** fonte não embutida volta a ser embutida; transparência em A-1 sobe para A-2; falta de OutputIntent ganha sRGB; Info e XMP divergentes são sincronizados; JavaScript e anexos proibidos são removidos.

## PDF/UA (PRD §11.3)
- **Criação:** tags ligadas por padrão. Com PDF/UA-1 ativo, o Typst recusa exportar quando falta texto alternativo, o que funciona como portão ([blog do Typst](https://typst.app/blog/2025/accessible-pdf/)).
- **PDF/UA-2:** via LuaLaTeX. Segundo a equipe do Quarto, o LaTeX já gera UA-2 e o Typst deve ganhar suporte ainda em 2026 ([Quarto](https://quarto.org/docs/blog/posts/2026-03-05-pdf-accessibility-and-standards/)).
- **Validação:** veraPDF cobre as checagens de máquina; um checklist humano baseado no Protocolo Matterhorn cobre ordem de leitura, qualidade do texto alternativo e uso de cor.
- **Remediação de PDF sem tags:** reconstrução — extrair a estrutura com Docling, regenerar em Typst com a mesma aparência, validar e comparar por SSIM. Tagueamento direto no arquivo original fica como recurso experimental.

## Ferramentas reais
- Documento novo: `compose motor=typst padroes="a-2b"` (ou `ua-1`) - nativo, validado no veraPDF pelo G9.
- Documento existente: `conform op=pdfa padrao="PDF/A-2b"` → Ghostscript com OutputIntent sRGB; só é entregue se o
  veraPDF 1.30.2 aprovar (senão E_CONFORMIDADE com as regras reprovadas).
- Validar qualquer arquivo: `validate padrao="PDF/A-2b"` (ou `PDF/UA-1`).
- Falha observada de verdade: cláusula 6.6.4 (XMP sem esquema de identificação PDF/A) em PDF comum declarado como A-2b.
- Sem suporte ainda: `conform op=pdfua` (remediação) e PDF/UA-2 (LuaLaTeX ausente).

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
