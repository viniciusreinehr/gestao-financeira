from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue

from app.extensions import db
from app.models import (
    FORMAS_PAGAMENTO,
    STATUS_PAGO,
    TIPO_LANCAMENTO_RECORRENTE,
    TIPOS_LANCAMENTO,
    Categoria,
    Conta,
    Lancamento,
    LancamentoRateio,
    Local,
)
from app.services.payment_service import quitar_conta_parcelada
from app.utils import (
    atualizar_lancamentos_em_aberto,
    calcular_custo_estimado,
    calcular_media_provisionamento,
    conta_cartao_vinculado,
    conta_eh_absorvida_por_cartao,
    criar_lancamento_inicial,
    gerar_lancamentos_futuros,
    itens_fatura_cartao,
    lista_meses,
    marcar_conta_recem_criada_como_paga,
    opcoes_forma_pagamento,
)

bp = Blueprint("contas", __name__, url_prefix="/contas")


def _parse_decimal(texto, default=None):
    if not texto:
        return default
    try:
        return Decimal(str(texto).replace(".", "").replace(",", "."))
    except InvalidOperation:
        return default


def _forma_padrao_para_selecao(conta):
    """Normaliza forma_pagamento_padrao para o formato codificado usado nos
    <option value> do select (ex.: 'Pix' antigo -> 'generico:Pix'), para que
    o valor salvo continue vindo selecionado corretamente no formulário."""
    if not conta or not conta.forma_pagamento_padrao:
        return "generico:Manual / Boleto"
    valor = conta.forma_pagamento_padrao
    return valor if ":" in valor else f"generico:{valor}"


@bp.route("/")
def listar():
    gerar_lancamentos_futuros(db, current_app.config.get("HORIZONTE_MESES", 5))

    categoria_id = request.args.get("categoria_id", type=int)
    local_id = request.args.get("local_id", type=int)
    situacao = request.args.get("situacao")

    query = Conta.query
    if categoria_id:
        query = query.filter_by(categoria_id=categoria_id)
    if local_id:
        query = query.filter_by(local_id=local_id)
    if situacao == "quitada":
        query = query.filter_by(quitada=True)
    elif situacao == "inativa":
        query = query.filter_by(ativa=False)
    elif situacao == "ativa":
        query = query.filter_by(ativa=True, quitada=False)
    contas = query.order_by(Conta.ativa.desc(), Conta.nome).all()

    # custo médio mensal de cada conta (base para "visão do custo de cada conta")
    custos = {c.id: calcular_custo_estimado(c) for c in contas}

    # Total do cabeçalho: só contas ATIVAS, e sem contar duas vezes o que já
    # está embutido na fatura de um cartão (a própria fatura do cartão já
    # reflete esse valor).
    total_mensal = sum(
        (
            custos[c.id]
            for c in contas
            if c.ativa and not conta_eh_absorvida_por_cartao(c)
        ),
        Decimal(0),
    )

    # Agrupa visualmente: cada conta paga sempre com um cartão aparece logo
    # abaixo dele, indentada, para deixar claro que faz parte da fatura dele.
    cartoes_no_conjunto = {c.id for c in contas if c.eh_cartao}
    vinculo = {}
    for c in contas:
        if not c.eh_cartao:
            cartao = conta_cartao_vinculado(c)
            if cartao and cartao.id in cartoes_no_conjunto:
                vinculo[c.id] = cartao.id

    usadas = set()
    contas_agrupadas = []
    for c in contas:
        if c.id in usadas or vinculo.get(c.id):
            # Conta vinculada a um cartão: não é emitida aqui como linha
            # solta — ela será inserida na hora certa, indentada, quando o
            # loop chegar no cartão. Sem esse skip, uma conta cujo nome
            # vem antes do nome do cartão na ordenação alfabética seria
            # processada primeiro e nunca mais agrupada abaixo dele.
            continue
        contas_agrupadas.append((c, False))
        usadas.add(c.id)
        if c.eh_cartao:
            for outra in contas:
                if outra.id not in usadas and vinculo.get(outra.id) == c.id:
                    contas_agrupadas.append((outra, True))
                    usadas.add(outra.id)

    # Contas vinculadas cujo cartão não está neste conjunto (ex.: cartão
    # filtrado pelos filtros da listagem, ou o próprio cartão inativo e
    # fora do resultado) continuam aparecendo normalmente, sem indentação.
    for c in contas:
        if c.id not in usadas:
            contas_agrupadas.append((c, False))
            usadas.add(c.id)

    categorias = Categoria.query.order_by(Categoria.nome).all()
    locais = Local.query.order_by(Local.nome).all()

    return render_template(
        "contas/list.html",
        contas_agrupadas=contas_agrupadas,
        custos=custos,
        total_mensal=total_mensal,
        categorias=categorias,
        locais=locais,
        categoria_id=categoria_id,
        local_id=local_id,
        situacao=situacao,
    )


