# HANDOFF — PAPIRO SOBERANO · Sessão 2026-09-17 (executor de receitas + templates RF-307)

> Continuação de `HANDOFF_SESSAO_2026-09-16_CORRECOES.md`. Tudo abaixo foi medido nesta sessão (17/09/2026, 07:53–09:00 -03)
> no clone Linux `~/PAPIRO-Soberano`. O que não foi medido está marcado como **não verificado**.

## 1. Pedido
"implemente o executor de receitas e os templates RF-307 e logo em seguida faça o commit total para o github".

## 2. Templates RF-307 (16) — `templates/<categoria>/<nome>/`
| Categoria | Templates |
| --- | --- |
| medico | `receituario-a5` (simples ou controle especial em 2 vias), `atestado-a5`, `pedido-exame-a5`, `encaminhamento-a4` |
| negocios | `relatorio-a4`, `proposta-a4`, `contrato-a4`, `one-pager-a4`, `cartao-visita` (85×55 mm) |
| marketing | `catalogo-a4`, `cardapio-a4`, `folder-a4-3dobras`, `cartaz-a3` |
| editorial | `apostila-a4`, `ebook-a5` |
| eventos | `certificado-a4` (QR + código de verificação) |

- Cada pasta: `template.typ` (Typst 0.15, função `documento` via `#show`), `schema.json` (JSON Schema 2020-12 — dados
  validados antes de compilar), `exemplo.json` (**fictício**), `meta.toml` (papel, design, padrões, título, notas legais) e
  `referencia.png` (teste visual). Base comum em `templates/_base/base.typ`; brand kit em `brandkits/padrao/tokens.yaml`
  (formato do PRD §10.1).
- `core/papiro_core/templates.py`: listar/resolver (id ou prefixo), validar, preparar (data, números por extenso com
  concordância de gênero, QR com segno, cópia de logos/imagens só de caminhos permitidos), projeto Typst isolado e
  **fonte ausente = erro** (o Typst só avisaria e cairia em fallback silencioso — erro de origem da REGRA 01).
- Integração MCP: `compose template=... dados_json|dados_arquivo|usar_exemplo marca=...`; `mail_merge template=...`
  (consolidado ou um por registro); recurso `papiro://templates` com os metadados; `papiro://brandkits`.
- **Resultado medido:** os 9 documentos saem **APROVADOS** nos 11 portões; os 4 médicos também no **veraPDF como PDF/A-2b e
  PDF/UA-1 ao mesmo tempo**; as 7 peças de design passam em todos os portões técnicos e ficam `PENDENTE_REVISAO` até a nota
  do pdf-revisor-qa (G6), como manda o PRD. Revisão visual feita página a página: 6 defeitos de diagramação encontrados e
  corrigidos (cardápio em uma coluna só, contraste do cartaz, hifenização no título do folder, one-pager subdimensionado,
  selo sem acento, QR sobre o texto do certificado, selo da 1ª via quebrando o título).
- **RF-304 medido:** mala direta de **1.000 atestados sem erro em 58,2 s** (1.000 páginas, QA APROVADO).
- **Regras legais conferidas em fonte oficial nesta sessão:**
  - Resolução CFM 1.658/2002 (redação da 1.851/2008), texto do CFM: art. 3º (tempo de dispensa; diagnóstico só autorizado;
    emissor com CRM), art. 4º §2º (documento de identidade no atestado), art. 5º parágrafo único (concordância expressa no
    atestado) → viraram campos obrigatórios e regras do schema do atestado.
  - Portaria SVS/MS 344/1998, art. 52 (cópia oficial da SES-DF, lida por OCR do próprio PAPIRO): duas vias com os dizeres
    "1ª via – Retenção da Farmácia ou Drogaria" / "2ª via – Orientação ao Paciente", quantidade em algarismos e por extenso,
    validade de 30 dias para C1 e C5 → receituário de controle especial.
  - **Não verificado:** o modelo gráfico do ANEXO XVII. Os blocos de comprador/fornecedor seguem os campos que o art. 36
    descreve para a Notificação de Receita.

## 3. Executor de receitas (PRD §9.3) — `core/papiro_core/receitas.py`
- **Validação:** JSON Schema + ids únicos + ferramentas existentes, antes de rodar; entrada `dados` validada no esquema
  declarado (ex.: `templates/medico/atestado-a5/schema.json`).
