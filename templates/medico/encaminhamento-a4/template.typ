// RF-307 Encaminhamento (referência) A4, com espaço de contrarreferência.
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let m = dados.medico
  let p = dados.paciente
  let d = dados.destino
  let prim = cor(tokens, "primaria")
  set page(paper: "a4", margin: (top: 16mm, bottom: 20mm, x: 18mm), footer: rodape-medico(tokens, m))
  set text(font: fam-titulo(tokens), size: 10pt, fill: cor(tokens, "texto"))
  show heading.where(level: 1): set text(size: 15pt, fill: prim, weight: "bold")
  show heading.where(level: 2): set text(size: 9pt, fill: cor(tokens, "texto_suave"), weight: "bold", tracking: 0.6pt)
  show heading: set block(above: 12pt, below: 5pt)
  cabecalho-medico(tokens, m)
  v(6pt)
  grid(columns: (1fr, auto), align: (left + horizon, right + horizon),
    heading(level: 1, "Encaminhamento"),
    {
      let urg = campo(dados, "urgencia", padrao: "eletivo")
      let fundo = if urg == "urgente" { rgb("#B3261E") } else if urg == "prioritario" { cor(tokens, "acento") } else { cor(tokens, "suave") }
      box(fill: fundo, inset: (x: 7pt, y: 4pt), radius: 2pt,
        text(size: 8pt, weight: "bold", fill: if urg == "urgente" { white } else { cor(tokens, "texto") }, upper((eletivo: "Eletivo", prioritario: "Prioritário", urgente: "Urgente").at(urg))))
    })
  v(2pt)
  text(size: 11pt)[Ao(À) #if campo(d, "servico") != none [#d.servico — ]*#d.especialidade*#if campo(d, "profissional") != none [, aos cuidados de #d.profissional]]
  v(6pt)
  caixa(tokens, titulo: "Paciente", {
    text(size: 11pt, weight: "bold", p.nome)
    let extra = ()
    if campo(p, "data_nascimento") != none { extra.push("Nascimento: " + p.data_nascimento) }
    if campo(p, "documento") != none { extra.push(p.documento.tipo + " " + p.documento.numero) }
    if extra.len() > 0 { linebreak(); text(size: 9pt, extra.join("  ·  ")) }
  })
  set par(justify: true, leading: 0.7em)
  heading(level: 2, upper("Motivo do encaminhamento"))
  dados.motivo
  if campo(dados, "resumo_clinico") != none { heading(level: 2, upper("Resumo clínico")); dados.resumo_clinico }
  if campo(dados, "exames_realizados") != none {
    heading(level: 2, upper("Exames realizados"))
    list(..dados.exames_realizados)
  }
  if campo(dados, "medicacoes_em_uso") != none {
    heading(level: 2, upper("Medicações em uso"))
    list(..dados.medicacoes_em_uso)
  }
  v(14pt)
  grid(columns: (1fr, 1fr), align: (left + bottom, center + bottom),
    text(size: 9.5pt, local-data(dados)),
    linha-assinatura(tokens, m.nome, detalhe: "CRM " + m.crm + "/" + m.uf, largura: 90%))
  v(1fr)
  block(width: 100%, height: 150pt, inset: 8pt, radius: 3pt, stroke: (paint: cor(tokens, "linha"), thickness: 0.6pt, dash: "dashed"),
    rotulo(tokens, "Contrarreferência — preenchimento pelo serviço de destino"))
  body
}
