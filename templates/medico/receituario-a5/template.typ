// RF-307 Receituário A5 — simples ou de controle especial (Portaria SVS/MS 344/1998, art. 52: duas vias com os
// dizeres de destino e quantidade em algarismos arábicos e por extenso).
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let m = dados.medico
  let p = dados.paciente
  let especial = campo(dados, "tipo", padrao: "simples") == "controle_especial"
  let prim = cor(tokens, "primaria")
  set page(paper: "a5", margin: (top: 13mm, bottom: 17mm, x: 13mm), footer: rodape-medico(tokens, m))
  set text(font: fam-titulo(tokens), size: 9.5pt, fill: cor(tokens, "texto"))
  set par(leading: 0.55em)
  show heading.where(level: 1): set text(size: 12.5pt, fill: prim, weight: "bold")
  show heading: set block(above: 0pt, below: 0pt)
  let vias = if especial { ("1ª via – Retenção da Farmácia ou Drogaria", "2ª via – Orientação ao Paciente") } else { (none,) }
  for (i, via) in vias.enumerate() {
    if i > 0 { pagebreak() }
    cabecalho-medico(tokens, m)
    v(9pt)
    if via != none {
      align(right, box(fill: cor(tokens, "acento"), inset: (x: 6pt, y: 3pt), radius: 2pt, text(size: 7.5pt, weight: "bold", via)))
      v(4pt)
    }
    heading(level: 1, if especial { "Receituário de Controle Especial" } else { "Receituário" })
    v(7pt)
    caixa(tokens, titulo: "Paciente", {
      text(size: 10.5pt, weight: "bold", p.nome)
      if campo(p, "endereco") != none { linebreak(); text(size: 8.5pt, p.endereco) }
    })
    v(9pt)
    for (n, item) in dados.itens.enumerate(start: 1) {
      block(breakable: false, below: 10pt, {
        grid(columns: (14pt, 1fr, auto), align: (left, left, right),
          text(weight: "bold", fill: prim, str(n) + "."),
          text(size: 10.5pt, weight: "bold", item.medicamento),
          if campo(item, "quantidade") != none {
            text(size: 9pt, str(item.quantidade) + " " + campo(item, "unidade", padrao: ""))
          } else { [] })
        if campo(item, "quantidade_extenso") != none {
          pad(left: 14pt, top: 1pt, text(size: 8pt, fill: cor(tokens, "texto_suave"),
            "Quantidade por extenso: " + item.quantidade_extenso + " " + campo(item, "unidade", padrao: "")))
        }
        pad(left: 14pt, top: 2pt, text(size: 9.5pt, item.posologia))
      })
    }
    if campo(dados, "orientacoes") != none {
      v(2pt)
      caixa(tokens, titulo: "Orientações", text(size: 9pt, dados.orientacoes))
    }
    v(1fr)
    align(right, text(size: 9pt, local-data(dados)))
    v(20pt)
    linha-assinatura(tokens, m.nome, detalhe: "CRM " + m.crm + "/" + m.uf)
    if especial {
      v(8pt)
      set text(size: 7.5pt)
      grid(columns: (1fr, 1fr), gutter: 6pt,
        caixa(tokens, titulo: "Identificação do comprador", {
          for r in ("Nome", "Documento", "Endereço", "Telefone") { r + ": "; box(width: 1fr, line(length: 100%, stroke: 0.4pt)); linebreak() }
        }),
        caixa(tokens, titulo: "Identificação do fornecedor", {
          for r in ("Nome e endereço", "Responsável", "Data") { r + ": "; box(width: 1fr, line(length: 100%, stroke: 0.4pt)); linebreak() }
        }))
    }
  }
  body
}
