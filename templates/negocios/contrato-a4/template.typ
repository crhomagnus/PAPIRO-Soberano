// RF-307 Contrato A4: qualificação das partes, cláusulas numeradas por extenso, assinaturas e testemunhas.
// Só diagramação: o conteúdo jurídico vem dos dados e é responsabilidade de quem redige.
#import "base.typ": *

#let ordinais = ("PRIMEIRA", "SEGUNDA", "TERCEIRA", "QUARTA", "QUINTA", "SEXTA", "SÉTIMA", "OITAVA", "NONA", "DÉCIMA",
  "DÉCIMA PRIMEIRA", "DÉCIMA SEGUNDA", "DÉCIMA TERCEIRA", "DÉCIMA QUARTA", "DÉCIMA QUINTA", "DÉCIMA SEXTA",
  "DÉCIMA SÉTIMA", "DÉCIMA OITAVA", "DÉCIMA NONA", "VIGÉSIMA")

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  set page(paper: "a4", margin: (top: 25mm, bottom: 25mm, x: 25mm), footer: rodape-paginas(tokens, texto: dados.titulo))
  set text(font: fam-texto(tokens), size: 11pt, fill: cor(tokens, "texto"))
  set par(justify: true, leading: 0.78em, spacing: 1em)
  show heading.where(level: 1): set text(font: fam-titulo(tokens), size: 14pt, weight: "bold")
  show heading.where(level: 2): set text(font: fam-titulo(tokens), size: 10.5pt, weight: "bold", fill: prim)
  show heading: set block(above: 14pt, below: 6pt)
  align(center, heading(level: 1, upper(dados.titulo)))
  v(8pt)
  for parte in dados.partes {
    [*#upper(parte.papel):* #parte.nome, #parte.qualificacao]
    parbreak()
  }
  [As partes acima identificadas têm, entre si, justo e acordado o presente contrato, que se regerá pelas cláusulas seguintes.]
  for (i, cl) in dados.clausulas.enumerate() {
    let ord = if i < ordinais.len() { ordinais.at(i) } else { str(i + 1) + "ª" }
    heading(level: 2, "CLÁUSULA " + ord + " — " + upper(cl.titulo))
    cl.texto
  }
  v(12pt)
  align(right, local-data(dados))
  v(30pt)
  grid(columns: (1fr, 1fr), row-gutter: 38pt, column-gutter: 16pt,
    ..dados.partes.map(parte => linha-assinatura(tokens, parte.nome, detalhe: upper(parte.papel), largura: 95%)))
  if campo(dados, "testemunhas") != none {
    v(20pt)
    rotulo(tokens, "Testemunhas")
    v(26pt)
    grid(columns: (1fr, 1fr), column-gutter: 16pt,
      ..dados.testemunhas.map(t => linha-assinatura(tokens, t.nome, detalhe: campo(t, "documento", padrao: none), largura: 95%)))
  }
  body
}
