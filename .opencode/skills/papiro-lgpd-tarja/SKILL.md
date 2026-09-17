---
name: papiro-lgpd-tarja
description: "Categorias de dados pessoais e fluxo de revisão do tarjamento LGPD. SÓ O USUÁRIO invoca."
disable-model-invocation: true
---

# papiro-lgpd-tarja

## Tarjamento para LGPD (PRD §12.3)
1. **Detectar:** Presidio com modelo spaCy português e reconhecedores próprios com dígito verificador (CPF, CNPJ, CNS), além de RG, CRM, telefone, e-mail, CEP, data de nascimento e nomes.
2. **Propor:** PDF de revisão com caixas coloridas por categoria.
3. **Aprovar:** o usuário confirma, ajusta ou descarta cada tarja.
4. **Aplicar:** remoção real de texto, imagem e vetores sob a área; em escaneados, OCR antes e tarja na imagem.
5. **Verificar:** extrair o texto de novo e confirmar a ausência; limpar metadados e anexos; nomear o arquivo sem dado pessoal.

Retângulo preto desenhado por cima, sem remoção, é proibido.

## Ferramentas reais (papiro-seguranca, só no pdf-seguranca)
1. `redact_detect entrada=...` → `caixas.json` (categoria, texto, página, caixa, motor) + `revisao_tarja.pdf` com
   caixas coloridas. Reconhecedores: CPF/CNPJ/CNS com dígito verificador, RG, CRM, telefone, e-mail, CEP, data de
   nascimento, nomes (Presidio + spaCy pt_core_news_sm e rótulos "Nome:", "Paciente:", "Dr(a).").
2. Mostre a revisão ao usuário; ele aprova, ajusta ou descarta cada caixa (edite o JSON).
3. `redact_apply entrada=... caixas_arquivo=aprovadas.json confirm=true` → remoção real (texto, pixels de imagem e
   vetores), re-extração que prova a ausência, metadados/XMP/anexos limpos, nome de saída sem dado pessoal.
Escaneado: rode `ocr` antes para que o texto seja detectável; a tarja remove os pixels da imagem sob a caixa.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
