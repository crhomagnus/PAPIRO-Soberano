// RF-307 Cardápio A4: seções em duas colunas com linhas pontilhadas até o preço.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(paper: "a4", margin: (top: 16mm, bottom: 18mm, x: 16mm), fill: rgb("#FFFDF7"))
  set text(font: fam-texto(tokens), size: 10pt, fill: cor(tokens, "texto"))
  align(center, {
    logo(dados, 24pt)
    text(font: fam-titulo(tokens), size: 30pt, weight: "bold", fill: prim, tracking: 2pt, upper(dados.estabelecimento))
    if campo(dados, "subtitulo") != none { linebreak(); text(size: 11pt, style: "italic", dados.subtitulo) }
    v(2pt)
    line(length: 40%, stroke: 1.5pt + cor(tokens, "acento"))
  })
  v(6pt)
  let secao(s) = {
      block(breakable: false, below: 16pt, {
        text(font: fam-titulo(tokens), size: 15pt, weight: "bold", fill: prim, upper(s.nome))
        v(-6pt)
        line(length: 100%, stroke: 0.5pt + cor(tokens, "linha"))
        for item in s.itens {
          block(below: 9pt, breakable: false, {
            grid(columns: (auto, 1fr, auto), align: (left + bottom, left + bottom, right + bottom), column-gutter: 3pt,
              text(size: 11.5pt, weight: "bold", item.nome),
              box(width: 1fr, repeat(text(fill: cor(tokens, "linha"), "."))),
              text(font: fam-titulo(tokens), weight: "bold", fill: prim, brl(item.preco)))
            if campo(item, "descricao") != none { v(-4pt); text(size: 9.5pt, style: "italic", fill: cor(tokens, "texto_suave"), item.descricao) }
          })
        }
      })
  }
  // distribui as secoes pelo numero de itens, para as duas colunas ficarem equilibradas
  let pesos = dados.secoes.map(s => s.itens.len() + 2)
  let metade = pesos.sum() / 2
  let (esq, dir, acumulado) = ((), (), 0)
  for (i, s) in dados.secoes.enumerate() {
    if acumulado < metade { esq.push(s) } else { dir.push(s) }
    acumulado += pesos.at(i)
  }
  v(8pt)
  grid(columns: (1fr, 1fr), column-gutter: 12mm, esq.map(secao).join(), dir.map(secao).join())
  if campo(dados, "observacoes") != none {
    place(bottom + center, text(size: 8pt, fill: cor(tokens, "texto_suave"), dados.observacoes))
  }
  body
}
