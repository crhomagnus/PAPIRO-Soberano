// RF-307 Folder A4 paisagem de 3 dobras. Página 1 (externa): aba interna | contracapa | capa.
// Página 2 (interna): três painéis.
#import "base.typ": *

#let painel(tokens, conteudo, fundo: none) = block(width: 100%, height: 100%, fill: fundo, inset: (x: 9mm, y: 11mm), conteudo)

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(paper: "a4", flipped: true, margin: 0pt)
  set text(font: fam-titulo(tokens), size: 10.5pt, fill: cor(tokens, "texto"))
  set par(justify: true, leading: 0.66em)
  let titulo-painel(t) = { block(text(size: 14pt, weight: "bold", fill: prim, hyphenate: false, par(justify: false, t))); v(-3pt); box(width: 20pt, height: 2.5pt, fill: cor(tokens, "acento")); v(4pt) }
  // externa
  grid(columns: (1fr, 1fr, 1fr), rows: 100%,
    painel(tokens, { titulo-painel(dados.aba.titulo); dados.aba.texto }),
    painel(tokens, fundo: cor(tokens, "suave"), {
      titulo-painel(dados.contracapa.titulo)
      set par(justify: false)
      dados.contracapa.contato
      v(1fr)
      align(center, qr(dados, 28mm))
    }),
    painel(tokens, fundo: prim, {
      set text(fill: white, hyphenate: false)
      set par(justify: false, leading: 0.55em)
      logo(dados, 22pt)
      v(1fr)
      text(size: 26pt, weight: "bold", dados.capa.titulo)
      v(4pt)
      text(size: 12pt, dados.capa.subtitulo)
      v(20mm)
    }))
  pagebreak()
  // interna
  grid(columns: (1fr, 1fr, 1fr), rows: 100%,
    ..dados.paineis.map(p => painel(tokens, {
      titulo-painel(p.titulo)
      p.texto
      if campo(p, "topicos") != none { v(4pt); list(..p.topicos) }
    })))
  body
}
