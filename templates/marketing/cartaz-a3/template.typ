// RF-307 Cartaz A3: título dominante, data e local, destaque e chamada; QR opcional.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  let acento = cor(tokens, "acento")
  set page(paper: "a3", margin: 0pt, fill: prim)
  set text(font: fam-titulo(tokens), fill: white)
  place(top + right, dx: 60mm, dy: -60mm, circle(radius: 120mm, fill: prim.lighten(12%)))
  place(bottom + right, dx: 55mm, dy: 55mm, circle(radius: 95mm, fill: acento))
  pad(x: 24mm, y: 26mm, {
    grid(columns: (1fr, auto), text(size: 16pt, weight: "bold", tracking: 2pt, upper(campo(dados, "organizador", padrao: ""))), logo(dados, 30pt))
    v(60mm)
    text(size: 64pt, weight: "bold", dados.titulo)
    v(4mm)
    text(size: 24pt, dados.subtitulo)
    v(14mm)
    box(fill: acento, inset: (x: 10pt, y: 8pt), radius: 3pt, text(size: 22pt, weight: "bold", fill: cor(tokens, "texto"), dados.data + "  ·  " + dados.horario))
    v(6mm)
    text(size: 20pt, dados.local)
    v(1fr)
    grid(columns: (1fr, auto), align: (left + bottom, right + bottom),
      { text(size: 18pt, dados.destaque); v(6mm); text(size: 28pt, weight: "bold", dados.chamada) },
      box(fill: white, inset: 6pt, radius: 3pt, qr(dados, 42mm)))
  })
  body
}
