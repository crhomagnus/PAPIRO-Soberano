# HANDOFF — PAPIRO SOBERANO · Sessão de correção 2026-09-16 (Linux, Claude Code Opus 5)

> Substitui as afirmações de estado do `HANDOFF_SESSAO_2026-09-16_PAPIRO-SOBERANO.md` (sessão opencode/Windows).
> Tudo abaixo foi **medido** nesta sessão (16/09/2026, 21:13–23:30 -03) no clone `~/PAPIRO-Soberano`.
> O que não foi medido está marcado como **não verificado**.

## 1. Por que esta sessão existiu
Uma varredura com provas empíricas mostrou que o handoff anterior declarava pronto o que não funcionava:
portões de QA que nunca reprovavam (G2, G3, G6 com nota 8,0 fixa, G7, G9), otimizador que destruía imagens,
sanitização que só removia anexos, flatten que não achatava, OCR que ignorava página escaneada em PDF misto,
RAG que citava sempre a página 1, `job_id` repetido, `papiro-seguranca` sem registro em nenhum host,
subagentes sem restrição de ferramentas e hooks inativos no Linux. O pedido do Márcio: corrigir tudo.

## 2. Antes × agora (mesmos arquivos de teste da varredura)
| Prova | Antes | Agora |
| --- | --- | --- |
| PDF com fonte não embutida | QA **APROVADO** | REPROVADO (G3) |
| Página em branco | "0 em branco" | detectada (página 1) |
| Peça de design sem rubrica | APROVADO, nota 8,0 fixa | PENDENTE_REVISAO / REPROVADO; aprova só com `nota_visual` ≥ 8 |
| Sem idioma / sem produtor | G7 ok | G7 reprova |
| PDF com hyperlink | REPROVADO (G10) | G10 ok; JavaScript/Launch reprovam |
| Documentos totalmente diferentes (G11) | 0,976 ≥ 0,9 aprovava | SSIM pior bloco 0,521 → reprova |
| `otimizar` (e-mail) | imagem preta, SSIM 0,74 | −98,2%, SSIM pior bloco 0,967, texto idêntico |
| `sanitizar` | JS, AA, Launch, XMP ficavam | tudo removido; triagem RF-009 BAIXA (autor visível mantido só se `manter_metadados_basicos=true`) |
| `flatten` | campo continuava editável | 0 campos; aparência conferida por SSIM |
| Marca d'água | ValueError (rotate=45) | camada OCG "Marca d'agua" |
| Remover branco em página só vetorial | apagava | mantém (zero falso positivo) |
| `compose` Markdown | linha cortada em 110 chars, travessão perdido, QA REPROVADO | Typst, texto completo, QA APROVADO |
| Mala direta | ignorava o modelo | "Prezado Ana, sua consulta é em 01/10." |
| OCR em PDF misto | página escaneada sem OCR, "ok" | só a página 2 recebe OCR; texto reconhecido |
| Dados pessoais | CPF, CNPJ, e-mail, telefone | + CNS (DV), RG, CRM, CEP, nascimento, nomes (Presidio + spaCy pt) |
| RAG | página 1 sempre | página correta + PDF de evidências destacadas |
| `job_id` em 3 chamadas | igual nas 3 | únicos (SQLite atômico) |
| merge com QA reprovado | `ok: true` | `ok: false`, E_CONFORMIDADE |
| Extração de anexo | PdfError em qualquer anexo | ok; nome `../../X` saneado, nada escapa do out_dir |
| Tags / ToUnicode / revisões | sempre falso / sempre verdadeiro / não detectava | medidos de verdade |
| Cobertura de testes (RNF-19) | 29% | 86% (107 testes, incluindo os 9 hooks; 0 falhas) |

RNFs medidos agora: RNF-01 inventário 100 p em 1,0 s (≤ 2) · RNF-02 merge 1000 p em 0,37 s (≤ 15) ·
RNF-03 render 110 DPI a 25,9 p/s (≥ 10) · RNF-04 OCR A4 300 DPI 3,28 s/p com OCRmyPDF e 3,65 s/p com Tesseract
direto (≤ 4) · RNF-05 Typst 26 páginas em 1,2 s (≤ 3). QA completo de 20 páginas: 2,7 s.

