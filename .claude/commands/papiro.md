---
description: "Entrada principal do PAPIRO para qualquer tarefa de PDF ou documento."
argument-hint: "<pedido livre>"
---

# /papiro

Pedido: $ARGUMENTS

1. `jobs op=route pedido="$ARGUMENTS"` → tarefa e motores pontuados; skill `papiro-roteamento` para a tabela.
2. Se houver arquivo, `inspect op=all` antes de qualquer operação (e `inspect op=risk` se a origem for desconhecida).
3. Delegue ao subagente do nível (pdf-inspetor, pdf-operador, pdf-editor, pdf-compositor, pdf-designer,
   pdf-apresentador, pdf-extrator, pdf-formularios, pdf-conformidade, pdf-seguranca, pdf-revisor-qa, pdf-sentinela).
4. Toda saída em `out/<data>/<job>` (ou `work/`); nunca sobre a entrada.
5. Entrega só com `qa.status=APROVADO`; peça de design passa pelo pdf-revisor-qa (nota ≥ 8). Máximo 3 ciclos.
