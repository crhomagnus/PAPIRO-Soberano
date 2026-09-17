// RF-307 Certificado A4 paisagem com moldura, texto de conclusão, assinaturas e código/QR de verificação.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let prim = cor(tokens, "primaria")
  let acento = cor(tokens, "acento")
  set page(paper: "a4", flipped: true, margin: 12mm)
  set text(font: fam-texto(tokens), size: 15pt, fill: cor(tokens, "texto"))
  block(width: 100%, height: 100%, stroke: 2.5pt + prim, inset: 5pt,
    block(width: 100%, height: 100%, stroke: 0.8pt + acento, inset: (x: 20mm, y: 12mm), {
      grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
        text(font: fam-titulo(tokens), size: 11pt, weight: "bold", fill: prim, tracking: 1pt, upper(dados.emissor.nome)),
        logo(dados.emissor, 28pt))
      v(6mm)
      align(center, {
        text(font: fam-titulo(tokens), size: 46pt, weight: "bold", fill: prim, tracking: 6pt, "CERTIFICADO")
        v(-4mm)
        text(font: fam-titulo(tokens), size: 12pt, fill: cor(tokens, "texto_suave"), campo(dados, "tipo", padrao: "de participação"))
        v(10mm)
        set par(justify: false, leading: 0.9em)
        [Certificamos que]
        v(3mm)
        text(size: 32pt, weight: "bold", style: "italic", dados.participante)
        v(3mm)
        block(width: 85%, [#campo(dados, "verbo", padrao: "participou do(a)") *#dados.evento*, realizado(a) em #dados.periodo#if campo(dados, "local") != none [, em #dados.local], com carga horária de #str(dados.carga_horaria) horas.])
      })
      v(1fr)
      // QR fora do fluxo, no canto: nunca disputa espaco com o texto nem com as assinaturas
      if campo(dados, "_qr") != none {
        place(bottom + right, align(center, { qr(dados, 22mm); v(-2pt); text(font: fam-titulo(tokens), size: 7pt, "Código " + dados.codigo_verificacao) }))
      }
      pad(right: if campo(dados, "_qr") != none { 34mm } else { 0mm },
        grid(columns: (1fr,) * dados.assinaturas.len(), align: bottom, column-gutter: 10mm,
          ..dados.assinaturas.map(a => linha-assinatura(tokens, a.nome, detalhe: a.cargo, largura: 90%))))
    }))
  body
}
