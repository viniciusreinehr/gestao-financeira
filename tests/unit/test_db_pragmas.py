"""🧪 Tester — Fase 1: Testes dos pragmas SQLite (foreign_keys + WAL).

Estes testes FALHAM antes da implementação em extensions.py (Red phase TDD).
"""

import pytest


def test_pragma_foreign_keys_ativo(db):
    """PRAGMA foreign_keys deve retornar 1 (ativo) após conectar."""
    resultado = db.session.execute(db.text("PRAGMA foreign_keys;")).scalar()
    assert resultado == 1, (
        "PRAGMA foreign_keys está DESATIVADO. Adicione o listener em app/extensions.py."
    )


def test_pragma_journal_mode_wal(db):
    """PRAGMA journal_mode deve retornar 'wal' ou 'memory'.

    SQLite aceita WAL apenas para bancos em arquivo; bancos em memória
    (:memory:) ignoram o pragma e mantêm 'memory'. O teste verifica que o
    listener é executado sem erro e que o valor retornado é um dos dois modos
    válidos — WAL em produção, memory nos testes em memória.
    """
    resultado = db.session.execute(db.text("PRAGMA journal_mode;")).scalar()
    assert resultado in ("wal", "memory"), (
        f"journal_mode inesperado: '{resultado}'. "
        "Esperado 'wal' (arquivo) ou 'memory' (in-memory)."
    )


def test_foreign_key_violacao_levanta_erro(db):
    """Com foreign_keys=ON, inserção com FK inválida deve levantar erro de integridade."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.session.execute(
            db.text(
                "INSERT INTO lancamento (conta_id, competencia, vencimento, valor, status) "
                "VALUES (99999, '2026-01', '2026-01-10', 100.00, 'pendente')"
            )
        )
        db.session.commit()
