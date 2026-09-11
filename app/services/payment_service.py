from datetime import date
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy.orm import Session

from app.models import (
    STATUS_PAGO,
    TIPO_LANCAMENTO_PARCELADO,
    Conta,
    Quitacao,
)


class PaymentSplitter:
    """Estratégia para rateio e divisão de valores monetários entre N partes,
    garantindo precisão de 2 casas decimais e compensação de centavos residuais."""

    @staticmethod
    def split(total: Decimal, n: int) -> list[Decimal]:
        if n <= 0:
            raise ValueError("Número de partes deve ser maior que zero.")

        total_dec = Decimal(str(total)).quantize(Decimal("0.01"))
        base = (total_dec / n).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
        resto = total_dec - (base * n)
        centavos_resto = int((resto * 100).to_integral_value())

        partes = []
        for i in range(n):
            valor_parte = base + (
                Decimal("0.01") if i < centavos_resto else Decimal("0.00")
            )
            partes.append(valor_parte)

        return partes


def quitar_conta_parcelada(
    db_session: Session,
    conta: Conta,
    valor_quitacao: Decimal,
    data_quitacao: date | None = None,
    observacao: str | None = None,
) -> Quitacao:
    """Quita antecipadamente um financiamento/empréstimo/consórcio parcelado:
    o valor total da quitação é dividido de forma equilibrada pelas parcelas em aberto,
    que são automaticamente baixadas (pagas) nessa data."""
    if conta.tipo_lancamento != TIPO_LANCAMENTO_PARCELADO:
        raise ValueError("Somente contas do tipo Parcelado podem ser quitadas.")

    if data_quitacao is None:
        data_quitacao = date.today()

    abertas = [l for l in conta.lancamentos if l.status != STATUS_PAGO]
    if not abertas:
        raise ValueError("Não há parcelas em aberto para quitar.")

    partes = PaymentSplitter.split(valor_quitacao, len(abertas))

    for lancamento, parte_valor in zip(abertas, partes, strict=False):
        lancamento.valor = parte_valor
        lancamento.valor_pago = parte_valor
        lancamento.data_pagamento = data_quitacao
        lancamento.forma_pagamento = "Quitação antecipada"
        lancamento.status = STATUS_PAGO
        lancamento.observacao = (
            f"{lancamento.observacao} [Quitado antecipadamente]".strip()
            if lancamento.observacao
            else "[Quitado antecipadamente]"
        )

    quit_reg = Quitacao(
        conta_id=conta.id,
        data_quitacao=data_quitacao,
        valor_quitacao=valor_quitacao,
        parcelas_restantes=len(abertas),
        observacao=observacao,
    )
    db_session.add(quit_reg)
    conta.quitada = True
    db_session.commit()

    return quit_reg
