# HANDOFF — PAPIRO SOBERANO · Sessão 2026-09-17 (assinatura A3 + pastas monitoradas + carimbo do tempo)

> Continuação de `HANDOFF_SESSAO_2026-09-17_RECEITAS_TEMPLATES.md`. Tudo abaixo foi medido nesta sessão
> (17/09/2026, 18:00–20:30 -03) no clone Linux `~/PAPIRO-Soberano`. O que não foi medido está marcado como
> **não verificado**.

## 1. Pedido
"implemente a assinatura A3 e as pastas monitoradas" e, em seguida, "implemente o carimbo do tempo (TSA)".

## 2. Assinatura A3 — token ou cartão via PKCS#11 (RF-806, PRD §12.1)
- `sign` e `certify` (servidor `papiro-seguranca`) agora aceitam **duas credenciais**: A1 (`pfx=` + `senha_ref=`,
  como antes) e **A3** (`token=` rótulo, `modulo=` biblioteca PKCS#11, `pin_ref=`, e `rotulo=`/`id_chave=`/`slot=`
  para escolher o certificado). O arquivo `core/papiro_core/mcp_seguranca.py` abre a sessão no token, assina e
  **fecha a sessão sempre** (`_abrir_credencial`); a chave privada nunca sai do token.
- **PIN:** `env:NOME`, `keyring:servico/usuario` ou `prompt` (digitado no terminal, `getpass`, só com TTY).
  Nunca é argumento, nunca é gravado. O `runner` passou a excluir do plano do job qualquer argumento com "pin"
  (já excluía "senha") — há teste que varre `logs/jobs.db` e `logs/audit.jsonl` provando que nem o PIN nem a
  referência dele aparecem.
- **Descoberta:** `papiro token` (CLI) lista tokens conectados (rótulo, fabricante, série) e os certificados de cada
  um (rótulo, id, titular, emissor, validade). Sem isso não há como saber o que passar em `token=`/`rotulo=`.
- **Facilidades e erros úteis:** com um único token conectado, `token=` é dispensável; com vários, o erro lista os
  rótulos. Certificado inexistente ou ambíguo → erro listando os disponíveis. PIN errado → `E_SENHA` avisando que o
  token bloqueia depois de poucas tentativas; token ausente → `E_ENTRADA`; módulo inexistente → `E_ENTRADA`.
  Tudo dentro do envelope §8.1 (nenhuma exceção escapa).
- **Módulo PKCS#11:** argumento > `PAPIRO_PKCS11_MODULO` > `papiro.toml [assinatura] pkcs11_modulo` > caminhos usuais
  (SafeNet `eTPKCS11.dll`, Watchdata `WDPKCS.dll`, SafeSign `aetpkss1.dll`, OpenSC, SoftHSM).
