from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    STATUS_PAGO,
    STATUS_PENDENTE,
    Conta,
    Lancamento,
    LancamentoRateio,
    Receita,
)
from app.utils import (
    competencia_fatura_cartao,
    competencia_str,
    decompor_forma_pagamento,
    recalcular_fatura_cartao,
)


def _parse_decimal_str(
    texto: str | None, default: Decimal | None = None
) -> Decimal | None:
    if not texto:
        return default
    try:
        return Decimal(str(texto).replace(".", "").replace(",", "."))
    except InvalidOperation:
        return default


def pontos_fatura_afetados(lancamento_id: int) -> set[tuple[int, str]]:
    """Retorna o conjunto de (cartao_id, competencia_da_fatura) relevantes
    para um lançamento agora — considerando tanto a forma de pagamento
    única quanto cada parte de um pagamento dividido."""
    from app.extensions import db

    lanc = db.session.get(Lancamento, lancamento_id)
    if not lanc or not lanc.data_pagamento:
        return set()

    pontos: set[tuple[int, str]] = set()
    if lanc.cartao_id:
        cartao = db.session.get(Conta, lanc.cartao_id)
        if cartao:
            pontos.add(
                (cartao.id, competencia_fatura_cartao(cartao, lanc.data_pagamento))
            )

    for rateio in LancamentoRateio.query.filter_by(
        lancamento_id=lancamento_id, tipo="cartao"
    ).all():
        if rateio.cartao_id:
            cartao = db.session.get(Conta, rateio.cartao_id)
            if cartao:
                pontos.add(
                    (cartao.id, competencia_fatura_cartao(cartao, lanc.data_pagamento))
                )

    return pontos


def recalcular_pontos_fatura(db_session: Session, pontos: set[tuple[int, str]]) -> None:
    """Recalcula o total das faturas de cartão que foram afetadas."""
    for cartao_id, competencia in pontos:
        cartao = db_session.get(Conta, cartao_id)
        if cartao:
            recalcular_fatura_cartao(db_session, cartao, competencia)


def atualizar_lancamento_from_form(
    db_session: Session,
    lancamento: Lancamento,
    form: Mapping[str, Any],
    rateio_formas: list[str],
    rateio_valores: list[str],
) -> Lancamento:
    """Atualiza atributos, baixa de pagamento e rateio de um lançamento."""
    pontos_antes = pontos_fatura_afetados(lancamento.id)

    valor = form.get("valor")
    vencimento = form.get("vencimento")
    mes_competencia = form.get("mes_competencia")
    ano_competencia = form.get("ano_competencia")
    forma_pagamento_raw = form.get("forma_pagamento")
    dividir_pagamento = form.get("dividir_pagamento") == "on"
    pago = form.get("pago") == "on"
    data_pagamento = form.get("data_pagamento")
    valor_pago = form.get("valor_pago")
    observacao = form.get("observacao")

    novo_valor = _parse_decimal_str(valor)
    if novo_valor is not None:
        lancamento.valor = novo_valor

    if vencimento:
        lancamento.vencimento = datetime.strptime(vencimento, "%Y-%m-%d").date()

    if mes_competencia and ano_competencia:
        lancamento.competencia = competencia_str(
            int(ano_competencia), int(mes_competencia)
        )

    if observacao is not None:
        lancamento.observacao = observacao

    if pago:
        lancamento.status = STATUS_PAGO
        dec_valor_pago = _parse_decimal_str(valor_pago, lancamento.valor)
        lancamento.valor_pago = dec_valor_pago
        lancamento.data_pagamento = (
            datetime.strptime(data_pagamento, "%Y-%m-%d").date()
            if data_pagamento
            else date.today()
        )
    else:
        if lancamento.status == STATUS_PAGO:
            lancamento.status = STATUS_PENDENTE
            lancamento.valor_pago = None
            lancamento.data_pagamento = None

    # Limpa os rateios antigos para reconstruir
    LancamentoRateio.query.filter_by(lancamento_id=lancamento.id).delete()

    if dividir_pagamento and rateio_formas:
        partes_label = []
        for forma_raw, valor_raw in zip(rateio_formas, rateio_valores, strict=False):
            valor_rateio = _parse_decimal_str(valor_raw, Decimal(0)) or Decimal(0)
            if valor_rateio <= 0:
                continue

            tipo_forma, valor_forma = decompor_forma_pagamento(forma_raw)
            rateio = LancamentoRateio(
                lancamento_id=lancamento.id, tipo=tipo_forma, valor=valor_rateio
            )

            if tipo_forma == "cartao":
                cartao = (
                    db_session.get(Conta, int(valor_forma)) if valor_forma else None
                )
                rateio.cartao_id = cartao.id if cartao else None
                partes_label.append(cartao.nome if cartao else "Cartão")
            elif tipo_forma == "receita":
                receita = (
                    db_session.get(Receita, int(valor_forma)) if valor_forma else None
                )
                rateio.receita_id = receita.id if receita else None
                partes_label.append(receita.tipo if receita else "Receita")
            else:
                rateio.descricao_generica = valor_forma
                partes_label.append(valor_forma)

            db_session.add(rateio)

        lancamento.forma_pagamento = (
            "Dividido: " + " + ".join(partes_label) if partes_label else "Dividido"
        )
        lancamento.cartao_id = None
        lancamento.pago_com_receita_id = None

    elif forma_pagamento_raw:
        tipo_forma, valor_forma = decompor_forma_pagamento(forma_pagamento_raw)
        if tipo_forma == "cartao":
            cartao = db_session.get(Conta, int(valor_forma)) if valor_forma else None
            lancamento.cartao_id = cartao.id if cartao else None
            lancamento.pago_com_receita_id = None
            lancamento.forma_pagamento = (
                f"Cartão de crédito: {cartao.nome}" if cartao else "Cartão de crédito"
            )
        elif tipo_forma == "receita":
            receita = db_session.get(Receita, int(valor_forma)) if valor_forma else None
            lancamento.pago_com_receita_id = receita.id if receita else None
            lancamento.cartao_id = None
            lancamento.forma_pagamento = (
                f"Receita: {receita.tipo} - {receita.origem}" if receita else "Receita"
            )
        else:
            lancamento.forma_pagamento = valor_forma
            lancamento.cartao_id = None
            lancamento.pago_com_receita_id = None

    db_session.commit()

    pontos_depois = pontos_fatura_afetados(lancamento.id)
    recalcular_pontos_fatura(db_session, pontos_antes | pontos_depois)
    db_session.commit()

    return lancamento
