from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Local
from app.utils import calcular_custo_estimado, conta_eh_absorvida_por_cartao

bp = Blueprint("locais", __name__, url_prefix="/locais")

CORES_SUGERIDAS = [
    "#1f3a5f",
    "#2ecc71",
    "#e67e22",
    "#9b59b6",
    "#e74c3c",
    "#16a085",
    "#2980b9",
    "#d35400",
    "#8e44ad",
    "#c0392b",
    "#27ae60",
    "#7f8c8d",
]


@bp.route("/")
def listar():
    locais = Local.query.order_by(Local.nome).all()

    resumo = []
    for local in locais:
        contas = [c for c in local.contas if c.ativa]
        total = sum(
            (
                calcular_custo_estimado(c)
                for c in contas
                if not conta_eh_absorvida_por_cartao(c)
            ),
            Decimal(0),
        )
        resumo.append(
            {
                "local": local,
                "qtd_contas": len(contas),
                "qtd_receitas": len([r for r in local.receitas if r.ativo]),
                "total_mensal": total,
            }
        )

    return render_template("locais/list.html", resumo=resumo, cores=CORES_SUGERIDAS)


@bp.route("/<int:local_id>")
def detalhe(local_id):
    local = Local.query.get_or_404(local_id)
    contas = sorted(local.contas, key=lambda c: (not c.ativa, c.nome))
    custos = {c.id: calcular_custo_estimado(c) for c in contas}
    receitas = sorted(local.receitas, key=lambda r: (not r.ativo, r.tipo))
    return render_template(
        "locais/detalhe.html",
        local=local,
        contas=contas,
        custos=custos,
        receitas=receitas,
    )


@bp.route("/novo", methods=["POST"])
def novo():
    nome = request.form["nome"].strip()
    if Local.query.filter_by(nome=nome).first():
        flash(f'Já existe um local/responsável chamado "{nome}".', "danger")
    else:
        local = Local(nome=nome, cor=request.form.get("cor") or "#6c757d")
        db.session.add(local)
        db.session.commit()
        flash(f'"{nome}" cadastrado com sucesso.', "success")
    return redirect(url_for("locais.listar"))


@bp.route("/<int:local_id>/editar", methods=["POST"])
def editar(local_id):
    local = Local.query.get_or_404(local_id)
    nome = request.form["nome"].strip()
    if nome != local.nome and Local.query.filter_by(nome=nome).first():
        flash(f'Já existe um local/responsável chamado "{nome}".', "danger")
    else:
        local.nome = nome
        local.cor = request.form.get("cor") or local.cor
        db.session.commit()
        flash("Atualizado com sucesso.", "success")
    return redirect(url_for("locais.listar"))


@bp.route("/<int:local_id>/excluir", methods=["POST"])
def excluir(local_id):
    local = Local.query.get_or_404(local_id)
    if local.contas or local.receitas:
        flash(
            "Não é possível excluir: existem contas ou receitas vinculadas a este local/responsável.",
            "danger",
        )
    else:
        db.session.delete(local)
        db.session.commit()
        flash("Removido com sucesso.", "success")
    return redirect(url_for("locais.listar"))