## 3. O que mudou no código (`core/papiro_core`)
- **Novo núcleo comum:** `runner.py` (executor único: job-id, confinamento de caminhos, cópia somente leitura das
  entradas em `work/<job>/in`, `dry_run`, QA, envelope §8.1, estatística por motor), `caminhos.py` (entradas só na raiz
  ou pastas liberadas; escrita só em `work/` e `out/`; nunca sobrescreve), `erros.py`, `config.py` (`papiro.toml`),
  `roteador.py` (§9: pontuação qualidade × compatibilidade × histórico − custo; registro de motores separado),
  `fidelidade.py` (SSIM de Wang com OpenCV, média e pior bloco), `jobs.py` (SQLite: jobs, contador, estatística,
  checkpoints de receita), `audit.py` (JSONL **só com hashes**, sem caminho nem nome de arquivo).
- **Adaptadores reescritos:** `inspect`, `pages` (+ duplicar, mover, inverter, intercalar, resize, boxes, n-up, livreto,
  rótulos, reparo em cascata qpdf→pikepdf→GS→PyMuPDF→render, otimização com candidatos PyMuPDF/GS, linearização
  conferida no qpdf, embutir fontes + ToUnicode), `edit` (carimbo por âncora, QR, marca OCG, cabeçalho/rodapé/Bates,
  replace preservando corpo/cor e fonte quando possível, Info+XMP+Lang, tarja com re-extração), `create` (Markdown→Typst
  com strings literais, Story como fallback, HTML/web via Chromium com tags, mala direta JSON/CSV/XLSX, Office, fotos
  com retificação OpenCV, QR decodificado de volta, diagrama Graphviz vetorial), `convert` (txt/md/json/png/svg/xlsx/csv,
  tabelas com conferência entre pdfplumber e PyMuPDF, formulários com import/export JSON/CSV/FDF/XFDF, flatten real,
  AES-256, sanitização completa), `intel` (OCR por página com OCRmyPDF paralelo e fallback Tesseract, RAG FTS5/BM25),
  `pii` (novo), `conform` (novo: PDF/A via GS + veraPDF; preflight PDF/X §11.4), `qa` (G1–G11 conforme §11.1 +
  qa-report.json/.md com miniaturas marcadas), `compare` (texto, estrutura, SSIM, PDF marcado).
- **Servidores MCP:** `mcp_server.py` (38 ferramentas = PRD §8.3, + recursos e prompts §8.5) e `mcp_seguranca.py`
  (10 = §8.4; assinatura PAdES-B-B e certificação com A1/PFX via pyHanko; verificação local; confirmação obrigatória;
  senha só por referência `env:`/`keyring:`; documento reprovado não assina; aparência nunca sobre o conteúdo).
- **CLI:** `python -m papiro_core.cli status | ferramentas | chamar <ferramenta> '<json>' | inspecionar | ocr | ...`.
- **Testes:** `core/tests/` (conftest com corpus sintético; fumaça 20; regressão de cada defeito da varredura;
  contrato das 48 ferramentas; segurança com certificado autoassinado; CLI; núcleo; 9 hooks).

## 4. Fiação
- **Linux (lançador `~/.local/share/lancadores-claude/papiro-soberano/`, backup em `backup-2026-09-16/`):**
  venv **Python 3.12.13** em `venv312` (o `venv` 3.10 antigo ficou intacto); `sessao.sh` passa
  `--settings .claude/settings.linux.json` (9 hooks Python ativos) e o aviso de ambiente foi corrigido;
  `agentes_json.py` preserva ferramentas, proibições, modelo, permissionMode, skills, memória e o MCP embutido
  (formato **lista**, o único que a CLI 2.1.274 aceita).
  **Teste ao vivo (claude -p):** sessão principal com 38 ferramentas papiro e nenhuma de segurança; `pdf-seguranca` vê as
  10; `pdf-revisor-qa` sem Write/Edit/Bash; `pdf-inspetor` em Haiku 4.5 sem Write.
