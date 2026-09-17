---
name: papiro-formularios
description: "Formulários AcroForm no PAPIRO: preencher, lote, exportar, achatar, XFA e máscaras brasileiras."
---

# papiro-formularios

## Ferramenta `forms`
- `op=list` (campos, tipo, valor, opções) · `op=detect_xfa`.
- `op=fill dados_json='{"nome":"João","aceite":true}'` → aparência regenerada, acentos preservados; campos inexistentes
  voltam em `warnings`.
- `op=fill_batch dados_arquivo=dados.csv|json|xlsx campo_nome=nome` → um PDF por registro.
- `op=export formato=json|csv|fdf|xfdf` · `op=import_xfdf xfdf=arquivo.xfdf` (ida e volta).
- `op=flatten` → campos queimados no conteúdo, AcroForm removido, aparência conferida por SSIM (RF-705/RF-207).
- XFA: só a camada AcroForm é preenchida, com aviso explícito (RF-706). Criar/detectar campos (RF-701/702): sem suporte.

## Máscaras brasileiras (validar antes de preencher)
- CPF `000.000.000-00` com dígito verificador · CNPJ `00.000.000/0000-00` com DV · CEP `00000-000`
- Data `dd/mm/aaaa` · Telefone `(00) 00000-0000` · CNS 15 dígitos (soma ponderada múltipla de 11).

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
