from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    STATUS_PAGO,
    STATUS_PENDENTE,
    TIPO_LANCAMENTO_PARCELADO,
    Categoria,
    Conta,
    Lancamento,
)
from app.services.payment_service import PaymentSplitter, quitar_conta_parcelada


def test_payment_splitter_impar():
    """Cenário obrigatório: rateio de R$ 100,00 para 3 partes distribui os centavos sem perder saldo."""
    partes = PaymentSplitter.split(Decimal("100.00"), 3)
    assert len(partes) == 3
    assert sum(partes) == Decimal("100.00")
    assert partes == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]


def test_payment_splitter_divisao_exata():
    partes = PaymentSplitter.split(Decimal("150.00"), 3)
    assert partes == [Decimal("50.00"), Decimal("50.00"), Decimal("50.00")]
    assert sum(partes) == Decimal("150.00")


def test_payment_splitter_quantidade_invalida():
    with pytest.raises(ValueError, match="Número de partes deve ser maior que zero"):
        PaymentSplitter.split(Decimal("50.00"), 0)


def test_quitar_conta_parcelada_sucesso(app, db):
    with app.app_context():
        categoria = Categoria.query.first()
        conta = Conta(
            nome="Empréstimo Teste",
            categoria_id=categoria.id,
            tipo_lancamento=TIPO_LANCAMENTO_PARCELADO,
            valor_base=Decimal("100.00"),
            num_parcelas=3,
            dia_vencimento=10,
        )
        db.session.add(conta)
        db.session.flush()

        # Cria 3 lançamentos (1 pago e 2 pendentes)
        l1 = Lancamento(
            conta_id=conta.id,
            competencia="2026-01",
            vencimento=date(2026, 1, 10),
            valor=Decimal("100.00"),
            valor_pago=Decimal("100.00"),
            status=STATUS_PAGO,
            parcela_num=1,
        )
        l2 = Lancamento(
            conta_id=conta.id,
            competencia="2026-02",
            vencimento=date(2026, 2, 10),
            valor=Decimal("100.00"),
            status=STATUS_PENDENTE,
            parcela_num=2,
        )
        l3 = Lancamento(
            conta_id=conta.id,
            competencia="2026-03",
            vencimento=date(2026, 3, 10),
            valor=Decimal("100.00"),
            status=STATUS_PENDENTE,
            parcela_num=3,
        )
        db.session.add_all([l1, l2, l3])
        db.session.commit()

        # Quitar as 2 parcelas restantes por R$ 150.01 total
        quitacao = quitar_conta_parcelada(
            db_session=db.session,
            conta=conta,
            valor_quitacao=Decimal("150.01"),
            data_quitacao=date(2026, 1, 25),
            observacao="Negociação antecipada",
        )

        assert quitacao is not None
        assert quitacao.parcelas_restantes == 2
        assert quitacao.valor_quitacao == Decimal("150.01")
        assert conta.quitada is True

        db.session.refresh(l2)
        db.session.refresh(l3)
        assert l2.status == STATUS_PAGO
        assert l3.status == STATUS_PAGO
        assert l2.valor_pago + l3.valor_pago == Decimal("150.01")
        assert l2.valor_pago == Decimal("75.01")
        assert l3.valor_pago == Decimal("75.00")
