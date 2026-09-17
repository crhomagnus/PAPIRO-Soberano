---
name: papiro-preflight
description: "Preflight próprio de produção gráfica (PDF/X) do PAPIRO e como corrigir (PRD §11.4)."
---

# papiro-preflight

## Preflight próprio (PRD §11.4)
- O Ghostscript gera PDF/X-1a, X-3 e X-4 ([docs do Ghostscript](https://ghostscript.readthedocs.io/en/latest/VectorDevices.html)).
- O veraPDF valida PDF/A e PDF/UA, não PDF/X. Por isso o PAPIRO implementa um preflight próprio, com relatório em PDF que marca os problemas sobre as páginas.

| Checagem do preflight | Regra |
| --- | --- |
| Caixas | TrimBox e BleedBox presentes e coerentes com a sangria |
| OutputIntent | Perfil ICC de saída declarado |
| Espaços de cor | Sem RGB em X-1a; spots com nomes padronizados |
| Cobertura de tinta | Máximo por pixel dentro do limite do perfil |
| Resolução | Imagens ≥ 300 DPI efetivos |
| Fontes | Todas embutidas |
| Preto | Texto preto em 100% K com sobreimpressão |
| Transparência | Ausente em X-1a |
| Linhas finas | Nenhuma abaixo de 0,25 pt |
| Texto pequeno | Sem cor composta abaixo de 8 pt |

## Ferramenta e correções
- `preflight entrada=... padrao=PDF/X-4|PDF/X-3|PDF/X-1a limite_tinta=300` → `falhas` por regra e página.
- Caixas: `pages op=boxes caixas_json='{"TrimBox":[...],"BleedBox":[...]}'` (aninhamento conferido).
- Fontes: `fonts op=embed`. RGB → `color op=cmyk` (perfil padrão; peça o ICC da gráfica).
- Imagens < 300 DPI: substituir por original melhor (`images op=replace`); ampliar por IA só com aviso.
- Sobreimpressão do preto não é verificável automaticamente: conferir no RIP da gráfica.
- Conversão para PDF/X pelo Ghostscript ainda não está implementada (`conform op=pdfx` → E_SEM_SUPORTE).

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
