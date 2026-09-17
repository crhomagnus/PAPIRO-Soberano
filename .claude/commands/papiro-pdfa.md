---
description: "Converter e validar PDF/A (RF-801)."
argument-hint: "<arquivo> [PDF/A-2b|2u|3b|...]"
---

# /papiro-pdfa

1. `inspect op=fonts` e `inspect op=risk` (JavaScript e anexos impedem PDF/A-2).
2. `conform op=pdfa entrada=<arquivo> padrao=<nível, padrão PDF/A-2b>` → só entrega se o veraPDF aprovar.
3. Se reprovar, leia `error.message`/regras, corrija (`fonts op=embed`, `sanitize` via pdf-seguranca) e repita.
