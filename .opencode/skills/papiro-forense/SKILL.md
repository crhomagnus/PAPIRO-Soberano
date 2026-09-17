---
name: papiro-forense
description: "Forense de PDF no PAPIRO: revisões incrementais, cobertura de assinatura, triagem de risco."
---

# papiro-forense

## Ferramentas
- `inspect op=revisions` → cada revisão (marcadores %%EOF) com data declarada e objetos adicionados/removidos/alterados;
  assinaturas com `cobre_ate` (fim do ByteRange) e `alterado_apos_assinatura`. Arquivo linearizado tem 2 marcadores
  e só 1 revisão - o relatório desconta.
- `verify` (papiro-seguranca, só no pdf-seguranca) → integridade, cobertura (ENTIRE_FILE/ENTIRE_REVISION),
  nível de modificação e signatário; sem âncoras ICP-Brasil em `certs/icp-brasil`, `confiavel` é sempre falso.
- `inspect op=risk` → JavaScript, Launch, AA, OpenAction com ação, URI, anexos, XFA, RichMedia, com evidência por objeto;
  nota ALTA/MÉDIA/BAIXA. Arquivo de origem desconhecida passa por aqui antes de qualquer processamento (§12.4).
- `compare a b` → texto, estrutura e SSIM, com PDF marcado nas regiões alteradas.

## Anomalias a relatar
Revisão após assinatura; objetos alterados sem mudança de data; fontes trocadas entre revisões; JavaScript em PDF
de laudo; anexos não declarados; datas de criação posteriores à modificação.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
