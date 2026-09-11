"""Fixtures compartilhadas entre todas as suítes de teste."""

import pytest

from app import _seed_categorias, _seed_locais, create_app
from app.extensions import db as _db


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret"
    HORIZONTE_MESES = 1
    MESES_MEDIA_PROVISIONAMENTO = 3
    WTF_CSRF_ENABLED = False


@pytest.fixture(scope="session")
def app():
    """Cria a aplicação Flask configurada para testes (banco em memória)."""
    application = create_app(TestConfig)
    return application


@pytest.fixture
def db(app):
    """Banco de dados limpo para cada teste."""
    with app.app_context():
        _db.create_all()
        _seed_categorias()
        _seed_locais()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    """Cliente HTTP do Flask para testes de integração."""
    return app.test_client()
