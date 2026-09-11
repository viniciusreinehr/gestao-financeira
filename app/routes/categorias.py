from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Categoria

bp = Blueprint("categorias", __name__, url_prefix="/categorias")

CORES_SUGERIDAS = [
    "#f1c40f",
    "#3498db",
    "#9b59b6",
    "#1abc9c",
    "#e67e22",
    "#e74c3c",
    "#c0392b",
    "#d35400",
    "#8e44ad",
    "#7f8c8d",
    "#2980b9",
    "#16a085",
    "#27ae60",
    "#2ecc71",
    "#95a5a6",
]


@bp.route("/")
def listar():
    categorias = Categoria.query.order_by(Categoria.nome).all()
    return render_template(
        "categorias.html", categorias=categorias, cores=CORES_SUGERIDAS
    )


@bp.route("/nova", methods=["POST"])
def nova():
    nome = request.form["nome"].strip()
    if Categoria.query.filter_by(nome=nome).first():
        flash("Já existe uma categoria com esse nome.", "danger")
    else:
        cat = Categoria(
            nome=nome,
            cor=request.form.get("cor") or "#6c757d",
            icone=request.form.get("icone") or "bi-tag",
        )
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoria "{nome}" criada.', "success")
    return redirect(url_for("categorias.listar"))


@bp.route("/<int:categoria_id>/excluir", methods=["POST"])
def excluir(categoria_id):
    categoria = Categoria.query.get_or_404(categoria_id)
    if categoria.contas:
        flash("Não é possível excluir: existem contas usando essa categoria.", "danger")
    else:
        db.session.delete(categoria)
        db.session.commit()
        flash("Categoria removida.", "success")
    return redirect(url_for("categorias.listar"))
