---
name: papiro-receitas
description: "Receitas YAML do PAPIRO (PRD §9.3): escrever, validar, rodar, retomar e salvar tarefa como receita."
---

# papiro-receitas

## Receitas declarativas (PRD §9.3)
Exemplo de receita:

```yaml
receita: receituario-assinado
versao: 1
descricao: Receituário A5 em PDF/A-2b e PDF/UA-1, assinado com ICP-Brasil
sensivel: true            # ativa o hook de soberania
entradas:
  dados: {tipo: json, esquema: esquemas/receituario.schema.json}
passos:
  - id: compor
    ferramenta: compose
    com: {motor: typst, template: medico/receituario-a5, dados: $dados,
          padroes_pdf: [a-2b, ua-1]}
  - id: validar
    ferramenta: validate
    com: {validadores: [verapdf, qpdf]}
    exige: {verapdf: aprovado}
  - id: revisar
    ferramenta: qa_run
    com: {rubrica: documento-medico}
  - id: assinar
    ferramenta: papiro-seguranca.sign
    com: {certificado: a3, visivel: true, carimbo_tempo: se_tsa_configurada, perfil: PAdES-B-B}
    confirmacao: obrigatoria
  - id: verificar
    ferramenta: papiro-seguranca.verify
saida:
  pasta: out/medico/{data}
  nome: receita-{id_pseudonimo}.pdf
```

Recursos do executor de receitas:

- **Checkpoints:** cada passo grava estado; uma queda retoma do passo exato.
- **Cache por hash:** passo com a mesma entrada não roda de novo.
- **Asserções:** `exige` interrompe a receita quando uma condição falha.
- **Controle de fluxo:** `se`, `para_cada` e `paralelo: N`.
- **Confirmação:** `confirmacao: obrigatoria` pausa e pergunta antes de passos sensíveis.
- **Validação:** toda receita é checada contra JSON Schema antes de rodar.

## Ferramenta `recipes` (executor real)
- `op=list` · `op=validate arquivo=recipes/x.yaml` (JSON Schema + ids únicos + ferramentas existentes).
- `op=run arquivo=... dados_json=... | dados_arquivo=...` → roda os passos em ordem; envelope com `dados.execucao`,
  `dados.passos` (ok, cache, pulado, retomado, reprovado, falhou, aguardando_*) e `dados.saida_final`.
- Checkpoints: `op=run execucao=<id>` (mesma receita e mesmos dados) retoma do passo exato.
- Cache por hash: passo com a mesma ferramenta, argumentos e arquivos de entrada reaproveita a saída (status `cache`).
- `exige`: `ok`, `qa: APROVADO`, `verapdf: aprovado`, `erro`, `paginas: ">=1"` ou caminho no envelope (`dados.x`).
- Fluxo: `se: "$dados.juntar == true"` (também `!=`, `not $ref`), `para_cada: $dados.lista` com `$item`/`$indice`,
  `paralelo: N` (processos separados). Referências: `$dados.campo`, `$<passo>.saida`, `$<passo>.saidas`, `$execucao`, `$data`.
- Sem `entrada`, o passo usa o PDF do passo anterior; sem `out_dir`, usa `out/<data>/receita-<execucao>/<passo>`.
- `confirmacao: obrigatoria` → pausa com E_POLITICA; retomar com `confirmados="<id do passo>"` SÓ depois que o usuário confirmar.
- Passos `papiro-seguranca.*` nunca rodam no executor: a execução pausa (`aguardando_seguranca`) com a instrução para o
  `pdf-seguranca`; depois de ele executar, retome com `externos_json='{"<passo>": {"saida": "<arquivo gerado>"}}'`.
- `sensivel: true` liga `work/_sensivel.flag` (hook soberania) até a execução terminar; `op=cancel execucao=<id>` encerra
  uma execução pausada e desliga a trava. `op=status execucao=<id>` mostra o estado.
- Vocabulário do PRD aceito: `padroes_pdf: [a-2b, ua-1]`, `dados: $dados`, `validadores: [verapdf, qpdf]`,
  `rubrica: ...` (vira aviso: a rubrica é do pdf-revisor-qa).
- RF-908: `op=save job_ids="<id1>,<id2>" nome=<nome>` gera a receita YAML dos jobs concluídos (encadeia saídas e troca
  conteúdo omitido por `$dados`). Reprodução do mesmo hash de saída: **não verificada**.
- Receitas prontas: `recipes/atestado-pdfa.yaml`, `recipes/lote-certificados.yaml`, `recipes/exemplo-receituario-assinado.yaml`.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
