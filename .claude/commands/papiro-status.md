---
description: "Saúde do ambiente: motores, versões, perfil, disco, jobs e sucesso por motor (RNF-14)."
---

# /papiro-status

1. `engines` → bibliotecas e binários com versão, idiomas do Tesseract, perfil de hardware.
2. `jobs op=list limite=10` e `jobs op=stats` → fila e taxa de sucesso por motor.
3. Compare com `engines.lock.toml` e aponte divergências; espaço em disco pelo hook doctor.
Responda em uma tabela curta: presente/ausente/versão, sem inventar versão que não veio da ferramenta.
