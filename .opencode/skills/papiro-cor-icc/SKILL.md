---
name: papiro-cor-icc
description: "Cor, perfis ICC, CMYK, cobertura de tinta e contraste WCAG no PAPIRO (PRD §10.5)."
---

# papiro-cor-icc

## Pré-impressão (PRD §10.5)
| Item | Regra padrão | Ferramenta |
| --- | --- | --- |
| Sangria | 3 mm, ajustável | Typst + pdfimpose |
| Marcas de corte e registro | Fora da área de sangria | pdfimpose |
| Cor | CMYK com o perfil ICC da gráfica; sem perfil informado, FOGRA39 ou FOGRA51 da ECI | Ghostscript |
| Cobertura total de tinta | Limite do perfil, medido por pixel | Ghostscript `tiffsep` + cálculo próprio |
| Preto de texto | 100% K com sobreimpressão | Preflight próprio |
| Imagens | ≥ 300 DPI efetivos | Preflight próprio |
| Fontes | Todas embutidas | Preflight próprio |
| Formato final | PDF/X-4 por padrão; X-1a quando a gráfica exigir | Ghostscript |
| Imposição | Livreto grampeado, 2-up, n-up, corte e empilhamento | pdfimpose |
| Prova de cor em tela | Simulação do perfil de saída | LittleCMS |

## Ferramentas reais
- `color op=gray|cmyk` (Ghostscript). CMYK usa o perfil padrão do Ghostscript - não é FOGRA: para gráfica peça o ICC.
- `preflight padrao="PDF/X-4" limite_tinta=300` mede cobertura por pixel (conversão CMYK sem ICC, aproximada).
- Contraste WCAG 2.2: texto normal ≥ 4,5:1; texto grande ≥ 3:1 (checagem manual na rubrica: sem ferramenta dedicada).

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
