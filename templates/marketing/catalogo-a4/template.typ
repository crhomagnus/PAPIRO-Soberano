// RF-307 Catálogo A4: produtos em cartões de duas colunas (imagem opcional).
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(paper: "a4", margin: (top: 18mm, bottom: 20mm, x: 16mm), footer: rodape-paginas(tokens, texto: dados.empresa))
  set text(font: fam-titulo(tokens), size: 9.5pt, fill: cor(tokens, "texto"))
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
    { text(size: 24pt, weight: "bold", fill: prim, dados.titulo); linebreak(); text(size: 11pt, fill: cor(tokens, "texto_suave"), dados.empresa) },
    logo(dados, 30pt))
  v(3pt)
  line(length: 100%, stroke: 2pt + cor(tokens, "acento"))
  if campo(dados, "introducao") != none { v(4pt); set par(justify: true); dados.introducao }
  v(8pt)
  grid(columns: (1fr, 1fr), gutter: 9pt,
    ..dados.produtos.map(p => block(width: 100%, breakable: false, radius: 4pt, stroke: 0.6pt + cor(tokens, "linha"), clip: true, {
      if campo(p, "imagem") != none {
        image(p.imagem, width: 100%, height: 42mm, fit: "cover", alt: p.nome)
      } else {
        block(width: 100%, height: 42mm, fill: cor(tokens, "suave"),
          align(center + horizon, text(size: 22pt, weight: "bold", fill: prim.lighten(55%), upper(p.nome.first()))))
      }
      pad(9pt, {
        grid(columns: (1fr, auto), align: (left, right),
          text(size: 11pt, weight: "bold", p.nome),
          text(size: 11pt, weight: "bold", fill: prim, brl(p.preco)))
        if campo(p, "codigo") != none { text(size: 7.5pt, fill: cor(tokens, "texto_suave"), "Cód. " + p.codigo); linebreak() }
        v(-2pt)
        text(size: 8.5pt, p.descricao)
      })
    })))
  if campo(dados, "rodape") != none { v(8pt); text(size: 8pt, fill: cor(tokens, "texto_suave"), dados.rodape) }
  body
}
