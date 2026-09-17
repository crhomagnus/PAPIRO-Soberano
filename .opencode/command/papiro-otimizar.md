---
description: "Compressão por perfil com meta de tamanho, sem perder fidelidade (RF-902/903)."
argument-hint: "<arquivo> [tela|email|impressao|arquivo] [meta_mb]"
---

# /papiro-otimizar

1. `optimize entrada=<arquivo> perfil=<perfil, padrão email> meta_mb=<meta> linearizar=<true se for para web>`.
2. O PAPIRO só entrega candidato com texto idêntico e SSIM (pior bloco) acima do limiar do perfil; sem candidato
   fiel e menor, entrega versão sem perda e avisa. Informe antes/depois, redução, motor e avisos de meta.
