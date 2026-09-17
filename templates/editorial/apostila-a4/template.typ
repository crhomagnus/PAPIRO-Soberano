// RF-307 Apostila A4: capa, sumário, capítulos com seções, exercícios e cabeçalho corrente.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(paper: "a4", margin: (top: 24mm, bottom: 22mm, inside: 24mm, outside: 18mm))
  set text(font: fam-texto(tokens), size: corpo(tokens), fill: cor(tokens, "texto"))
  set par(justify: true, leading: 0.72em, spacing: 1em)
  show heading: set text(font: fam-titulo(tokens), fill: prim)
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => { pagebreak(weak: true); v(18mm); text(size: 11pt, fill: cor(tokens, "texto_suave"), "Capítulo " + counter(heading).display("1")); linebreak(); text(size: 24pt, weight: "bold", it.body); v(10mm) }
  show heading.where(level: 2): set text(size: 13pt)
  show heading.where(level: 2): set block(above: 16pt, below: 8pt)
  page(margin: (x: 24mm, y: 30mm), header: none, footer: none, {
    logo(dados, 30pt)
    v(1fr)
    text(font: fam-titulo(tokens), size: 11pt, fill: cor(tokens, "texto_suave"), upper(campo(dados, "instituicao", padrao: "")))
    v(4pt)
    text(font: fam-titulo(tokens), size: 34pt, weight: "bold", fill: prim, dados.titulo)
    if campo(dados, "subtitulo") != none { v(4pt); text(font: fam-titulo(tokens), size: 15pt, dados.subtitulo) }
    v(10pt)
    line(length: 35%, stroke: 3pt + cor(tokens, "acento"))
    v(8pt)
    text(font: fam-titulo(tokens), size: 12pt, dados.autor)
    v(1fr)
  })
  set page(header: context {
      set text(font: fam-titulo(tokens), size: 8pt, fill: cor(tokens, "texto_suave"))
      grid(columns: (1fr, auto), dados.titulo, campo(dados, "instituicao", padrao: ""))
    }, footer: rodape-paginas(tokens))
  counter(page).update(1)
  outline(title: [Sumário], indent: auto, depth: 2)
  for cap in dados.capitulos {
    heading(level: 1, cap.titulo)
    if campo(cap, "introducao") != none { cap.introducao; parbreak() }
    for s in campo(cap, "secoes", padrao: ()) {
      heading(level: 2, s.titulo)
      for par in s.paragrafos { par; parbreak() }
    }
    if campo(cap, "exercicios") != none {
      block(width: 100%, fill: cor(tokens, "suave"), inset: 10pt, radius: 3pt, breakable: false, {
        text(font: fam-titulo(tokens), weight: "bold", fill: prim, "Exercícios")
        enum(..cap.exercicios)
      })
    }
  }
  body
}
