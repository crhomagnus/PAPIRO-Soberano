// RF-307 One-pager A4: título, números em destaque, blocos em duas colunas e chamada.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  let acento = cor(tokens, "acento")
  set page(paper: "a4", margin: 0pt)
  set text(font: fam-titulo(tokens), size: 10pt, fill: cor(tokens, "texto"))
  block(width: 100%, fill: prim, inset: (x: 18mm, top: 16mm, bottom: 12mm), {
    set text(fill: white)
    grid(columns: (1fr, auto), align: (left + horizon, right + horizon), text(size: 9pt, tracking: 1pt, upper(campo(dados, "marca", padrao: ""))), logo(dados, 22pt))
    v(8pt)
    text(size: 36pt, weight: "bold", hyphenate: false, dados.titulo)
    if campo(dados, "subtitulo") != none { v(4pt); text(size: 16pt, dados.subtitulo) }
  })
  pad(x: 18mm, top: 12mm, bottom: 0pt, {
    grid(columns: (1fr,) * dados.destaques.len(), gutter: 8pt,
      ..dados.destaques.map(d => block(width: 100%, inset: 14pt, radius: 4pt, fill: cor(tokens, "suave"), {
        text(size: 32pt, weight: "bold", fill: prim, d.valor)
        linebreak()
        text(size: 10.5pt, fill: cor(tokens, "texto_suave"), d.rotulo)
      })))
    v(14mm)
    set par(justify: true, leading: 0.72em)
    grid(columns: (1fr, 1fr), column-gutter: 12mm, row-gutter: 12mm,
      ..dados.blocos.map(b => block({
        box(width: 18pt, height: 3pt, fill: acento)
        v(2pt)
        text(size: 15pt, weight: "bold", fill: prim, b.titulo)
        v(-1pt)
        text(size: 11.5pt, b.texto)
      })))
  })
  place(bottom + left, block(width: 100%, fill: cor(tokens, "texto"), inset: (x: 18mm, y: 9mm), {
    set text(fill: white)
    grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
      text(size: 16pt, weight: "bold", dados.chamada),
      text(size: 11pt, dados.contato))
  }))
  body
}
