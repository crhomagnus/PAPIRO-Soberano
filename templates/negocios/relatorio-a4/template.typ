// RF-307 Relatório A4: capa, sumário com links internos, seções numeradas.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(paper: "a4", margin: (top: 22mm, bottom: 22mm, x: 20mm))
  set text(font: fam-texto(tokens), size: corpo(tokens), fill: cor(tokens, "texto"))
  set par(justify: true, leading: 0.72em, spacing: 1.1em)
  show heading: set text(font: fam-titulo(tokens), fill: prim)
  show heading.where(level: 1): set text(size: 17pt)
  show heading.where(level: 1): set block(above: 20pt, below: 10pt)
  show heading.where(level: 2): set text(size: 12pt)
  set heading(numbering: "1.1")
  // capa
  page(margin: 0pt, footer: none, {
    place(top + left, rect(width: 100%, height: 58%, fill: prim))
    place(top + left, dx: 20mm, dy: 20mm, logo(dados, 30pt))
    place(top + left, dx: 20mm, dy: 95mm, block(width: 170mm, {
      set text(font: fam-titulo(tokens), fill: white)
      text(size: 30pt, weight: "bold", dados.titulo)
      if campo(dados, "subtitulo") != none { v(4pt); text(size: 14pt, dados.subtitulo) }
    }))
    place(top + left, dx: 20mm, dy: 58% + 14mm, block(width: 170mm, {
      set text(font: fam-titulo(tokens))
      line(length: 30mm, stroke: 3pt + cor(tokens, "acento"))
      v(6pt)
      text(size: 12pt, weight: "bold", dados.autor)
      if campo(dados, "organizacao") != none { linebreak(); text(size: 11pt, dados.organizacao) }
      linebreak()
      text(size: 10pt, fill: cor(tokens, "texto_suave"), campo(dados, "data", padrao: dados._hoje))
    }))
  })
  set page(header: context {
      if counter(page).get().first() > 1 {
        set text(font: fam-titulo(tokens), size: 8pt, fill: cor(tokens, "texto_suave"))
        grid(columns: (1fr, auto), dados.titulo, campo(dados, "organizacao", padrao: ""))
        v(-4pt); line(length: 100%, stroke: 0.4pt + cor(tokens, "linha"))
      }
    },
    footer: rodape-paginas(tokens))
  counter(page).update(1)
  outline(title: [Sumário], indent: auto)
  pagebreak()
  if campo(dados, "resumo") != none {
    block(fill: cor(tokens, "suave"), inset: 12pt, radius: 3pt, width: 100%, {
      rotulo(tokens, "Resumo executivo"); v(2pt); dados.resumo })
  }
  for s in dados.secoes {
    heading(level: 1, s.titulo)
    for par in campo(s, "paragrafos", padrao: ()) { par; parbreak() }
    if campo(s, "topicos") != none { list(..s.topicos) }
    for sub in campo(s, "subsecoes", padrao: ()) {
      heading(level: 2, sub.titulo)
      for par in campo(sub, "paragrafos", padrao: ()) { par; parbreak() }
    }
  }
  body
}