@bp.route("/nova", methods=["GET", "POST"])
def nova():
    categorias = Categoria.query.order_by(Categoria.nome).all()

    if request.method == "POST":
        eh_cartao = request.form.get("eh_cartao") == "on"
        local_id = (
            int(request.form["local_id"]) if request.form.get("local_id") else None
        )
        local_obj = Local.query.get(local_id) if local_id else None
        conta = Conta(
            nome=request.form["nome"].strip(),
            categoria_id=int(request.form["categoria_id"]),
            local_id=local_id,
            local=local_obj.nome if local_obj else None,
            tipo_lancamento=TIPO_LANCAMENTO_RECORRENTE
            if eh_cartao
            else request.form["tipo_lancamento"],
            provisionar=(not eh_cartao) and request.form.get("provisionar") == "on",
            dia_vencimento=int(request.form.get("dia_vencimento") or 10),
            valor_base=Decimal(0)
            if eh_cartao
            else _parse_decimal(request.form.get("valor_base"), Decimal(0)),
            num_parcelas=None
            if eh_cartao
            else (
                int(request.form["num_parcelas"])
                if request.form.get("num_parcelas")
                else None
            ),
            forma_pagamento_padrao=request.form.get("forma_pagamento_padrao")
            or "Manual / Boleto",
            eh_cartao=eh_cartao,
            dia_fechamento=int(request.form["dia_fechamento"])
            if eh_cartao and request.form.get("dia_fechamento")
            else None,
            observacao=request.form.get("observacao"),
        )
        db.session.add(conta)
        db.session.commit()

        # Lançar retroativamente algo que já aconteceu (ex.: uma compra do
        # mês passado que foi esquecida) — ancora o primeiro lançamento
        # nessa data em vez de hoje.
        data_criacao_texto = request.form.get("data_criacao")
        if not eh_cartao and data_criacao_texto:
            data_criacao = datetime.strptime(data_criacao_texto, "%Y-%m-%d").date()
            criar_lancamento_inicial(db, conta, data_criacao)

        gerar_lancamentos_futuros(db, current_app.config.get("HORIZONTE_MESES", 5))

        if not eh_cartao and request.form.get("ja_paga") == "on":
            forma_raw = request.form.get("ja_paga_forma")
            data_texto = request.form.get("ja_paga_data")
            data_pagamento = (
                datetime.strptime(data_texto, "%Y-%m-%d").date()
                if data_texto
                else date.today()
            )
            valor_e_total = request.form.get("ja_paga_valor_e_total") == "on"
            marcar_conta_recem_criada_como_paga(
                db,
                conta,
                forma_raw,
                data_pagamento,
                request.form.get("ja_paga_valor"),
                valor_e_total_parcelado=valor_e_total,
            )
            flash(f'Conta "{conta.nome}" cadastrada e marcada como paga.', "success")
        else:
            flash(f'Conta "{conta.nome}" cadastrada com sucesso.', "success")

        return redirect(url_for("contas.detalhe", conta_id=conta.id))

    return render_template(
        "contas/form.html",
        conta=None,
        categorias=categorias,
        tipos=TIPOS_LANCAMENTO,
        locais=Local.query.order_by(Local.nome).all(),
        formas=FORMAS_PAGAMENTO,
        opcoes_forma_pagamento=opcoes_forma_pagamento(),
        forma_pagamento_padrao_atual=_forma_padrao_para_selecao(None),
    )


