# PAPIRO Soberano

> Agente Autônomo Especialista em Engenharia Documental + Agente Soberano de PDF via CLI.
> Fusão fiel de 2 projetos canônicos em `docs/`: `AGENTE_AUTONOMO_ENGENHARIA_PDF.md` (seções I–LXXX)
> e `PAPIRO_PRD_ORIGINAL.md` (88 RFs, 23 RNFs). Em dúvida, leia `docs/` linha por linha — eles mandam.

**Repo:** https://github.com/crhomagnus/PAPIRO-Soberano · **Branch:** `master` · **Núcleo:** `core/papiro_core` (Python ≥3.12)

Estado medido em 17/09/2026 (auditoria): **184 testes, cobertura 87%** — a suíte completa acusou 2 falhas do LTV inacabado,
corrigidas em seguida, com os 41 testes dos arquivos afetados verdes (ver `HANDOFF_SESSAO_2026-09-17_A3_PASTAS.md` §4).
Windows ainda **não testado** — código portátil (RNF-17), validação feita no Linux.

## O que é

Transformar qualquer pedido documental em solução completa, executável, validada e pronta para uso:

```
PESQUISAR → ENTENDER → PLANEAR → EXECUTAR → VERIFICAR → CORRIGIR → VALIDAR → ENTREGAR → APRENDER
```

Princípios: prova antes de promessa (`qa-report.json` APROVADO), original intocável (nunca sobrescreve entrada),
motor certo para cada trabalho com fallback, local e gratuito por padrão, determinismo (receitas reproduzíveis),
visão no loop.

Fora de escopo absoluto: quebrar senha sem senha legítima, falsificar documentos/assinaturas/carimbos/datas,
dependência paga obrigatória, GUI própria.

## Capacidades (PRD §6 — 88 RFs)