- **Agentes:** `.claude/agents/papiro/*.md` no formato do PRD §7.1 (Claude Code). `.opencode/agent(s)/` seguem no formato
  opencode; `pdf-seguranca` ganhou `tools: papiro-seguranca*: true` e `opencode.json` registra o servidor com
  `"tools": {"papiro-seguranca*": false}` (validado contra o schema oficial; **não executado no opencode**).
- **Hooks:** `.claude/hooks/papiro_hooks.py` (os 9 do §7.4) + `.claude/settings.linux.json`. No Windows,
  `.claude/settings.json` ganhou o registro do `soberania.ps1`, que faltava (**não testado no Windows**).
- **Skills e comandos:** 16 skills com as seções do PRD copiadas verbatim e as chamadas reais; 15 comandos
  (no Claude Code o `/papiro-ocr` é a própria skill `papiro-ocr`, fim da colisão de nomes).

## 5. Motores (versões e hashes em `engines.lock.toml`)
Projeto, em `bin/linux-x86_64/` (fora do git): Typst 0.15.1, qpdf 12.4.1, pdfcpu 0.15.0, Ghostscript 10.08.0
(compilado), veraPDF 1.30.2. Sistema: Tesseract 4.1.1 (por/eng/osd), LibreOffice 7.3.7.2, Poppler 22.02, Java 17,
Chrome 149, Graphviz. Python: OCRmyPDF 17.12.1, pyHanko 0.37, Presidio 2.2.364 + spaCy pt_core_news_sm 3.8, OpenCV 5.0.
Fontes OFL em `fonts/` (Liberation, fsType 0, licença incluída).

## 6. Continua NÃO implementado (a ferramenta responde `E_SEM_SUPORTE` com alternativa)
> **Atualização 17/09/2026:** executor de receitas, 16 templates RF-307, brand kit e RF-908 foram implementados — ver `HANDOFF_SESSAO_2026-09-17_RECEITAS_TEMPLATES.md`.
tradução com layout (RF-608) · texto alternativo por visão (RF-609) · decks Touying/handout com notas (RF-501..506) ·
16 templates RF-307 e brand kits · executor de receitas (§9.3; `recipes run`) · lotes paralelos com retomada, pastas
monitoradas e agendamento (RF-905..907) · A3/PKCS#11, carimbo do tempo, LTV (RF-806 parcial) · Docling/PaddleOCR-VL
(RF-602/603 estrutural) · `conform` pdfua/pdfx/remediate · XFDF de anotações · criação/detecção de campos (RF-701/702) ·
remoção de camada OCG · gráfico Vega-Lite · conversão para docx/epub/dxf · embeddings no RAG (é lexical FTS5) ·
Tesseract 5 no Linux (há 4.1.1) · RNF-12 (pip-audit semanal) **não verificado**.

## 7. Windows
Nada foi executado no Windows. O código é portátil (raiz = pasta do repositório, `binfinder` com `bin\*.exe` e Program
Files), mas o `venv` do Windows precisa das dependências novas do `core/pyproject.toml` (incluindo `mcp<2`).
**Não verificado:** hooks .ps1, opencode com `papiro-seguranca`, agentes Claude Code no Windows.

## 8. Retomar daqui
1. `cd ~/PAPIRO-Soberano && git log --oneline -3` — correções no commit `bf681ac`, enviado ao GitHub em 17/09/2026 por ordem do Márcio.
2. Testes: `cd core && ~/.local/share/lancadores-claude/papiro-soberano/venv312/bin/python -m pytest -q --cov=papiro_core`.
3. Sessão: ícone "PAPIRO Soberano Opus 5 (YOLO)" (usa a fiação nova).
4. Próximos itens de maior valor: executor de receitas → templates RF-307 (receituário/atestado) → A3/PKCS#11 →
   lotes RF-905.
