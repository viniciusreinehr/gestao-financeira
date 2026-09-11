from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import (
    RECORRENCIA_RECEITA_RECORRENTE,
    RECORRENCIA_RECEITA_UNICA,
    RECORRENCIAS_RECEITA,
    REGRAS_DATA_RECEITA,
    Local,
    Receita,
    ReceitaRecebimento,
)
from app.utils import format_competencia, format_currency

bp = Blueprint("receitas", __name__, url_prefix="/receitas")


def _parse_decimal(texto, default=None):
    if not texto:
        return default
    try:
        return Decimal(str(texto).replace(".", "").replace(",", "."))
    except InvalidOperation:
        return default


def _preencher_receita_a_partir_do_form(receita, form):
    receita.tipo = form["tipo"].strip()
    receita.origem = form["origem"].strip()
    responsavel_id = int(form["responsavel_id"]) if form.get("responsavel_id") else None
    responsavel_obj = Local.query.get(responsavel_id) if responsavel_id else None
    receita.responsavel_id = responsavel_id
    receita.responsavel = responsavel_obj.nome if responsavel_obj else None
    receita.valor = _parse_decimal(form.get("valor"), Decimal(0))
    receita.observacao = form.get("observacao")

    receita.recorrencia = form.get("recorrencia") or RECORRENCIA_RECEITA_RECORRENTE

    if receita.recorrencia == RECORRENCIA_RECEITA_UNICA:
        data_unica = form.get("data_unica")
        receita.data_unica = (
            datetime.strptime(data_unica, "%Y-%m-%d").date() if data_unica else None
        )
        receita.regra_data = None
        receita.dia_fixo = None
        receita.n_dia_util = None
    else:
        receita.regra_data = form.get("regra_data") or "dia_fixo"
        receita.dia_fixo = int(form["dia_fixo"]) if form.get("dia_fixo") else None
        receita.n_dia_util = int(form["n_dia_util"]) if form.get("n_dia_util") else None
        receita.data_unica = None

    return receita


@bp.route("/")
def listar():
    receitas = Receita.query.order_by(Receita.ativo.desc(), Receita.tipo).all()
    total_ativas = sum(
        (
            r.valor
            for r in receitas
            if r.ativo and r.recorrencia == RECORRENCIA_RECEITA_RECORRENTE
        ),
        Decimal(0),
    )
    return render_template(
        "receitas/list.html", receitas=receitas, total_ativas=total_ativas
    )


@bp.route("/nova", methods=["GET", "POST"])
def nova():
    if request.method == "POST":
        receita = _preencher_receita_a_partir_do_form(Receita(), request.form)
        db.session.add(receita)
        db.session.commit()
        flash(f'Receita "{receita.tipo} - {receita.origem}" cadastrada.', "success")
        return redirect(url_for("receitas.listar"))

    return render_template(
        "receitas/form.html",
        receita=None,
        regras=REGRAS_DATA_RECEITA,
        recorrencias=RECORRENCIAS_RECEITA,
        locais=Local.query.order_by(Local.nome).all(),
    )


@bp.route("/<int:receita_id>/editar", methods=["GET", "POST"])
def editar(receita_id):
    receita = Receita.query.get_or_404(receita_id)

    if request.method == "POST":
        _preencher_receita_a_partir_do_form(receita, request.form)
        receita.ativo = request.form.get("ativo") == "on"
        db.session.commit()
        flash("Receita atualizada.", "success")
        return redirect(url_for("receitas.listar"))

    return render_template(
        "receitas/form.html",
        receita=receita,
        regras=REGRAS_DATA_RECEITA,
        recorrencias=RECORRENCIAS_RECEITA,
        locais=Local.query.order_by(Local.nome).all(),
    )


@bp.route("/<int:receita_id>/excluir", methods=["POST"])
def excluir(receita_id):
    receita = Receita.query.get_or_404(receita_id)
    db.session.delete(receita)
    db.session.commit()
    flash("Receita removida.", "success")
    return redirect(url_for("receitas.listar"))


@bp.route("/<int:receita_id>/confirmar", methods=["POST"])
def confirmar_recebimento(receita_id):
    """Registra o valor efetivamente recebido num mês específico (competência),
    para substituir a previsão pelo valor real na visão do dashboard —
    ex.: previsão de comissão R$ 400, mas naquele mês entrou R$ 800."""
    receita = Receita.query.get_or_404(receita_id)

    competencia = request.form.get("competencia")
    if not competencia:
        flash("Competência inválida.", "danger")
        return redirect(request.referrer or url_for("dashboard.index"))

    valor_recebido = _parse_decimal(request.form.get("valor_recebido"))
    data_recebimento = request.form.get("data_recebimento")

    recebimento = ReceitaRecebimento.query.filter_by(
        receita_id=receita.id, competencia=competencia
    ).first()
    if not recebimento:
        recebimento = ReceitaRecebimento(receita_id=receita.id, competencia=competencia)
        db.session.add(recebimento)

    recebimento.valor_recebido = (
        valor_recebido if valor_recebido is not None else receita.valor
    )
    recebimento.data_recebimento = (
        datetime.strptime(data_recebimento, "%Y-%m-%d").date()
        if data_recebimento
        else date.today()
    )
    recebimento.recebido = True
    db.session.commit()

    flash(
        f'Recebimento de "{receita.tipo} - {receita.origem}" confirmado para '
        f"{format_competencia(competencia)}: {format_currency(recebimento.valor_recebido)}.",
        "success",
    )
    return redirect(request.referrer or url_for("dashboard.index"))


@bp.route("/recebimentos/<int:recebimento_id>/desfazer", methods=["POST"])
def desfazer_recebimento(recebimento_id):
    """Remove a confirmação de recebimento, voltando a mostrar a previsão
    cadastrada na receita em vez do valor real informado por engano."""
    recebimento = ReceitaRecebimento.query.get_or_404(recebimento_id)
    db.session.delete(recebimento)
    db.session.commit()
    flash("Confirmação removida — voltou a mostrar a previsão.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))