- **Checkpoints:** estado por passo em `logs/jobs.db` (`receita_execucoes`, `receita_passos`); `run execucao=<id>` retoma do
  passo exato (mesma receita e mesmos dados, conferidos por hash).
- **Cache por hash:** ferramenta + argumentos + SHA-256 dos arquivos de entrada; saídas conferidas por hash antes de
  reaproveitar. Medido: receita do atestado 21,2 s → **2,2 s** na segunda execução (3 passos em cache).
- **Asserções `exige`:** `ok`, `qa`, `verapdf`, `erro`, `paginas` (">=1") ou caminho no envelope.
- **Fluxo:** `se` (sem eval), `para_cada` com `$item`/`$indice`, `paralelo: N` (processos separados via CLI); referências
  `$dados.x`, `$<passo>.saida`, `$<passo>.saidas`, `$execucao`, `$data`; passo sem `entrada` usa o PDF do anterior.
- **Confirmação:** `confirmacao: obrigatoria` pausa (E_POLITICA) até `confirmados=<id>`.
- **Isolamento de segurança:** passos `papiro-seguranca.*` nunca rodam no executor — ele pausa (`aguardando_seguranca`)
  devolvendo ferramenta, argumentos sugeridos e como retomar; retoma com `externos_json`. Testado de ponta a ponta com
  assinatura PAdES real (certificado de teste autoassinado) no meio da receita do receituário.
- **Sensível:** `sensivel: true` mantém `work/_sensivel.flag` (hook soberania) até a execução terminar; `op=cancel` encerra
  uma pausa e desliga a trava.
- **Vocabulário do PRD aceito:** `padroes_pdf`, `dados: $dados`, `validadores: [verapdf, qpdf]`, `rubrica` (vira aviso).
- **RF-908:** `recipes op=save job_ids=... nome=...` gera YAML dos jobs concluídos (o runner agora grava os argumentos de
  cada job — segredos nunca, conteúdo longo só como hash, caminhos só como hash em modo sensível — e as saídas). A receita
  gerada roda. **Não verificado:** reprodução do mesmo hash de saída (RNF-10).
- Receitas prontas: `recipes/atestado-pdfa.yaml`, `recipes/lote-certificados.yaml`, `recipes/exemplo-receituario-assinado.yaml`
  (a do PRD, agora apontando para o schema real do template).
- Outras mudanças: G9 e `validate` aceitam vários padrões ("PDF/A-2b,PDF/UA-1"); o executor único ganhou `erro` explícito
  no `Resultado`.

## 4. Testes
`core/tests/test_templates.py` (16 templates: exemplo, portões, regressão visual contra `referencia.png`; travas legais;
extenso; fonte ausente; imagens; compose/mail_merge) e `core/tests/test_receitas.py` (validação, atestado + cache,
receituário com confirmação → assinatura real → verificação → saída final, cancelamento, lote paralelo com `se`, `exige`,
retomada após queda simulada, RF-908, condições e referências).
**Rodada completa final (17/09/2026 08:50): 145 testes passando, 0 falhas, cobertura 87%** (4.532 linhas; eram 107 testes e 86%).

## 5. Continua NÃO implementado
tradução com layout (RF-608) · texto alternativo por visão (RF-609) · decks Touying (RF-501..506) · pastas monitoradas e
agendamento (RF-906/907) · A3/PKCS#11, carimbo do tempo, LTV · Docling/PaddleOCR-VL · `conform` pdfua/pdfx/remediate ·
XFDF de anotações · criação/detecção de campos (RF-701/702) · gráfico Vega-Lite (RF-305) · conversão para docx/epub/dxf ·
embeddings no RAG · Tesseract 5 no Linux · RNF-10 (mesmo hash) e RNF-12 **não verificados** · Windows não testado.

## 6. Retomar daqui
1. `cd ~/PAPIRO-Soberano && git log --oneline -3`.
2. Testes: `cd core && ~/.local/share/lancadores-claude/papiro-soberano/venv312/bin/python -m pytest -q --cov=papiro_core`.
3. Criar documento: `compose motor=auto template=medico/atestado-a5 dados_json=...` ou `recipes op=run arquivo=recipes/atestado-pdfa.yaml`.
4. Template novo: pasta com os 5 arquivos, revisão visual, `referencia.png` e teste.
5. Próximos itens de maior valor: A3/PKCS#11 (assinatura com token) → pastas monitoradas RF-906 → Vega-Lite RF-305.