- **Como foi testado:** token de software **SoftHSM2** (mesma interface PKCS#11 de um eToken ICP-Brasil), com
  certificado de teste autoassinado. Medido: assinatura **íntegra e válida** na verificação local do pyHanko, com
  aparência visível (recusada quando cairia sobre o conteúdo), `certify` DocMDP, e A1 sem regressão.
  `pip install "pyhanko[pkcs11]"` (python-pkcs11 0.9.5) foi acrescentado ao venv; `softhsm2` e `opensc` instalados
  no sistema **apenas para teste** (os testes se pulam sozinhos onde eles não existirem).
- **Não verificado:** token A3 real ICP-Brasil (não tenho o token aqui), comportamento no Windows, carimbo do tempo
  (TSA), LTV B-LT/B-LTA e o fallback JSignPdf — continuam sem suporte, como antes.

## 3. Pastas monitoradas (RF-906) — `core/papiro_core/vigia.py`
- Um bloco `[[pastas]]` no `papiro.toml` liga **uma pasta a uma receita**: `nome`, `entrada`, `receita`, `campo`
  (o dado que recebe o caminho do arquivo), `padrao`, `estavel_s`, `ao_terminar`, `processados`, `falhas`, `saida`,
  `recursivo` e `dados` fixos. A configuração é conferida na carga: pasta fora do PAPIRO → `E_POLITICA` mandando
  liberar em `[caminhos] liberadas`; receita ausente, `ao_terminar` inválido e nomes repetidos → `E_ENTRADA`.
- **Dois modos:** `papiro vigiar` fica observando (watchdog + varredura periódica de segurança, que pega evento
  perdido e cópia lenta) e `papiro vigiar --uma-vez` / `recipes op=watch` fazem uma passada — é a forma indicada
  para o Agendador do Windows (RF-907). `recipes op=watch_status` / `papiro vigiar --estado` mostram fila,
  pendentes e falhas.
- **Cuidados que estão no código:** só processa arquivo que parou de crescer (`estavel_s`, para não pegar cópia pela
  metade); ignora `.part`, `.tmp`, `.crdownload`, ocultos e o que não casa com `padrao`; **não repete** o mesmo
  conteúdo (dedup por SHA-256 em `logs/jobs.db`, tabela `vigia_arquivos`) — nem quando o resultado foi falha, senão
  um arquivo quebrado que ficasse na pasta rodaria a cada varredura, em laço: ele fica em `falhas` e só volta a rodar
  com `reprocessar=true`, decisão do usuário; o original **nunca** é alterado — com
  `ao_terminar="mover"` ele vai para `processados/` ou `falhas/` e **nunca sobrescreve** (acrescenta `_1`, `_2`).
- **A trava que mais importa (§12):** a pasta monitorada **nunca assina nem tarja sozinha**. Receita com
  `confirmacao` ou com passo `papiro-seguranca.*` para em `aguardando_confirmacao`/`aguardando_seguranca`, o
  arquivo **fica onde está** e a execução aparece em "pendentes" com a instrução de como retomar. Há teste disso.
- Receita pronta: `recipes/entrada-ocr-pdfa.yaml` (triagem de risco → OCR só nas páginas sem texto → PDF/A-2b →
  veraPDF → 11 portões). Medido de ponta a ponta: **PDF digital de 1 página, 32,8 s**, saída em
  `out/recebidos/<data>/pesquisavel-<pseudônimo>.pdf` e original movido para `processados/`.

### Números medidos (17/09/2026, neste PC)
| O quê | Medida |
| --- | --- |
| Da chegada do arquivo ao início do processamento | **~0,5 s** após o arquivo ficar estável (janela `estavel_s`, padrão 3 s). É este o prazo que o teste do RF-906 cobra (≤ 10 s) |
| Ciclo completo com receita leve (triagem de risco) | **5,5 s** com a máquina livre; **18,6 s** com ela carregada (Rhino + Chrome abertos) — o tempo da receita depende da carga, por isso não entra no prazo cobrado |
| Ciclo completo com a receita de OCR + PDF/A | **32,8 s** (1 página) — o tempo é da receita, não da detecção |
| Primeira execução num `PAPIRO_HOME` novo | +2,8 s só para criar `logs/jobs.db` (disco USB deste PC; depois, 0,3 ms por abertura) |

## 3-B. Carimbo do tempo RFC 3161 (PRD §12.1) — `timestamp` e `sign carimbo=true`
- **`sign ... carimbo=true`** (ou `tsa="https://..."`) embute o carimbo na assinatura: o perfil passa de **PAdES-B-B
  para PAdES-B-T**, o motor vira `pyhanko+rfc3161` e o envelope traz `dados.carimbo` (hora atestada, autoridade,
  se está íntegro). Vale para A1 e A3, e também em `certify`.
- **`timestamp entrada=... tsa=...`** carimba o documento inteiro sem assinar (DocTimeStamp). Deixou de ser
  `E_SEM_SUPORTE`. Pode ser aplicado **sobre um PDF já assinado sem quebrar a assinatura** (medido: a assinatura
  continua íntegra e o carimbo entra por cima).
- **`verify` agora relata carimbos:** cada item ganhou `tipo` (`assinatura` ou `carimbo_do_documento`) e `carimbo`
  com hora, autoridade e integridade.
- **Privacidade (§12.5), medida e testada:** a TSA recebe **só o resumo SHA-256** — o teste intercepta o que sai pela
  rede e confirma que cada pedido tem menos de 200 bytes, não contém nenhum trecho do PDF e leva apenas um digest de
  32 bytes. Ainda assim é rede: em **job sensível a chamada é recusada** (`E_POLITICA`) até vir `rede_tsa=true`
  explícito, e o envelope sempre avisa o que foi enviado e para qual servidor.
- **Configuração:** `tsa=` na chamada, `PAPIRO_TSA_URL`, ou `[assinatura] tsa_url` no `papiro.toml`
  (com `tsa_usuario`/`tsa_senha_ref` quando a TSA exigir autenticação, e `tsa_timeout_s`). Carimbo de ACT credenciada
  na ICP-Brasil costuma ser pago, por isso fica opcional.
- **Erros úteis:** TSA ausente ou URL que não é http(s) → `E_ENTRADA`; servidor fora do ar → `E_MOTOR` dizendo o
  servidor; sem resposta → `E_TEMPO`; carimbo que não ficou no documento → `E_CONFORMIDADE`.
- **Como foi testado:** uma **TSA RFC 3161 de verdade rodando em 127.0.0.1** (o `DummyTimeStamper` do pyHanko atrás
  de um servidor HTTP), então o caminho exercitado é o mesmo de uma TSA da internet — pedido HTTP, resposta DER,
  carimbo embutido e validado — sem depender de rede nem de serviço pago.
- **Não verificado:** TSA pública real (ex.: freetsa.org) e TSA de ACT credenciada ICP-Brasil; `ltv_update`
  (B-LT/B-LTA) continua sem suporte, porque exige buscar revogação on-line.

## 4. Testes
`core/tests/test_assinatura_a3.py` (16 testes: token e certificados, assinatura + verificação, token único,
`certify`, aparência visível, 7 erros de token/PIN/módulo, políticas, PIN fora do log, `prompt` sem terminal, CLI)
e `core/tests/test_vigia.py` (9 testes: configuração conferida, processa/move/dedup/reprocessa, espera a cópia
terminar, arquivo ruim vai para `falhas/`, **falha não vira laço**, **não assina sozinha**, prazo do RF-906, MCP
`watch`/`watch_status`, CLI).
`core/tests/test_carimbo_tsa.py` (8 testes: B-T, só o resumo vai para a TSA, carimbo do documento, carimbo sobre
assinatura, erros da TSA, política do job sensível, TSA vinda da configuração, assinatura sem carimbo continua B-B).
**Rodada completa antes do carimbo (17/09/2026 19:11): 169 testes passando, 0 falhas, cobertura 87%**
Depois do carimbo, os arquivos afetados foram repetidos (20:15): carimbo 8/8, segurança 11/11, A3 16/16, vigia 9/9.
Um teste antigo precisou mudar: `timestamp` sem TSA agora responde `E_ENTRADA` (pedindo a TSA) no lugar do antigo
`E_SEM_SUPORTE`. (4.909 linhas; eram 145 e 87%).
Os 9 do vigia foram repetidos depois da correção do laço: verdes. A suíte levou 35 min contra 12 min da rodada
anterior — a máquina estava disputada (Rhino e Chrome abertos), não houve mudança de desempenho no PAPIRO.

## 5. Continua NÃO implementado
LTV B-LT/B-LTA (`ltv_update`) · JSignPdf · tradução com layout (RF-608) · alt-text por visão (RF-609) · decks Touying
(RF-501..506) · Docling/PaddleOCR-VL · `conform` pdfua/pdfx/remediate · XFDF · criação/detecção de campos
(RF-701/702) · Vega-Lite (RF-305) · docx/epub/dxf · embeddings no RAG · Tesseract 5 no Linux · RNF-10 (mesmo hash)
**não verificado** · Windows não testado.

## 6. Retomar daqui
1. `cd ~/PAPIRO-Soberano && git log --oneline -3`.
2. Testes: `cd core && ~/.local/share/lancadores-claude/papiro-soberano/venv312/bin/python -m pytest -q --cov=papiro_core`.
3. Ligar uma pasta monitorada: descomente o `[[pastas]]` do `papiro.toml`, crie a pasta e rode `papiro vigiar --uma-vez`.
4. Assinar com o token A3 de verdade: conecte o token, `papiro token` para ver o rótulo, e `sign token=... pin_ref=prompt`.
   Depois confira o PDF em `validar.iti.gov.br` (homologação do PRD §12) — é o passo que falta para o A3 sair de
   "testado com token de software" para "homologado".
5. Carimbar com uma TSA de verdade: `sign ... carimbo=true tsa="https://freetsa.org/tsr"` (ou a da sua ACT) e
   conferir o PDF em `validar.iti.gov.br`.
6. Próximos itens de maior valor: LTV (B-LT/B-LTA) → Vega-Lite (RF-305) → `conform` pdfua/remediate.
