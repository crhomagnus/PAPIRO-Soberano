---
name: papiro-receitas
description: "Receitas YAML do PAPIRO (PRD §9.3): escrever, validar e o que o executor ainda não faz."
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

## Ferramentas reais
- `recipes op=list` · `recipes op=validate arquivo=recipes/x.yaml` (JSON Schema: `receita`, `versao` ≥ 1, `passos`
  com `id` único e `ferramenta`).
- `recipes op=run` ainda devolve E_SEM_SUPORTE: o executor (checkpoints, cache por hash, `exige`, `se`, `para_cada`,
  `paralelo`, `confirmacao`) não foi implementado. Execute os passos manualmente, na ordem, conferindo `exige`.
- A tabela `receita_passos` do `logs/jobs.db` já guarda checkpoints e cache por hash para o futuro executor.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
