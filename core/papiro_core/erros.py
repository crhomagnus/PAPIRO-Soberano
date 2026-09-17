# -*- coding: utf-8 -*-
"""Erros padronizados PRD §8.2."""
from __future__ import annotations

ERROS = {
    "E_ENTRADA": "Arquivo ausente ou caminho fora da raiz",
    "E_SENHA": "PDF criptografado sem senha informada",
    "E_CORROMPIDO": "Nenhum parser abriu o arquivo",
    "E_MOTOR": "Motor falhou",
    "E_TEMPO": "Timeout",
    "E_CONFORMIDADE": "Validador reprovou",
    "E_POLITICA": "Hook ou regra bloqueou",
    "E_SEM_SUPORTE": "Recurso impossivel no motor",
}


class PapiroErro(Exception):
    """Erro com codigo do contrato. `mensagem` nunca deve conter conteudo do documento."""

    def __init__(self, codigo: str, mensagem: str = ""):
        if codigo not in ERROS:
            raise ValueError(f"codigo de erro desconhecido: {codigo}")
        self.codigo = codigo
        self.mensagem = mensagem or ERROS[codigo]
        super().__init__(f"{codigo}: {self.mensagem}")

    def como_dict(self) -> dict:
        return {"code": self.codigo, "message": self.mensagem}


def err(codigo: str, mensagem: str = "") -> dict:
    return PapiroErro(codigo, mensagem).como_dict()
