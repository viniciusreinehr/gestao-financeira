"""Extensões Flask compartilhadas entre todos os módulos da aplicação.

Instâncias declaradas aqui (db) são inicializadas pela application factory
em app/__init__.py via db.init_app(app) para evitar importações circulares.

O listener set_sqlite_pragma garante que cada nova conexão SQLite ative:
  - journal_mode=WAL  : permite leituras simultâneas sem bloquear escritas
  - foreign_keys=ON   : aplica integridade referencial (desativado por padrão
                        no SQLite)
  - synchronous=NORMAL: performance balanceada e segura com WAL
"""

from typing import Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Ativa pragmas críticos do SQLite em cada nova conexão."""
    # Aplica apenas para SQLite — outros engines (PostgreSQL, MySQL) ignoram.
    if "sqlite" not in type(dbapi_connection).__module__:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.close()
