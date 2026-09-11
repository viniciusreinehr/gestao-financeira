import json
import os
import sys

from flask import Flask
from markupsafe import Markup

from app.extensions import db
from app.utils import (
    format_competencia,
    format_currency,
    format_date,
    format_date_curta,
)
from config import Config


def _pasta_recursos(subpasta):
    """Resolve o caminho de templates/static tanto rodando via `python run.py`
    quanto empacotado como executável (PyInstaller extrai os dados para uma
    pasta temporária referenciada por sys._MEIPASS)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "app", subpasta)
    return subpasta  # usa o padrão do Flask (relativo a este arquivo)


def _tojson_atributo(valor):
    """Serializa para JSON de forma segura para uso dentro de um atributo
    HTML com aspas duplas (o filtro `tojson` padrão do Jinja é pensado para
    uso dentro de <script> e não escapa aspas corretamente nesse contexto —
    sem isso, o JSON quebrava o atributo no meio)."""
    return Markup(json.dumps(valor).replace('"', "&quot;"))


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=_pasta_recursos("templates"),
        static_folder=_pasta_recursos("static"),
    )
    app.config.from_object(config_class)

    db.init_app(app)

    # filtros Jinja para máscara de moeda e data
    app.jinja_env.filters["moeda"] = format_currency
    app.jinja_env.filters["data"] = format_date
    app.jinja_env.filters["data_curta"] = format_date_curta
    app.jinja_env.filters["competencia"] = format_competencia
    app.jinja_env.filters["tojson_attr"] = _tojson_atributo

    from app.routes.categorias import bp as categorias_bp
    from app.routes.contas import bp as contas_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.investimentos import bp as investimentos_bp
    from app.routes.locais import bp as locais_bp
    from app.routes.receitas import bp as receitas_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(contas_bp)
    app.register_blueprint(receitas_bp)
    app.register_blueprint(investimentos_bp)
    app.register_blueprint(categorias_bp)
    app.register_blueprint(locais_bp)

    with app.app_context():
        db.create_all()
        _migrar_schema()
        _seed_categorias()
        _seed_locais()
        # mantém sempre o mês atual + horizonte gerado
        from app.utils import gerar_lancamentos_futuros

        gerar_lancamentos_futuros(db, app.config.get("HORIZONTE_MESES", 5))

    return app


def _migrar_schema():
    """Migração leve: adiciona colunas novas em bancos já existentes (criados
    antes de alguma alteração no modelo), sem apagar os dados já cadastrados.
    db.create_all() só cria tabelas que ainda não existem, então colunas
    novas em tabelas antigas precisam ser adicionadas manualmente aqui."""
    from sqlalchemy import inspect, text

    inspetor = inspect(db.engine)

    colunas_receita = {c["name"] for c in inspetor.get_columns("receita")}
    if "recorrencia" not in colunas_receita:
        db.session.execute(
            text(
                "ALTER TABLE receita ADD COLUMN recorrencia VARCHAR(20) DEFAULT 'recorrente'"
            )
        )
    if "data_unica" not in colunas_receita:
        db.session.execute(text("ALTER TABLE receita ADD COLUMN data_unica DATE"))
    if "responsavel_id" not in colunas_receita:
        db.session.execute(
            text("ALTER TABLE receita ADD COLUMN responsavel_id INTEGER")
        )

    colunas_conta = {c["name"] for c in inspetor.get_columns("conta")}
    if "eh_cartao" not in colunas_conta:
        db.session.execute(
            text("ALTER TABLE conta ADD COLUMN eh_cartao BOOLEAN DEFAULT 0")
        )
    if "dia_fechamento" not in colunas_conta:
        db.session.execute(text("ALTER TABLE conta ADD COLUMN dia_fechamento INTEGER"))
    if "local_id" not in colunas_conta:
        db.session.execute(text("ALTER TABLE conta ADD COLUMN local_id INTEGER"))

    colunas_lancamento = {c["name"] for c in inspetor.get_columns("lancamento")}
    if "cartao_id" not in colunas_lancamento:
        db.session.execute(text("ALTER TABLE lancamento ADD COLUMN cartao_id INTEGER"))
    if "pago_com_receita_id" not in colunas_lancamento:
        db.session.execute(
            text("ALTER TABLE lancamento ADD COLUMN pago_com_receita_id INTEGER")
        )

    db.session.commit()


def _seed_locais():
    """Garante que todo valor de 'local'/'responsavel' já usado em contas e
    receitas exista como um Local cadastrado (com local_id/responsavel_id
    apontando pra ele) — assim quem já usava o sistema não perde nada ao
    migrar da lista fixa antiga para o cadastro novo."""
    from app.models import Conta, Local, Receita

    cores_padrao = ["#1f3a5f", "#2ecc71", "#e67e22", "#9b59b6", "#e74c3c", "#16a085"]

    if Local.query.count() == 0:
        for i, nome in enumerate(["Casa", "Vinicius", "Gislaine"]):
            db.session.add(Local(nome=nome, cor=cores_padrao[i % len(cores_padrao)]))
        db.session.commit()

    cache = {l.nome: l for l in Local.query.all()}

    def _garantir_local(nome):
        if not nome:
            return None
        if nome not in cache:
            novo = Local(nome=nome, cor=cores_padrao[len(cache) % len(cores_padrao)])
            db.session.add(novo)
            db.session.flush()
            cache[nome] = novo
        return cache[nome]

    mudou = False
    for conta in Conta.query.filter_by(local_id=None).all():
        local_obj = _garantir_local(conta.local)
        if local_obj:
            conta.local_id = local_obj.id
            mudou = True
    for receita in Receita.query.filter_by(responsavel_id=None).all():
        local_obj = _garantir_local(receita.responsavel)
        if local_obj:
            receita.responsavel_id = local_obj.id
            mudou = True
    if mudou:
        db.session.commit()


def _seed_categorias():
    from app.models import Categoria

    padrao = [
        ("Luz", "#f1c40f", "bi-lightning-charge"),
        ("Água", "#3498db", "bi-droplet"),
        ("Internet", "#9b59b6", "bi-wifi"),
        ("Telefonia", "#1abc9c", "bi-telephone"),
        ("Locação", "#e67e22", "bi-house"),
        ("Cartão de Crédito", "#e74c3c", "bi-credit-card"),
        ("Financiamento", "#c0392b", "bi-bank"),
        ("Empréstimo", "#d35400", "bi-cash-coin"),
        ("Consórcio", "#8e44ad", "bi-people"),
        ("Imposto", "#7f8c8d", "bi-file-earmark-text"),
        ("Seguro", "#2980b9", "bi-shield-check"),
        ("Combustível", "#16a085", "bi-fuel-pump"),
        ("Mercado", "#27ae60", "bi-cart"),
        ("Investimento", "#2ecc71", "bi-graph-up-arrow"),
        ("Outros", "#95a5a6", "bi-three-dots"),
    ]
    if Categoria.query.count() == 0:
        for nome, cor, icone in padrao:
            db.session.add(Categoria(nome=nome, cor=cor, icone=icone))
        db.session.commit()
    else:
        existentes = {c.nome for c in Categoria.query.all()}
        for nome, cor, icone in padrao:
            if nome not in existentes:
                db.session.add(Categoria(nome=nome, cor=cor, icone=icone))
        db.session.commit()