@bp.route("/<int:conta_id>/editar", methods=["GET", "POST"])
def editar(conta_id):
    conta = Conta.query.get_or_404(conta_id)
    categorias = Categoria.query.order_by(Categoria.nome).all()

    if request.method == "POST":
        eh_cartao = request.form.get("eh_cartao") == "on"
        local_id = (
            int(request.form["local_id"]) if request.form.get("local_id") else None
        )
        local_obj = Local.query.get(local_id) if local_id else None
        conta.nome = request.form["nome"].strip()
        conta.categoria_id = int(request.form["categoria_id"])
        conta.local_id = local_id
        conta.local = local_obj.nome if local_obj else None
        conta.tipo_lancamento = (
            TIPO_LANCAMENTO_RECORRENTE if eh_cartao else request.form["tipo_lancamento"]
        )
        conta.provisionar = (not eh_cartao) and request.form.get("provisionar") == "on"
        conta.dia_vencimento = int(request.form.get("dia_vencimento") or 10)
        conta.valor_base = (
            Decimal(0)
            if eh_cartao
            else _parse_decimal(request.form.get("valor_base"), Decimal(0))
        )
        conta.num_parcelas = (
            None
            if eh_cartao
            else (
                int(request.form["num_parcelas"])
                if request.form.get("num_parcelas")
                else None
            )
        )
        conta.forma_pagamento_padrao = (
            request.form.get("forma_pagamento_padrao") or "Manual / Boleto"
        )
        conta.eh_cartao = eh_cartao
        conta.dia_fechamento = (
            int(request.form["dia_fechamento"])
            if eh_cartao and request.form.get("dia_fechamento")
            else None
        )
        conta.ativa = request.form.get("ativa") == "on"
        conta.observacao = request.form.get("observacao")
        db.session.commit()
        gerar_lancamentos_futuros(db, current_app.config.get("HORIZONTE_MESES", 5))

        if (not eh_cartao) and request.form.get(
            "atualizar_lancamentos_abertos"
        ) == "on":
            atualizar_dia = request.form.get("atualizar_dia_vencimento") == "on"
            qtd = atualizar_lancamentos_em_aberto(
                conta, atualizar_dia_vencimento=atualizar_dia
            )
            db.session.commit()
            if qtd:
                flash(
                    f"Conta atualizada — {qtd} lançamento(s) em aberto também "
                    f"foram ajustados para o novo valor.",
                    "success",
                )
            else:
                flash(
                    "Conta atualizada com sucesso. Não havia lançamentos em aberto para ajustar.",
                    "success",
                )
        else:
            flash("Conta atualizada com sucesso.", "success")

        return redirect(url_for("contas.detalhe", conta_id=conta.id))

    return render_template(
        "contas/form.html",
        conta=conta,
        categorias=categorias,
        tipos=TIPOS_LANCAMENTO,
        locais=Local.query.order_by(Local.nome).all(),
        formas=FORMAS_PAGAMENTO,
        opcoes_forma_pagamento=opcoes_forma_pagamento(),
        forma_pagamento_padrao_atual=_forma_padrao_para_selecao(conta),
    )


@bp.route("/<int:conta_id>/excluir", methods=["POST"])
def excluir(conta_id):
    conta = Conta.query.get_or_404(conta_id)
    nome = conta.nome

    # Se for um cartão de crédito, outras contas podem ter lançamentos
    # vinculados a ele (cartao_id) — precisa desvincular antes de excluir,
    # senão ficariam referências soltas apontando para uma conta inexistente.
    if conta.eh_cartao:
        Lancamento.query.filter_by(cartao_id=conta.id).update(
            {"cartao_id": None}, synchronize_session=False
        )
        LancamentoRateio.query.filter_by(cartao_id=conta.id).update(
            {"cartao_id": None}, synchronize_session=False
        )

    db.session.delete(conta)  # cascade: apaga também todos os lançamentos desta conta
    db.session.commit()
    flash(f'Conta "{nome}" e todos os seus lançamentos foram removidos.', "success")
    return redirect(url_for("contas.listar"))


