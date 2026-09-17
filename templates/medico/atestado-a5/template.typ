// RF-307 Atestado médico A5 (Resolução CFM 1.658/2002: tempo de dispensa, identificação do paciente por documento,
// diagnóstico só com concordância expressa registrada no próprio atestado, emissor identificado com CRM).
#import "base.typ": *

#let documento(dados: none, tokens: none, body) = {
  let m = dados.medico
  let p = dados.paciente
  let prim = cor(tokens, "primaria")
  set page(paper: "a5", margin: (top: 13mm, bottom: 17mm, x: 14mm), footer: rodape-medico(tokens, m))
  set text(font: fam-titulo(tokens), size: 10.5pt, fill: cor(tokens, "texto"))
  show heading.where(level: 1): set text(size: 14pt, fill: prim, weight: "bold", tracking: 1pt)
  show heading: set block(above: 0pt, below: 0pt)
  cabecalho-medico(tokens, m)
  v(18pt)
  align(center, heading(level: 1, "ATESTADO MÉDICO"))
  v(16pt)
  set par(justify: true, leading: 0.9em)
  let doc = p.documento.tipo + " nº " + p.documento.numero
  let dias = campo(dados, "dias", padrao: 0)
  [Atesto, para os devidos fins, que *#p.nome*, portador(a) do documento #doc, ]
  if dias > 0 {
    [esteve sob meus cuidados profissionais e necessita de *#str(dias) (#dados.dias_extenso) dia#if dias > 1 [s]* de afastamento
    #if campo(dados, "finalidade") != none [#dados.finalidade] else [de suas atividades], a partir de
    #campo(dados, "data_inicio", padrao: campo(dados, "data", padrao: dados._hoje)).]
  } else {
    [compareceu a atendimento médico nesta data#if campo(dados, "horario") != none [, #dados.horario].]
  }
  if campo(dados, "diagnostico") != none {
    v(10pt)
    caixa(tokens, titulo: "Diagnóstico", {
      set par(justify: false)
      text(weight: "bold", "CID-10 " + dados.diagnostico.cid)
      if campo(dados.diagnostico, "descricao") != none { [ — #dados.diagnostico.descricao] }
      linebreak()
      text(size: 8.5pt, fill: cor(tokens, "texto_suave"),
        "Diagnóstico incluído por solicitação e com a concordância expressa do(a) paciente.")
    })
  }
  if campo(dados, "observacoes") != none { v(8pt); text(size: 9.5pt, dados.observacoes) }
  v(1fr)
  align(right, text(size: 9.5pt, local-data(dados)))
  v(24pt)
  linha-assinatura(tokens, m.nome, detalhe: "CRM " + m.crm + "/" + m.uf)
  v(6pt)
  body
}
