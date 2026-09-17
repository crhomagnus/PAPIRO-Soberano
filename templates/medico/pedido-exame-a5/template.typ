// RF-307 Pedido (solicitação) de exames A5.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let m = dados.medico
  let p = dados.paciente
  let prim = cor(tokens, "primaria")
  set page(paper: "a5", margin: (top: 13mm, bottom: 17mm, x: 13mm), footer: rodape-medico(tokens, m))
  set text(font: fam-titulo(tokens), size: 9.5pt, fill: cor(tokens, "texto"))
  show heading.where(level: 1): set text(size: 12.5pt, fill: prim, weight: "bold")
  show heading: set block(above: 0pt, below: 0pt)
  cabecalho-medico(tokens, m)
  v(9pt)
  heading(level: 1, "Solicitação de Exames")
  v(7pt)
  caixa(tokens, titulo: "Paciente", {
    text(size: 10.5pt, weight: "bold", p.nome)
    let extra = ()
    if campo(p, "data_nascimento") != none { extra.push("Nascimento: " + p.data_nascimento) }
    if campo(p, "documento") != none { extra.push(p.documento.tipo + " " + p.documento.numero) }
    if campo(p, "convenio") != none { extra.push("Convênio: " + p.convenio) }
    if extra.len() > 0 { linebreak(); text(size: 8.5pt, extra.join("  ·  ")) }
  })
  v(8pt)
  table(columns: (16pt, 1fr, auto), stroke: none, inset: (x: 3pt, y: 4.5pt),
    fill: (_, y) => if y == 0 { cor(tokens, "suave") } else if calc.even(y) { cor(tokens, "fundo") } else { none },
    table.header(text(weight: "bold", "Nº"), text(weight: "bold", "Exame"), text(weight: "bold", "Código")),
    ..dados.exames.enumerate(start: 1).map(((n, e)) => (
      text(fill: prim, weight: "bold", str(n)),
      { text(weight: "bold", e.nome); if campo(e, "observacao") != none { linebreak(); text(size: 8pt, fill: cor(tokens, "texto_suave"), e.observacao) } },
      text(size: 8.5pt, campo(e, "codigo", padrao: "—")),
    )).flatten())
  if campo(dados, "indicacao_clinica") != none {
    v(6pt)
    caixa(tokens, titulo: "Indicação clínica", {
      text(size: 9pt, dados.indicacao_clinica)
      if campo(dados, "cid") != none { linebreak(); text(size: 8.5pt, weight: "bold", "CID-10 " + dados.cid) }
    })
  }
  v(1fr)
  align(right, text(size: 9pt, local-data(dados)))
  v(20pt)
  linha-assinatura(tokens, m.nome, detalhe: "CRM " + m.crm + "/" + m.uf)
  body
}
