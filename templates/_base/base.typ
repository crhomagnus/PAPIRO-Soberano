// PAPIRO — base comum dos templates RF-307 (Typst 0.15). Tokens do brand kit (PRD §10.1).
#let cor(tokens, nome) = rgb(tokens.cores.at(nome))
#let fam-titulo(tokens) = tokens.tipografia.titulo.familia
#let fam-texto(tokens) = tokens.tipografia.texto.familia
#let corpo(tokens) = tokens.tipografia.corpo_pt * 1pt
#let campo(d, chave, padrao: none) = if type(d) == dictionary { d.at(chave, default: padrao) } else { padrao }

// R$ 1.234,56
#let brl(v) = {
  let c = int(calc.round(float(v) * 100))
  let neg = c < 0
  if neg { c = -c }
  let inteiro = str(calc.quo(c, 100))
  let cent = calc.rem(c, 100)
  let grupos = ()
  while inteiro.len() > 3 {
    grupos.insert(0, inteiro.slice(inteiro.len() - 3))
    inteiro = inteiro.slice(0, inteiro.len() - 3)
  }
  grupos.insert(0, inteiro)
  (if neg { "−" } else { "" }) + "R$ " + grupos.join(".") + "," + (if cent < 10 { "0" } else { "" }) + str(cent)
}

#let rotulo(tokens, t) = text(font: fam-titulo(tokens), size: 7pt, weight: "bold", fill: cor(tokens, "texto_suave"),
  tracking: 0.6pt, upper(t))

#let rodape-paginas(tokens, texto: none) = context {
  set text(font: fam-titulo(tokens), size: 7.5pt, fill: cor(tokens, "texto_suave"))
  grid(columns: (1fr, auto), align: (left, right),
    if texto != none { texto } else { [] },
    counter(page).display("1 de 1", both: true))
}

#let linha-assinatura(tokens, nome, detalhe: none, largura: 62%) = align(center, block(width: largura, {
  line(length: 100%, stroke: 0.6pt + cor(tokens, "texto"))
  v(-5pt)
  text(font: fam-titulo(tokens), size: 9pt, weight: "bold", nome)
  if detalhe != none { linebreak(); text(font: fam-titulo(tokens), size: 8pt, fill: cor(tokens, "texto_suave"), detalhe) }
}))

#let caixa(tokens, titulo: none, corpo-conteudo) = block(width: 100%, inset: 7pt, radius: 3pt,
  stroke: 0.5pt + cor(tokens, "linha"), {
    if titulo != none { rotulo(tokens, titulo); v(2pt) }
    corpo-conteudo
  })

#let logo(dados, altura) = if campo(dados, "_logo") != none {
  image(dados._logo, height: altura, alt: campo(dados, "_logo_alt", padrao: "Logotipo"))
}

#let qr(dados, largura) = if campo(dados, "_qr") != none {
  image(dados._qr, width: largura, alt: "Código QR: " + campo(dados, "url_qr", padrao: campo(dados, "url_verificacao", padrao: "")))
}

// Cabeçalho de documento médico: nome, especialidade, CRM/UF e RQE (identificação do emitente)
#let cabecalho-medico(tokens, m) = {
  set text(font: fam-titulo(tokens))
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon), gutter: 8pt,
    {
      text(size: 13pt, weight: "bold", fill: cor(tokens, "primaria"), m.nome)
      linebreak()
      let linha = ()
      if campo(m, "especialidade") != none { linha.push(m.especialidade) }
      linha.push("CRM " + m.crm + "/" + m.uf)
      if campo(m, "rqe") != none { linha.push("RQE " + m.rqe) }
      text(size: 8.5pt, fill: cor(tokens, "texto_suave"), linha.join("  ·  "))
    },
    logo(m, 26pt))
  v(4pt)
  line(length: 100%, stroke: 1.4pt + cor(tokens, "primaria"))
  v(-8pt)
  line(length: 22%, stroke: 1.4pt + cor(tokens, "acento"))
}

#let rodape-medico(tokens, m) = {
  set text(font: fam-titulo(tokens), size: 7pt, fill: cor(tokens, "texto_suave"))
  let partes = ()
  if campo(m, "endereco") != none { partes.push(m.endereco) }
  if campo(m, "telefone") != none { partes.push(m.telefone) }
  if campo(m, "email") != none { partes.push(m.email) }
  line(length: 100%, stroke: 0.4pt + cor(tokens, "linha"))
  v(-6pt)
  align(center, partes.join("  ·  "))
}

#let local-data(dados) = {
  let l = campo(dados, "local")
  let d = campo(dados, "data", padrao: campo(dados, "_hoje"))
  if l != none { l + ", " + d } else { d }
}

#let extenso(dados, chave) = campo(dados, chave + "_extenso")
