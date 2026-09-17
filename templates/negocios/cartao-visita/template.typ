// RF-307 Cartão de visita 85 x 55 mm: frente e verso.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(width: 85mm, height: 55mm, margin: 5mm)
  set text(font: fam-titulo(tokens), size: 7pt, fill: cor(tokens, "texto"))
  // frente
  place(left + top, dx: -5mm, dy: -5mm, rect(width: 2.2mm, height: 55mm, fill: prim))
  pad(left: 1.5mm, {
    text(size: 11.5pt, weight: "bold", fill: prim, dados.nome)
    linebreak()
    text(size: 7.5pt, fill: cor(tokens, "texto_suave"), dados.cargo)
    v(1fr)
    set par(leading: 0.5em)
    for (rot, chave) in (("Tel.", "telefone"), ("E-mail", "email"), ("Site", "site"), ("End.", "endereco")) {
      if campo(dados, chave) != none { text(weight: "bold", fill: prim, rot + " "); dados.at(chave); linebreak() }
    }
  })
  pagebreak()
  // verso
  set page(fill: prim)
  align(center + horizon, {
    set text(fill: white)
    logo(dados, 14mm)
    text(size: 13pt, weight: "bold", dados.empresa)
    if campo(dados, "slogan") != none { linebreak(); text(size: 7pt, dados.slogan) }
  })
  body
}
