from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue

from app.extensions import db
from app.models import FORMAS_PAGAMENTO, Lancamento
from app.services.dashboard_service import obter_dados_completos_dashboard
from app.services.lancamento_service import (
    atualizar_lancamento_from_form,
    pontos_fatura_afetados,
    recalcular_pontos_fatura,
)
from app.utils import (
    gerar_lancamentos_futuros,
    lista_meses,
    opcoes_forma_pagamento,
)

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index() -> ResponseReturnValue:
    """Visão geral financeira: consolidado mensal, próximos vencimentos e saldo previsto."""
    horizonte = current_app.config.get("HORIZONTE_MESES", 5)
    gerar_lancamentos_futuros(db, horizonte)

    dados = obter_dados_completos_dashboard(horizonte)
    hoje = dados["hoje"]

    return render_template(
        "dashboard.html",
        meses=dados["meses"],
        mes_atual=dados["mes_atual"],
        proximos_vencimentos=dados["proximos_vencimentos"],
        atrasados=dados["atrasados"],
        custo_categoria=dados["custo_categoria"],
        formas_pagamento=FORMAS_PAGAMENTO,
        opcoes_forma_pagamento=opcoes_forma_pagamento(),
        meses_nome=lista_meses(),
        anos_competencia=range(hoje.year - 1, hoje.year + 3),
        hoje=hoje,
    )


@bp.route("/lancamentos/<int:lancamento_id>/atualizar", methods=["POST"])
def atualizar_lancamento(lancamento_id: int) -> ResponseReturnValue:
    """Atualiza dados, baixa e rateio de um lançamento delegando ao serviço de lançamentos."""
    lanc = Lancamento.query.get_or_404(lancamento_id)
    rateio_formas = request.form.getlist("rateio_forma[]")
    rateio_valores = request.form.getlist("rateio_valor[]")

    atualizar_lancamento_from_form(
        db_session=db.session,
        lancamento=lanc,
        form=request.form,
        rateio_formas=rateio_formas,
        rateio_valores=rateio_valores,
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})

    flash("Lançamento atualizado com sucesso.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))


@bp.route("/lancamentos/<int:lancamento_id>/excluir", methods=["POST"])
def excluir_lancamento(lancamento_id: int) -> ResponseReturnValue:
    """Remove um lançamento e atualiza faturas de cartão afetadas."""
    lanc = Lancamento.query.get_or_404(lancamento_id)
    conta_id = lanc.conta_id

    pontos_antes = pontos_fatura_afetados(lancamento_id)

    db.session.delete(lanc)
    db.session.commit()

    recalcular_pontos_fatura(db.session, pontos_antes)
    db.session.commit()

    flash("Lançamento removido.", "success")
    return redirect(request.referrer or url_for("contas.detalhe", conta_id=conta_id))
