from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Investimento

bp = Blueprint("investimentos", __name__, url_prefix="/investimentos")

TIPOS_INVESTIMENTO = [
    "CDB",
    "Tesouro Direto",
    "Poupança",
    "Fundo",
    "Ações",
    "LCI/LCA",
    "Consórcio",
    "Outro",
]


def _parse_decimal(texto, default=None):
    if not texto:
        return default
    try:
        return Decimal(str(texto).replace(".", "").replace(",", "."))
    except InvalidOperation:
        return default


@bp.route("/")
def listar():
    investimentos = (
        Investimento.query.filter_by(ativo=True).order_by(Investimento.nome).all()
    )
    linhas = []
    total_investido = Decimal(0)
    total_projetado = Decimal(0)
    for inv in investimentos:
        projetado = inv.valor_projetado()
        total_investido += Decimal(inv.valor_inicial)
        total_projetado += projetado
        linhas.append(
            {
                "inv": inv,
                "projetado": projetado,
                "rendimento": projetado - Decimal(inv.valor_inicial),
            }
        )

    return render_template(
        "investimentos/list.html",
        linhas=linhas,
        total_investido=total_investido,
        total_projetado=total_projetado,
    )


@bp.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        inv = Investimento(
            nome=request.form["nome"].strip(),
            banco=request.form.get("banco"),
            tipo=request.form.get("tipo") or "CDB",
            valor_inicial=_parse_decimal(request.form.get("valor_inicial"), Decimal(0)),
            data_aplicacao=datetime.strptime(
                request.form["data_aplicacao"], "%Y-%m-%d"
            ).date(),
            taxa_mensal_pct=_parse_decimal(request.form.get("taxa_mensal_pct")),
            vencimento=(
                datetime.strptime(request.form["vencimento"], "%Y-%m-%d").date()
                if request.form.get("vencimento")
                else None
            ),
            liquidez_diaria=request.form.get("liquidez_diaria") == "on",
            observacao=request.form.get("observacao"),
        )
        db.session.add(inv)
        db.session.commit()
        flash(f'Investimento "{inv.nome}" cadastrado.', "success")
        return redirect(url_for("investimentos.listar"))

    return render_template(
        "investimentos/form.html", inv=None, tipos=TIPOS_INVESTIMENTO
    )


@bp.route("/<int:inv_id>/editar", methods=["GET", "POST"])
def editar(inv_id):
    inv = Investimento.query.get_or_404(inv_id)

    if request.method == "POST":
        inv.nome = request.form["nome"].strip()
        inv.banco = request.form.get("banco")
        inv.tipo = request.form.get("tipo") or "CDB"
        inv.valor_inicial = _parse_decimal(
            request.form.get("valor_inicial"), Decimal(0)
        )
        inv.data_aplicacao = datetime.strptime(
            request.form["data_aplicacao"], "%Y-%m-%d"
        ).date()
        inv.taxa_mensal_pct = _parse_decimal(request.form.get("taxa_mensal_pct"))
        inv.vencimento = (
            datetime.strptime(request.form["vencimento"], "%Y-%m-%d").date()
            if request.form.get("vencimento")
            else None
        )
        inv.liquidez_diaria = request.form.get("liquidez_diaria") == "on"
        inv.ativo = request.form.get("ativo") == "on"
        inv.observacao = request.form.get("observacao")
        db.session.commit()
        flash("Investimento atualizado.", "success")
        return redirect(url_for("investimentos.listar"))

    return render_template("investimentos/form.html", inv=inv, tipos=TIPOS_INVESTIMENTO)


@bp.route("/<int:inv_id>/atualizar-valor", methods=["POST"])
def atualizar_valor(inv_id):
    inv = Investimento.query.get_or_404(inv_id)
    valor = _parse_decimal(request.form.get("valor_atual_manual"))
    data_str = request.form.get("data_atualizacao_manual")
    if valor is None:
        flash("Informe o valor atualizado.", "danger")
        return redirect(url_for("investimentos.listar"))

    inv.valor_atual_manual = valor
    inv.data_atualizacao_manual = (
        datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()
    )
    db.session.commit()
    flash(f'Valor de "{inv.nome}" atualizado manualmente.', "success")
    return redirect(url_for("investimentos.listar"))


@bp.route("/<int:inv_id>/excluir", methods=["POST"])
def excluir(inv_id):
    inv = Investimento.query.get_or_404(inv_id)
    db.session.delete(inv)
    db.session.commit()
    flash("Investimento removido.", "success")
    return redirect(url_for("investimentos.listar"))
