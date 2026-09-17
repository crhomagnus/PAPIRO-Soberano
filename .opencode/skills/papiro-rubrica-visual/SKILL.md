---
name: papiro-rubrica-visual
description: "Rubrica de crítica visual 0-10 do PAPIRO (PRD §10.3) para o portão G6."
---

# papiro-rubrica-visual

## Loop de crítica visual (PRD §10.3)
1. Renderizar as páginas em 110 DPI para visão geral e 300 DPI para recortes de detalhe.
2. Rodar heurísticas: transbordo de texto, blocos sobrepostos, margens violadas, contraste, imagens fracas, fontes ausentes, páginas vazias.
3. Aplicar a rubrica no `pdf-revisor-qa`, que roda em contexto separado do autor.
4. Corrigir e repetir, no máximo 3 ciclos; depois disso, mostrar as pranchas ao usuário.

| Critério da rubrica | Peso | O que é observado |
| --- | --- | --- |
| Hierarquia | 20% | O mais importante é percebido em 3 segundos |
| Tipografia | 20% | Escala, entrelinha, comprimento de linha, pares de fontes |
| Alinhamento e grid | 15% | Todo elemento encaixado na grade |
| Cor e contraste | 15% | Paleta coerente, WCAG 2.2 AA |
| Espaço em branco | 10% | Respiro e densidade adequados ao tipo de peça |
| Consistência | 10% | Componentes repetidos idênticos |
| Acabamento | 10% | Viúvas, órfãs, hifenização, nitidez de imagens |

## Como aplicar e registrar
1. `render_pages dpi=110 prancha=true` e abra as páginas (Read nos PNG); recortes a 300 DPI quando precisar de detalhe.
2. Dê nota 0-10 a cada critério; nota final = soma ponderada (pesos acima). Anote defeitos por página.
3. Registre no portão: `qa_run entrada=... design=true nota_visual=<nota>`. Sem `nota_visual`, peça de design fica
   `PENDENTE_REVISAO` - o G6 nunca aprova sozinho. Mínimo para aprovar: 8,0.
4. Quem aplica é o `pdf-revisor-qa`, em contexto separado do autor, e nunca corrige nada.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
