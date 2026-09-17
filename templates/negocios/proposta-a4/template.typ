// RF-307 Proposta comercial A4: itens com subtotal e total calculados, validade e condições.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  let e = dados.empresa
  let c = dados.cliente
  set page(paper: "a4", margin: (top: 20mm, bottom: 22mm, x: 20mm), footer: rodape-paginas(tokens, texto: e.nome))
  set text(font: fam-titulo(tokens), size: 10pt, fill: cor(tokens, "texto"))
  set par(leading: 0.7em)
  show heading.where(level: 1): set text(size: 22pt, fill: prim, weight: "bold")
  show heading.where(level: 2): set text(size: 11pt, fill: prim, weight: "bold")
  show heading: set block(above: 14pt, below: 6pt)
  grid(columns: (1fr, auto), align: (left + top, right + top),
    { text(size: 14pt, weight: "bold", e.nome); if campo(e, "cnpj") != none { linebreak(); text(size: 8.5pt, fill: cor(tokens, "texto_suave"), "CNPJ " + e.cnpj) } ; if campo(e, "contato") != none { linebreak(); text(size: 8.5pt, e.contato) } },
    logo(e, 34pt))
  v(10pt)
  heading(level: 1, "Proposta comercial")
  grid(columns: (1fr, 1fr, 1fr), gutter: 8pt,
    caixa(tokens, titulo: "Número", dados.numero),
    caixa(tokens, titulo: "Data", campo(dados, "data", padrao: dados._hoje)),
    caixa(tokens, titulo: "Validade", str(dados.validade_dias) + " dias"))
  v(4pt)
  caixa(tokens, titulo: "Cliente", { text(weight: "bold", c.nome); if campo(c, "contato") != none { linebreak(); c.contato } })
  if campo(dados, "apresentacao") != none { heading(level: 2, "Apresentação"); set par(justify: true); dados.apresentacao }
  heading(level: 2, "Itens")
  let total = dados.itens.map(i => i.quantidade * i.valor_unitario).sum()
  table(columns: (1fr, auto, auto, auto), align: (left, right, right, right), stroke: none, inset: (x: 5pt, y: 6pt),
    fill: (_, y) => if y == 0 { prim } else if calc.even(y) { cor(tokens, "suave") } else { none },
    table.header(..("Descrição", "Qtd.", "Valor unitário", "Subtotal").map(h => text(fill: white, weight: "bold", h))),
    ..dados.itens.map(i => (i.descricao, str(i.quantidade), brl(i.valor_unitario), brl(i.quantidade * i.valor_unitario))).flatten(),
    table.cell(colspan: 3, align: right, text(weight: "bold", "Total")), text(weight: "bold", fill: prim, size: 11pt, brl(total)))
  if campo(dados, "prazo_entrega") != none { heading(level: 2, "Prazo"); dados.prazo_entrega }
  if campo(dados, "condicoes") != none { heading(level: 2, "Condições"); list(..dados.condicoes) }
  v(1fr)
  linha-assinatura(tokens, campo(e, "responsavel", padrao: e.nome), detalhe: e.nome)
  body
}
