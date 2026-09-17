// RF-307 E-book A5: capa, folha de rosto, sumário e capítulos em serifa com recuo de primeira linha.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(paper: "a5", margin: (top: 18mm, bottom: 18mm, inside: 17mm, outside: 13mm))
  set text(font: fam-texto(tokens), size: 10.5pt, fill: cor(tokens, "texto"), hyphenate: true)
  set par(justify: true, leading: 0.7em, first-line-indent: 1.2em, spacing: 0.7em)
  show heading.where(level: 1): it => { pagebreak(weak: true); v(22mm); align(center, text(font: fam-titulo(tokens), size: 17pt, weight: "bold", fill: prim, it.body)); v(12mm) }
  // capa
  page(margin: 0pt, fill: prim, {
    set text(font: fam-titulo(tokens), fill: white)
    place(center + horizon, block(width: 80%, {
      set align(center)
      text(size: 26pt, weight: "bold", dados.titulo)
      if campo(dados, "subtitulo") != none { v(6pt); text(size: 12pt, dados.subtitulo) }
      v(14mm)
      line(length: 30%, stroke: 2pt + cor(tokens, "acento"))
      v(6mm)
      text(size: 13pt, dados.autor)
    }))
  })
  // folha de rosto
  page({
    set align(center)
    set par(first-line-indent: 0pt)
    v(30mm)
    text(font: fam-titulo(tokens), size: 16pt, weight: "bold", dados.titulo)
    linebreak()
    text(size: 11pt, dados.autor)
    v(1fr)
    text(size: 8.5pt, fill: cor(tokens, "texto_suave"),
      campo(dados, "editora", padrao: "") + (if campo(dados, "ano") != none { " · " + str(dados.ano) } else { "" }))
    if campo(dados, "dedicatoria") != none { v(10mm); text(style: "italic", dados.dedicatoria) }
    v(8mm)
  })
  set page(footer: context align(center, text(font: fam-titulo(tokens), size: 8pt, fill: cor(tokens, "texto_suave"),
    counter(page).display())))
  counter(page).update(1)
  outline(title: [Sumário], depth: 1)
  for cap in dados.capitulos {
    heading(level: 1, cap.titulo)
    for par in cap.paragrafos { par; parbreak() }
  }
  body
}