@bp.route("/<int:conta_id>")
def detalhe(conta_id):
    conta = Conta.query.get_or_404(conta_id)

    # Ordenação: a pagar (vencimento crescente) primeiro, depois pagas
    # (data de pagamento decrescente) — mais fácil ver o que vem antes e
    # revisar o que já foi pago do mais recente para o mais antigo.
    abertos = sorted(
        (l for l in conta.lancamentos if l.status != STATUS_PAGO),
        key=lambda l: l.vencimento,
    )
    pagos = sorted(
        (l for l in conta.lancamentos if l.status == STATUS_PAGO),
        key=lambda l: l.data_pagamento or l.vencimento,
        reverse=True,
    )
    lancamentos = abertos + pagos

    media_provisionamento = (
        calcular_media_provisionamento(conta) if conta.provisionar else None
    )
    lancamentos_abertos_count = len(abertos)
    formas = FORMAS_PAGAMENTO
    hoje = date.today()

    # Para cartões: lista as compras (diretas ou parte de um pagamento
    # dividido) que compõem cada fatura, agrupadas por competência.
    compras_por_fatura = {}
    if conta.eh_cartao:
        competencias = {l.competencia for l in conta.lancamentos}
        for comp in competencias:
            itens = itens_fatura_cartao(conta, comp)
            if itens:
                compras_por_fatura[comp] = itens

    return render_template(
        "contas/detalhe.html",
        conta=conta,
        lancamentos=lancamentos,
        media_provisionamento=media_provisionamento,
        lancamentos_abertos_count=lancamentos_abertos_count,
        compras_por_fatura=compras_por_fatura,
        formas=formas,
        formas_pagamento=formas,
        opcoes_forma_pagamento=opcoes_forma_pagamento(),
        meses_nome=lista_meses(),
        anos_competencia=range(hoje.year - 1, hoje.year + 3),
        hoje=hoje,
    )


@bp.route("/<int:conta_id>/atualizar-lancamentos", methods=["POST"])
def atualizar_lancamentos(conta_id):
    """Reaplica o valor atual da conta (valor_base, ou a média de
    provisionamento recalculada) a todos os lançamentos ainda não pagos —
    útil depois de descobrir que o valor cadastrado estava errado."""
    conta = Conta.query.get_or_404(conta_id)
    atualizar_dia = request.form.get("atualizar_dia_vencimento") == "on"

    qtd = atualizar_lancamentos_em_aberto(conta, atualizar_dia_vencimento=atualizar_dia)
    db.session.commit()

    if qtd:
        flash(f"{qtd} lançamento(s) em aberto atualizado(s) com sucesso.", "success")
    else:
        flash("Não há lançamentos em aberto para atualizar nessa conta.", "warning")

    return redirect(url_for("contas.detalhe", conta_id=conta.id))


@bp.route("/<int:conta_id>/quitar", methods=["POST"])
def quitar(conta_id: int) -> ResponseReturnValue:
    """Quita antecipadamente um financiamento/empréstimo/consórcio parcelado delegando ao serviço de pagamento."""
    conta = Conta.query.get_or_404(conta_id)

    valor_quitacao = _parse_decimal(request.form.get("valor_quitacao"))
    if not valor_quitacao:
        flash("Informe o valor da quitação.", "danger")
        return redirect(url_for("contas.detalhe", conta_id=conta.id))

    data_quitacao_str = request.form.get("data_quitacao")
    data_quitacao = (
        datetime.strptime(data_quitacao_str, "%Y-%m-%d").date()
        if data_quitacao_str
        else date.today()
    )

    try:
        quit_reg = quitar_conta_parcelada(
            db_session=db.session,
            conta=conta,
            valor_quitacao=valor_quitacao,
            data_quitacao=data_quitacao,
            observacao=request.form.get("observacao"),
        )
        flash(
            f"Conta quitada: {quit_reg.parcelas_restantes} parcela(s) baixada(s) com sucesso.",
            "success",
        )
    except ValueError as e:
        flash(str(e), "warning")

    return redirect(url_for("contas.detalhe", conta_id=conta.id))