* **N0 Inspeção:** inventário JSON, fontes fsType/ToUnicode, DPI real, digital/escaneada/híbrida, thumbs, busca regex com coords, idioma pt-BR, revisões pós-assinatura, triagem de risco RF-009.
* **N1 Páginas:** merge/split/extract/reorder/invert/interleave, rotate+OSD, boxes, resize, n-up/livreto/pôster, marcadores/links, anexos com hash, branco zero-FP.
* **N2 Edição:** carimbo por âncora, replace preservando fonte, watermark OCG, header/footer/Bates, anotação XFDF, flatten real, OCG, imagem, Info+XMP+Lang.
* **N3 Criação:** Markdown→Typst, HTML→Chromium com tags, Office→LibreOffice, mala direta 1.000 registros (medido 58,2 s), longos com sumário, 16 templates RF-307, web sem cookies, fotos OpenCV+img2pdf, QR decodificável.
* **N4 Design:** tokens→typ+css, grid ≤0,5 pt, WCAG 4.5:1, rubrica ≥8/10, vetor sempre, 2–3 variações, pré-impressão CMYK+ICC/PDF-X.
* **N5 Slides:** Touying (parcial — ver pendências).
* **N6 Inteligência:** OCR invisível por página (OCRmyPDF paralelo + Tesseract), tabelas XLSX com conferência, Pydantic, resumo com página, RAG lexical FTS5 + evidências, diff texto+estrutura+visual, alt-text, rubricas.
* **N7 Formulários:** AcroForm import/export JSON/CSV/FDF/XFDF, flatten trava, XFA best-effort.
* **N8 Conformidade:** PDF/A-1b,2b,2u,3b,3u,4,4f via GS+veraPDF, UA-1/UA-2 (parcial), X-1a/X-3/X-4 via preflight próprio, AES-256, PAdES B-B (A1/PFX via pyHanko; A3/PKCS#11 pendente), tarja real irrecuperável (Presidio+spaCy pt + CPF/CNPJ/CNS/RG/CRM), sanitização completa.
* **N9 Operação:** reparo em cascata qpdf→pikepdf→GS→PyMuPDF→render, perfis tela/e-mail/impressão/arquivo, linearize, embutir fontes, receitas YAML com checkpoints/cache/retomada (RF-908), sentinela mensal.

## Arquitetura (§4 — 6 camadas)

```
L1 Host (Claude Code / OpenCode) → L2 Orquestrador `papiro-soberano` → L3 12 subagentes
→ L4 MCP FastMCP stdio (38 papiro + 10 papiro-seguranca isolado) → L5 papiro-core → L6 motores
```

Job: `intake → work/<job>/in (ro) → plano → execução SHA-256 → QA até 3 ciclos → out/<data>/<job> + qa-report.md/json + audit.jsonl (só hashes)`.

* **12 subagentes:** inspetor, operador, editor, compositor, designer, apresentador, extrator, formulários, conformidade, segurança (isolado, `permissionMode` default), revisor-qa (sem Write/Edit), sentinela.
* **MCP §8:** 38 tools `papiro` + 10 `papiro-seguranca`. Envelope `ok/job_id/outputs/engine/metrics/warnings/qa/audit_id`. Erros `E_ENTRADA/E_SENHA/E_CORROMPIDO/E_MOTOR/E_TEMPO/E_CONFORMIDADE/E_POLITICA/E_SEM_SUPORTE`.
* **QA §11:** 11 portões G1 qpdf+pdfcpu, G2 pypdfium2, G3 pdffonts+ToUnicode, G4 OCR, G5 heurísticas, G6 revisor ≥8, G7 metadados pt-BR, G8 tamanho, G9 veraPDF+preflight, G10 triagem, G11 SSIM pior bloco.
* **9 hooks:** doctor, contexto, guarda-originais (bloqueia), confirma-sensível (bloqueia), soberania (bloqueia rede), valida-saída, pede-revisão, salva-estado, portão-final (bloqueia sem QA aprovado).

## Templates RF-307 (16)

| Categoria | Templates |
|---|---|
| medico | `receituario-a5` (simples ou controle especial 2 vias, Port. 344/1998 art. 52), `atestado-a5` (CFM 1.658/2002), `pedido-exame-a5`, `encaminhamento-a4` |
| negocios | `relatorio-a4`, `proposta-a4`, `contrato-a4`, `one-pager-a4`, `cartao-visita` 85×55 mm |
| marketing | `catalogo-a4`, `cardapio-a4`, `folder-a4-3dobras`, `cartaz-a3` |
| editorial | `apostila-a4`, `ebook-a5` |
| eventos | `certificado-a4` (QR + código) |

Cada pasta: `template.typ` + `schema.json` + `exemplo.json` (fictício) + `meta.toml` + `referencia.png`. Base em `templates/_base/base.typ`, brand kit em `brandkits/padrao/tokens.yaml`.

## Início rápido

### Windows (C:\PAPIRO)

```powershell
cd C:\PAPIRO
# 1. Motores: winget/Scoop/uv/Node + Ghostscript, qpdf, pdfcpu, Typst, Poppler, Tesseract por, LibreOffice, JDK21, veraPDF, Playwright Chromium, Ollama
.\bin\bootstrap.ps1
# 2. Núcleo
cd core; uv sync --extra dev; .venv\Scripts\python -m pytest -q
# 3. Usar
opencode --auto --model opencode/muse-spark-1.3-contributor-free --agent papiro-soberano
```

### Linux (~/PAPIRO-Soberano)

```bash
cd ~/PAPIRO-Soberano
cd core && python3.12 -m pytest -q --cov=papiro_core
# criar: compose motor=auto template=medico/atestado-a5 dados_json=...
# receita: recipes op=run arquivo=recipes/atestado-pdfa.yaml
```

Config: `papiro.toml` (perfil P0–P3, `liberadas`, limiares SSIM, `ocr_paralelo`, raízes ICP-Brasil).
Motores com versão+hash em `engines.lock.toml`. Escrita sempre só em `work/` e `out/` — hook `guarda-originais` bloqueia o resto.

## Layout

```
bin/ core/papiro_core/{adapters,cli,runner,receitas,templates,qa,mcp_server}.py core/tests/
.claude/{agents/papiro,commands,hooks,skills} .opencode/{agent,command,skills} templates/ recipes/
brandkits/ fonts/ (Liberation OFL) models/tessdata/ docs/ kb/ corpus/ work/ out/ logs/
papiro.toml engines.lock.toml opencode.json .mcp.json AGENTS.md HANDOFF_*.md
```

## Documentos de sessão

* `HANDOFF_SESSAO_2026-09-16_PAPIRO-SOBERANO.md` — handoff original (superado).
* `HANDOFF_SESSAO_2026-09-16_CORRECOES.md` — varredura que provou defeitos + correção total (107 testes, cobertura 86%).
* `HANDOFF_SESSAO_2026-09-17_RECEITAS_TEMPLATES.md` — executor de receitas + 16 templates (145 testes, cobertura 87%).
* `HANDOFF_SESSAO_2026-09-17_A3_PASTAS.md` — assinatura A3 (PKCS#11), pastas monitoradas RF-906, carimbo do tempo RFC 3161 e LTV.
* `TRANSCRICAO_COMPLETA_SESSAO_2026-09-16.md` — transcrição.
* `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md` + `docs/PAPIRO_PRD_ORIGINAL.md` — fontes canônicas.

## Pendente / não verificado

Tradução com layout (RF-608) · alt-text por visão (RF-609) · decks Touying (RF-501–506) · Docling/PaddleOCR-VL · `conform` pdfua/pdfx/remediate · XFDF · campos RF-701/702 · Vega-Lite RF-305 · docx/epub/dxf · embeddings RAG · RNF-10 (mesmo hash) e RNF-12 sem verificação · **Windows não testado**.

**Implementado, mas sem homologação:** assinatura A3 (PKCS#11) provada com token de software SoftHSM2, nunca com token ICP-Brasil real; carimbo do tempo provado contra TSA RFC 3161 local, nunca contra ACT credenciada; LTV (B-LT/B-LTA) provado com PKI de teste. **Falta popular `certs/icp-brasil` com as ACs raiz da ICP-Brasil** — sem elas o `verify` nunca marca `confiavel` e o LTV recusa por não conseguir fechar a cadeia. Homologação final em `validar.iti.gov.br`.

## Segurança e conformidade

Assinatura/tarja só com confirmação explícita. PAdES proíbe assinar reprovado no QA, gravar PIN ou senha em log (só `env:`/`keyring:`). Tarja real remove texto+imagem+vetor e re-extrai para conferir — retângulo preto proibido. Sanitiza JS/OpenAction/Launch/anexos/XFA/XMP/thumbs; triagem RF-009. Logs só com hashes. Documentos médicos seguem CFM 1.658/2002 e 2.299/2021 — homologação ITI/CFM a cada troca de motor.

## Licença

MIT — ver `LICENSE`. Fontes Liberation sob OFL 1.1 (`fonts/LICENSE-OFL-1.1.txt`).
