---
name: papiro-tipografia
description: "Regras tipográficas do PAPIRO (PRD §10.2): escala, pares de fontes, pt-BR, fsType."
---

# papiro-tipografia

## Regras do motor de layout (PRD §10.2)
- Grid de 12 colunas com grade de linha de base; desvio máximo de 0,5 pt.
- Escala tipográfica modular (1,2; 1,25; 1,333 ou 1,5).
- No máximo 3 níveis de hierarquia por página, 2 famílias tipográficas e 1 cor de destaque.
- Linhas de 45 a 75 caracteres; hifenização pt-BR; controle de viúvas e órfãs.
- Números tabulares em tabelas; versaletes e ligaduras quando a fonte oferece.
- Imagens com DPI efetivo mínimo de 150 para tela e 300 para impressão; ampliação por IA só com aviso.
- Fonte com `fsType` restritivo não é embutida: o agente troca por alternativa de licença OFL.

## Tokens de marca (PRD §10.1)
Cada marca vive em `brandkits/<marca>/tokens.yaml`, compilado para `tokens.typ` e `tokens.css`. Assim Typst e Chromium usam exatamente os mesmos valores.

```yaml
marca: exemplo
cores:
  primaria: "#0F4C81"
  acento: "#F2A900"
  texto: "#1B1B1F"
  fundo: "#FFFFFF"
  cmyk:                      # informado pela marca, nunca adivinhado
    primaria: [100, 60, 0, 30]
tipografia:
  titulo: {familia: Inter, pesos: [600, 800]}
  texto: {familia: Source Serif 4, pesos: [400, 600]}
  mono: {familia: JetBrains Mono}
  escala: 1.25               # terça maior
  corpo_pt: 10.5
  entrelinha: 1.4
grid:
  pagina: A4
  margens_mm: [20, 18, 22, 18]
  colunas: 12
  gutter_mm: 4
  linha_base_pt: 14.7
logos:
  principal: logos/principal.svg
  mono: logos/mono.svg
```

## Estado real
Fontes incluídas em `fonts/`: Liberation Sans (4 estilos), Liberation Serif (4), Liberation Mono - SIL OFL 1.1, fsType 0
(embutimento livre). `brandkits/` ainda não tem marcas: sem `tokens.yaml`, use Liberation. `fonts op=list` mostra fsType
de cada fonte embutida de um PDF; fsType restritivo → trocar por OFL.

Fonte canônica: `docs/PAPIRO_PRD_ORIGINAL.md` (trechos acima copiados verbatim) e `docs/AGENTE_AUTONOMO_ENGENHARIA_PDF.md`. Ferramentas do MCP `papiro` respondem no envelope §8.1 (`ok`, `job_id`, `outputs`, `engine`, `qa`, `error`). Nunca declarar sucesso com `ok=false`.
