from datetime import date
from decimal import Decimal

from app.models import (
    STATUS_PAGO,
    STATUS_PENDENTE,
    TIPO_LANCAMENTO_PARCELADO,
    TIPO_LANCAMENTO_RECORRENTE,
    Categoria,
    Conta,
    Lancamento,
)


def test_dashboard_index_status_code(client, db):
    """GET / deve renderizar o dashboard com código HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Total do" in response.data


def test_contas_listar_status_code(client, db):
    """GET /contas/ deve listar contas com código HTTP 200."""
    response = client.get("/contas/")
    assert response.status_code == 200
    assert b"Controle / Contas" in response.data


def test_contas_quitar_via_post(client, db):
    """POST /contas/<id>/quitar deve baixar parcelas em aberto e redirecionar."""
    categoria = Categoria.query.first()
    conta = Conta(
        nome="Financiamento Teste",
        categoria_id=categoria.id,
        tipo_lancamento=TIPO_LANCAMENTO_PARCELADO,
        valor_base=Decimal("200.00"),
        num_parcelas=2,
        dia_vencimento=15,
    )
    db.session.add(conta)
    db.session.commit()

    l1 = Lancamento(
        conta_id=conta.id,
        competencia="2026-04",
        vencimento=date(2026, 4, 15),
        valor=Decimal("200.00"),
        status=STATUS_PENDENTE,
        parcela_num=1,
    )
    l2 = Lancamento(
        conta_id=conta.id,
        competencia="2026-05",
        vencimento=date(2026, 5, 15),
        valor=Decimal("200.00"),
        status=STATUS_PENDENTE,
        parcela_num=2,
    )
    db.session.add_all([l1, l2])
    db.session.commit()

    response = client.post(
        f"/contas/{conta.id}/quitar",
        data={
            "valor_quitacao": "350,00",
            "data_quitacao": "2026-04-01",
            "observacao": "Quitado à vista com desconto",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Conta quitada" in response.get_data(as_text=True)

    db.session.refresh(conta)
    assert conta.quitada is True


def test_atualizar_lancamento_via_post(client, db):
    """POST /lancamentos/<id>/atualizar deve alterar o valor e status do lançamento."""
    categoria = Categoria.query.first()
    conta = Conta(
        nome="Conta Luz Teste",
        categoria_id=categoria.id,
        tipo_lancamento=TIPO_LANCAMENTO_RECORRENTE,
        valor_base=Decimal("150.00"),
        dia_vencimento=10,
    )
    db.session.add(conta)
    db.session.commit()

    lanc = Lancamento(
        conta_id=conta.id,
        competencia="2026-04",
        vencimento=date(2026, 4, 10),
        valor=Decimal("150.00"),
        status=STATUS_PENDENTE,
    )
    db.session.add(lanc)
    db.session.commit()

    response = client.post(
        f"/lancamentos/{lanc.id}/atualizar",
        data={
            "valor": "165,50",
            "vencimento": "2026-04-12",
            "mes_competencia": "4",
            "ano_competencia": "2026",
            "pago": "on",
            "valor_pago": "165,50",
            "data_pagamento": "2026-04-11",
            "forma_pagamento": "generico:Pix",
            "observacao": "Pago com desconto pontualidade",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    db.session.refresh(lanc)
    assert lanc.status == STATUS_PAGO
    assert lanc.valor == Decimal("165.50")
    assert lanc.valor_pago == Decimal("165.50")
    assert lanc.vencimento == date(2026, 4, 12)
