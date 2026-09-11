"""🧪 Tester — Fase 2: Garantir que campos Numeric retornam Decimal, não float.

Estes testes FALHAM antes da correção em models.py (Red phase TDD).
"""

from decimal import Decimal


def test_conta_valor_base_retorna_decimal(db):
    """Conta.valor_base salvo como Decimal deve ser lido de volta como Decimal."""
    from app.models import Categoria, Conta, Local

    cat = Categoria(nome="Teste Cat D2", cor="#000", icone="bi-tag")
    loc = Local(nome="Teste Loc D2", cor="#000")
    db.session.add_all([cat, loc])
    db.session.flush()

    conta = Conta(
        nome="Conta Decimal Test",
        categoria_id=cat.id,
        local_id=loc.id,
        tipo_lancamento="recorrente",
        valor_base=Decimal("150.50"),
    )
    db.session.add(conta)
    db.session.commit()

    lida = db.session.get(Conta, conta.id)
    assert isinstance(lida.valor_base, Decimal), (
        f"valor_base retornou {type(lida.valor_base).__name__}, esperado Decimal. "
        "Adicione asdecimal=True ao Numeric em models.py."
    )
    assert lida.valor_base == Decimal("150.50")


def test_lancamento_valor_retorna_decimal(db):
    """Lancamento.valor salvo como Decimal deve ser lido como Decimal."""
    from datetime import date

    from app.models import Categoria, Conta, Lancamento, Local

    cat = Categoria(nome="Cat Lanc", cor="#111", icone="bi-tag")
    loc = Local(nome="Loc Lanc", cor="#111")
    db.session.add_all([cat, loc])
    db.session.flush()

    conta = Conta(
        nome="Conta Lancamento",
        categoria_id=cat.id,
        local_id=loc.id,
        tipo_lancamento="recorrente",
        valor_base=Decimal(0),
    )
    db.session.add(conta)
    db.session.flush()

    lanc = Lancamento(
        conta_id=conta.id,
        competencia="2026-09",
        vencimento=date(2026, 9, 10),
        valor=Decimal("1234.56"),
        status="pendente",
    )
    db.session.add(lanc)
    db.session.commit()

    lido = db.session.get(Lancamento, lanc.id)
    assert isinstance(lido.valor, Decimal), (
        f"valor retornou {type(lido.valor).__name__}, esperado Decimal."
    )
    assert lido.valor == Decimal("1234.56")


def test_soma_decimal_sem_conversao_explicita(db):
    """Deve ser possível somar campos monetários sem conversão manual para Decimal."""
    from datetime import date

    from app.models import Categoria, Conta, Lancamento, Local

    cat = Categoria(nome="Cat Soma", cor="#222", icone="bi-tag")
    loc = Local(nome="Loc Soma", cor="#222")
    db.session.add_all([cat, loc])
    db.session.flush()

    conta = Conta(
        nome="Conta Soma",
        categoria_id=cat.id,
        local_id=loc.id,
        tipo_lancamento="recorrente",
        valor_base=Decimal(0),
    )
    db.session.add(conta)
    db.session.flush()

    for i, valor in enumerate([Decimal("100.00"), Decimal("200.50"), Decimal("50.25")]):
        db.session.add(
            Lancamento(
                conta_id=conta.id,
                competencia=f"2026-0{i + 1}",
                vencimento=date(2026, i + 1, 10),
                valor=valor,
                status="pendente",
            )
        )
    db.session.commit()

    lancamentos = db.session.query(Lancamento).filter_by(conta_id=conta.id).all()
    total = sum(l.valor for l in lancamentos)  # não deve lançar TypeError
    assert total == Decimal("350.75")
    assert isinstance(total, Decimal)


def test_investimento_taxa_retorna_decimal(db):
    """Investimento.taxa_mensal_pct deve retornar Decimal."""
    from datetime import date

    from app.models import Investimento

    inv = Investimento(
        nome="CDB Teste",
        banco="Banco X",
        tipo="CDB",
        valor_inicial=Decimal("1000.00"),
        data_aplicacao=date(2026, 1, 1),
        taxa_mensal_pct=Decimal("0.9000"),
    )
    db.session.add(inv)
    db.session.commit()

    lido = db.session.get(Investimento, inv.id)
    assert isinstance(lido.taxa_mensal_pct, Decimal), (
        f"taxa_mensal_pct retornou {type(lido.taxa_mensal_pct).__name__}, esperado Decimal."
    )
    assert lido.taxa_mensal_pct == Decimal("0.9000")
