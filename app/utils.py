import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pprint import pprint

# ---------------------------------------------------------------------------
# Formatação (dd/mm/YYYY e R$ 123.456,78)
# ---------------------------------------------------------------------------


def format_currency(value):
    if value is None:
        value = 0
    value = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negativo = value < 0
    value = abs(value)
    inteiro, centavos = f"{value:.2f}".split(".")
    inteiro_formatado = f"{int(inteiro):,}".replace(",", ".")
    texto = f"R$ {inteiro_formatado},{centavos}"
    return f"-{texto}" if negativo else texto


def format_date(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime("%d/%m/%Y")


def format_date_curta(value):
    """dd/mm, sem o ano — usado em colunas estreitas como 'Venc.' no
    planejamento do dashboard."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime("%d/%m")


MESES_ABREV = [
    "",
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]
MESES_NOME_COMPLETO = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def format_competencia(competencia):
    """'2026-09' -> 'Set/2026'"""
    if not competencia:
        return ""
    ano, mes = competencia.split("-")
    return f"{MESES_ABREV[int(mes)]}/{ano}"


def lista_meses():
    """[(1, 'Janeiro'), (2, 'Fevereiro'), ...] — usado nos seletores de mês."""
    return list(enumerate(MESES_NOME_COMPLETO))[1:]


def competencia_str(ano, mes):
    return f"{ano:04d}-{mes:02d}"


def competencia_para_data(competencia):
    ano, mes = (int(p) for p in competencia.split("-"))
    return ano, mes


def somar_meses(ano, mes, n):
    total = (ano * 12 + (mes - 1)) + n
    return total // 12, total % 12 + 1


def ultimo_dia_mes(ano, mes):
    return calendar.monthrange(ano, mes)[1]


def montar_data(ano, mes, dia):
    dia = max(1, min(dia or 1, ultimo_dia_mes(ano, mes)))
    return date(ano, mes, dia)


# ---------------------------------------------------------------------------
# Dias úteis (considera apenas fins de semana; sem feriados nacionais)
# ---------------------------------------------------------------------------


def enesimo_dia_util(ano, mes, n):
    n = max(1, n or 1)
    dia = date(ano, mes, 1)
    encontrados = 0
    ultimo = ultimo_dia_mes(ano, mes)
    while dia.day <= ultimo:
        if dia.weekday() < 5:  # 0=segunda ... 4=sexta
            encontrados += 1
            if encontrados == n:
                return dia
        dia += timedelta(days=1)
    return date(ano, mes, ultimo)


def calcular_data_receita(receita, ano, mes):
    from app.models import RECORRENCIA_RECEITA_UNICA

    if receita.recorrencia == RECORRENCIA_RECEITA_UNICA:
        if (
            receita.data_unica
            and receita.data_unica.year == ano
            and receita.data_unica.month == mes
        ):
            return receita.data_unica
        return None  # receita única: só aparece no mês exato da data cadastrada

    if receita.regra_data == "dia_util":
        return enesimo_dia_util(ano, mes, receita.n_dia_util or 1)
    return montar_data(ano, mes, receita.dia_fixo or 1)


# ---------------------------------------------------------------------------
# Provisionamento: média dos últimos N meses PAGOS de uma conta variável
# ---------------------------------------------------------------------------


def calcular_media_provisionamento(conta, n_meses=3):
    from app.models import STATUS_PAGO

    pagos = [
        l
        for l in conta.lancamentos
        if l.status == STATUS_PAGO and l.valor_pago is not None
    ]
    pagos.sort(key=lambda l: l.vencimento, reverse=True)
    amostra = pagos[:n_meses]
    if not amostra:
        return Decimal(conta.valor_base or 0)
    soma = sum(Decimal(l.valor_pago) for l in amostra)
    return (soma / len(amostra)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_custo_estimado(conta):
    """Custo mensal estimado de uma conta, usado na listagem de contas e
    na listagem de locais/responsáveis."""
    if conta.provisionar or conta.eh_cartao:
        return calcular_media_provisionamento(conta)
    return Decimal(conta.valor_base or 0)


def conta_cartao_vinculado(conta):
    """Se esta conta é normalmente (ou sempre foi, até agora) paga com um
    cartão de crédito específico, retorna esse cartão (Conta) — usado para
    não contar o custo dela duas vezes nos totais (já está na fatura do
    cartão) e para agrupá-la visualmente abaixo do cartão na listagem."""
    from app.models import STATUS_PAGO, Conta

    if conta.eh_cartao:
        return None
    
    tipo, valor = decompor_forma_pagamento(conta.forma_pagamento_padrao)
    if tipo == "cartao" and valor:
        return Conta.query.get(int(valor))
    
    pagos = [l for l in conta.lancamentos if l.status == STATUS_PAGO]
    pagos_com_cartao = [l for l in pagos if l.cartao_id]
    if pagos and len(pagos_com_cartao) == len(pagos):
        return pagos_com_cartao[0].cartao

    return None


def conta_eh_absorvida_por_cartao(conta):
    """True quando o custo desta conta já está embutido na fatura de um
    cartão (ver conta_cartao_vinculado) — para excluir do total geral e
    evitar contar duas vezes (uma na conta, outra na fatura do cartão)."""
    return conta_cartao_vinculado(conta) is not None


# ---------------------------------------------------------------------------
# Cartão de crédito: em qual fatura (competência) uma compra cai, e cálculo
# do total da fatura a partir das compras vinculadas a esse cartão.
# ---------------------------------------------------------------------------


def competencia_fatura_cartao(cartao, data_compra):
    """Se a compra foi feita no dia de fechamento do cartão ou depois, ela
    cai na fatura do mês seguinte; antes do fechamento, na fatura do mês
    corrente. (Ex.: fecha dia 1 — uma compra feita no próprio dia 1 já
    entra na fatura do mês seguinte, não na que está fechando.)"""
    dia_fechamento = cartao.dia_fechamento or 1
    ano, mes = data_compra.year, data_compra.month
    if data_compra.day >= dia_fechamento:
        ano, mes = somar_meses(ano, mes, 1)
    return competencia_str(ano, mes)


def itens_fatura_cartao(cartao, competencia):
    """Lista as compras (diretas ou parte de um pagamento dividido) que
    compõem a fatura de uma competência específica de um cartão — usado
    tanto para recalcular o total da fatura quanto para exibir a lista de
    itens que a compõem (ex.: expandir a fatura no dashboard)."""
    from app.models import STATUS_PAGO, Lancamento, LancamentoRateio

    itens = []  # cada item: {"lancamento": Lancamento, "valor": Decimal}

    diretas = Lancamento.query.filter(
        Lancamento.cartao_id == cartao.id,
        Lancamento.status == STATUS_PAGO,
        Lancamento.data_pagamento.isnot(None),
    ).all()
    for l in diretas:
        if competencia_fatura_cartao(cartao, l.data_pagamento) == competencia:
            itens.append({"lancamento": l, "valor": Decimal(l.valor_pago or 0)})

    rateios = (
        LancamentoRateio.query.join(
            Lancamento, LancamentoRateio.lancamento_id == Lancamento.id
        )
        .filter(
            LancamentoRateio.cartao_id == cartao.id,
            Lancamento.status == STATUS_PAGO,
            Lancamento.data_pagamento.isnot(None),
        )
        .all()
    )
    for r in rateios:
        if (
            competencia_fatura_cartao(cartao, r.lancamento.data_pagamento)
            == competencia
        ):
            itens.append({"lancamento": r.lancamento, "valor": Decimal(r.valor or 0)})

    itens.sort(key=lambda i: i["lancamento"].data_pagamento)
    return itens


def recalcular_fatura_cartao(db, cartao, competencia):
    """Soma todas as compras vinculadas a este cartão que caem na fatura da
    competência informada, e cria/atualiza o lançamento do próprio cartão
    para refletir esse total. Não sobrescreve uma fatura que já foi paga
    (dar baixa nela é uma ação separada)."""
    from app.models import STATUS_PAGO, STATUS_PENDENTE, Lancamento

    itens = itens_fatura_cartao(cartao, competencia)
    total = sum((i["valor"] for i in itens), Decimal(0))

    fatura = Lancamento.query.filter_by(
        conta_id=cartao.id, competencia=competencia
    ).first()
    if not fatura:
        ano, mes = competencia_para_data(competencia)
        fatura = Lancamento(
            conta_id=cartao.id,
            competencia=competencia,
            vencimento=montar_data(ano, mes, cartao.dia_vencimento),
            valor=total,
            status=STATUS_PENDENTE,
            forma_pagamento=cartao.forma_pagamento_padrao,
        )
        db.session.add(fatura)
    elif fatura.status != STATUS_PAGO:
        fatura.valor = total

    return fatura, total, itens


# ---------------------------------------------------------------------------
# Geração automática de lançamentos futuros (recorrentes / provisionados /
# parcelados / faturas de cartão) para manter sempre o mês atual + horizonte
# de meses seguintes com lançamento cadastrado.
# ---------------------------------------------------------------------------


def gerar_lancamentos_futuros(db, horizonte_meses=3):
    from app.models import (
        STATUS_PENDENTE,
        STATUS_PROVISIONADO,
        TIPO_LANCAMENTO_PARCELADO,
        TIPO_LANCAMENTO_RECORRENTE,
        TIPO_LANCAMENTO_UNICO,
        Conta,
        Lancamento,
    )

    hoje = date.today()
    criados = 0

    contas = Conta.query.filter_by(ativa=True).all()
    for conta in contas:
        if conta.eh_cartao:
            # A fatura de cada mês é sempre recalculada a partir das compras
            # vinculadas a este cartão — não usa valor_base nem provisionar.
            for i in range(horizonte_meses + 1):
                ano, mes = somar_meses(hoje.year, hoje.month, i)
                comp = competencia_str(ano, mes)
                recalcular_fatura_cartao(db, conta, comp)
            continue

        # Resolve a forma de pagamento padrão da conta uma vez (pode ser um
        # texto simples antigo ou apontar para um cartão/receita cadastrado).
        forma_label, forma_cartao_id, forma_receita_id = (
            resolver_forma_pagamento_padrao(conta.forma_pagamento_padrao)
        )

        if conta.tipo_lancamento == TIPO_LANCAMENTO_RECORRENTE:
            competencias_existentes = {l.competencia for l in conta.lancamentos}
            for i in range(horizonte_meses + 1):
                ano, mes = somar_meses(hoje.year, hoje.month, i)
                comp = competencia_str(ano, mes)
                if comp in competencias_existentes:
                    continue
                if conta.provisionar:
                    valor = calcular_media_provisionamento(conta)
                    status = STATUS_PROVISIONADO
                else:
                    valor = Decimal(conta.valor_base or 0)
                    status = STATUS_PENDENTE
                lanc = Lancamento(
                    conta_id=conta.id,
                    competencia=comp,
                    vencimento=montar_data(ano, mes, conta.dia_vencimento),
                    valor=valor,
                    valor_provisionado=valor if conta.provisionar else None,
                    status=status,
                    forma_pagamento=forma_label,
                    cartao_id=forma_cartao_id,
                    pago_com_receita_id=forma_receita_id,
                )
                db.session.add(lanc)
                criados += 1

        elif conta.tipo_lancamento == TIPO_LANCAMENTO_PARCELADO and not conta.quitada:
            if not conta.num_parcelas:
                continue
            existentes = sorted((l.parcela_num or 0) for l in conta.lancamentos)
            proxima_parcela = (max(existentes) + 1) if existentes else 1
            if proxima_parcela > conta.num_parcelas:
                continue
            # Uma conta parcelada tem um número FIXO e conhecido de parcelas
            # (ex.: 6x de um empréstimo) — diferente das recorrentes, aqui
            # geramos TODAS as parcelas que faltam de uma vez, independente
            # do horizonte de meses do dashboard. Isso é essencial para que
            # a quitação antecipada (que divide o valor pelas parcelas em
            # aberto) sempre veja o total correto de parcelas do contrato.
            if conta.lancamentos:
                ultima = max(conta.lancamentos, key=lambda l: l.vencimento)
                ano, mes = ultima.vencimento.year, ultima.vencimento.month
            else:
                ano, mes = hoje.year, hoje.month

            while proxima_parcela <= conta.num_parcelas:
                if conta.lancamentos or proxima_parcela > 1:
                    ano, mes = somar_meses(ano, mes, 1)
                lanc = Lancamento(
                    conta_id=conta.id,
                    competencia=competencia_str(ano, mes),
                    vencimento=montar_data(ano, mes, conta.dia_vencimento),
                    valor=Decimal(conta.valor_base or 0),
                    parcela_num=proxima_parcela,
                    status=STATUS_PENDENTE,
                    forma_pagamento=forma_label,
                    cartao_id=forma_cartao_id,
                    pago_com_receita_id=forma_receita_id,
                )
                db.session.add(lanc)
                criados += 1
                proxima_parcela += 1

        elif conta.tipo_lancamento == TIPO_LANCAMENTO_UNICO:
            # Um lançamento único só precisa existir uma vez — se ainda não
            # tem nenhum, cria no mês atual (ou usa o mês/dia informado por
            # quem cadastrou a conta, se já tiver sido criado com pagamento).
            if not conta.lancamentos:
                lanc = Lancamento(
                    conta_id=conta.id,
                    competencia=competencia_str(hoje.year, hoje.month),
                    vencimento=montar_data(hoje.year, hoje.month, conta.dia_vencimento),
                    valor=Decimal(conta.valor_base or 0),
                    status=STATUS_PENDENTE,
                    forma_pagamento=forma_label,
                    cartao_id=forma_cartao_id,
                    pago_com_receita_id=forma_receita_id,
                )
                db.session.add(lanc)
                criados += 1

    db.session.commit()
    return criados


# ---------------------------------------------------------------------------
# Aplicar o valor atual da conta aos lançamentos ainda não pagos — usado
# depois de corrigir um valor errado cadastrado na conta (ex.: valor da
# parcela de um financiamento). Lançamentos já pagos nunca são alterados.
# ---------------------------------------------------------------------------


def atualizar_lancamentos_em_aberto(conta, atualizar_dia_vencimento=False):
    from app.models import STATUS_PAGO, STATUS_PROVISIONADO

    abertos = [l for l in conta.lancamentos if l.status != STATUS_PAGO]
    if not abertos:
        return 0

    if conta.provisionar:
        novo_valor = calcular_media_provisionamento(conta)
    else:
        novo_valor = Decimal(conta.valor_base or 0)

    for l in abertos:
        l.valor = novo_valor
        if conta.provisionar:
            l.valor_provisionado = novo_valor
            l.status = STATUS_PROVISIONADO
        if atualizar_dia_vencimento:
            l.vencimento = montar_data(
                l.vencimento.year, l.vencimento.month, conta.dia_vencimento
            )

    return len(abertos)


# ---------------------------------------------------------------------------
# Opções de forma de pagamento no momento de dar baixa num lançamento:
# opções genéricas + cada cartão de crédito cadastrado + cada receita ativa.
# O valor de cada opção é codificado como "tipo:id_ou_texto" para o backend
# conseguir separar cartão/receita/genérico ao salvar.
# ---------------------------------------------------------------------------


def opcoes_forma_pagamento():
    from app.models import FORMAS_PAGAMENTO_GENERICAS, Conta, Receita

    opcoes = {
        "genericas": [
            {"value": f"generico:{f}", "label": f} for f in FORMAS_PAGAMENTO_GENERICAS
        ],
        "cartoes": [
            {"value": f"cartao:{c.id}", "label": c.nome}
            for c in Conta.query.filter_by(eh_cartao=True, ativa=True)
            .order_by(Conta.nome)
            .all()
        ],
        "receitas": [
            {"value": f"receita:{r.id}", "label": f"{r.tipo} - {r.origem}"}
            for r in Receita.query.filter_by(ativo=True).order_by(Receita.tipo).all()
        ],
    }
    return opcoes


def decompor_forma_pagamento(valor_bruto):
    """'cartao:3' -> (tipo='cartao', id=3); 'generico:Pix' -> (tipo='generico', valor='Pix')."""
    if not valor_bruto or ":" not in valor_bruto:
        return "generico", valor_bruto or ""
    tipo, _, resto = valor_bruto.partition(":")
    return tipo, resto


def somar_meses_data(data_base, n):
    """Desloca uma data em n meses, mantendo o mesmo dia (com ajuste para
    meses mais curtos, ex.: dia 31 de jan + 1 mês -> fim de fevereiro)."""
    ano, mes = somar_meses(data_base.year, data_base.month, n)
    return montar_data(ano, mes, data_base.day)


def criar_lancamento_inicial(db, conta, data_criacao):
    """Cria o primeiro lançamento de uma conta recém-criada ancorado numa
    data específica em vez de hoje — para lançar retroativamente algo que
    já aconteceu (ex.: uma compra do mês passado que foi esquecida). Os
    lançamentos seguintes (parcelas futuras, meses seguintes de uma
    recorrente) continuam normalmente a partir daí via
    gerar_lancamentos_futuros."""
    from app.models import STATUS_PENDENTE, TIPO_LANCAMENTO_PARCELADO, Lancamento

    if conta.lancamentos:
        return None

    forma_label, forma_cartao_id, forma_receita_id = resolver_forma_pagamento_padrao(
        conta.forma_pagamento_padrao
    )

    ano, mes = data_criacao.year, data_criacao.month
    lanc = Lancamento(
        conta_id=conta.id,
        competencia=competencia_str(ano, mes),
        vencimento=montar_data(ano, mes, conta.dia_vencimento),
        valor=Decimal(conta.valor_base or 0),
        parcela_num=1 if conta.tipo_lancamento == TIPO_LANCAMENTO_PARCELADO else None,
        status=STATUS_PENDENTE,
        forma_pagamento=forma_label,
        cartao_id=forma_cartao_id,
        pago_com_receita_id=forma_receita_id,
    )
    db.session.add(lanc)
    db.session.commit()
    return lanc


def dividir_valor_total_em_parcelas(valor_total, n):
    """Divide um valor total em n parcelas cujo somatório bate exatamente
    com o total — a última parcela absorve a diferença de arredondamento,
    do jeito que compras parceladas de verdade costumam funcionar (ex.:
    R$74,98 em 5x vira 4x de R$15,00 + 1x de R$14,98, não 5x de R$74,98)."""
    if n <= 0:
        return []
    valor_total = Decimal(valor_total)
    parcela_padrao = (valor_total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    parcelas = [parcela_padrao] * (n - 1)
    ultima = (valor_total - parcela_padrao * (n - 1)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    parcelas.append(ultima)
    return parcelas


def resolver_forma_pagamento_padrao(valor_bruto):
    """Decodifica a 'forma de pagamento padrão' de uma conta — que pode ser
    um texto simples antigo (ex.: 'Pix') ou um valor codificado escolhido
    num cartão/receita (ex.: 'cartao:3') — e retorna
    (rótulo_para_exibir, cartao_id, receita_id) para aplicar a um novo
    lançamento gerado automaticamente."""
    from app.models import Conta, Receita

    tipo, valor = decompor_forma_pagamento(valor_bruto)
    if tipo == "cartao" and valor:
        cartao = Conta.query.get(int(valor))
        label = f"Cartão de crédito: {cartao.nome}" if cartao else "Cartão de crédito"
        return label, (cartao.id if cartao else None), None
    if tipo == "receita" and valor:
        receita = Receita.query.get(int(valor))
        label = f"Receita: {receita.tipo} - {receita.origem}" if receita else "Receita"
        return label, None, (receita.id if receita else None)
    return valor, None, None


def marcar_conta_recem_criada_como_paga(
    db,
    conta,
    forma_pagamento_raw,
    data_pagamento,
    valor_pago_texto,
    valor_e_total_parcelado=False,
):
    """Usado ao cadastrar uma conta já indicando que ela foi paga (ex.: uma
    compra feita na loja com o cartão de crédito).

    Se for uma conta PARCELADA e `valor_e_total_parcelado` estiver marcado,
    o valor de referência (e o valor pago, se informado) são tratados como
    o TOTAL da compra e divididos entre as parcelas — não repetidos em
    cada uma.

    Se for uma conta PARCELADA paga com um cartão de crédito, marca TODAS
    as parcelas como pagas de uma vez — cada uma caindo na fatura de um mês
    seguinte (mantendo o mesmo dia da compra original), exatamente como uma
    compra parcelada de verdade no cartão. Nos demais casos (única,
    recorrente, ou parcelado pago com outra forma), marca só o primeiro
    lançamento."""
    from app.models import STATUS_PAGO, TIPO_LANCAMENTO_PARCELADO, Conta, Receita

    tipo_forma, valor_forma = decompor_forma_pagamento(forma_pagamento_raw)

    try:
        valor_pago_total = (
            Decimal(valor_pago_texto.replace(".", "").replace(",", "."))
            if valor_pago_texto
            else None
        )
    except InvalidOperation:
        valor_pago_total = None

    cartao = None
    receita = None
    forma_label = valor_forma
    if tipo_forma == "cartao" and valor_forma:
        cartao = Conta.query.get(int(valor_forma))
        forma_label = (
            f"Cartão de crédito: {cartao.nome}" if cartao else "Cartão de crédito"
        )
    elif tipo_forma == "receita" and valor_forma:
        receita = Receita.query.get(int(valor_forma))
        forma_label = (
            f"Receita: {receita.tipo} - {receita.origem}" if receita else "Receita"
        )

    lancamentos = sorted(
        conta.lancamentos, key=lambda l: (l.parcela_num or 0, l.vencimento)
    )
    if not lancamentos:
        return

    # Se o valor informado na conta é o TOTAL da compra parcelada, divide
    # entre as N parcelas (ajustando o nominal `valor` de todas elas, pagas
    # ou não) em vez de repetir o mesmo valor em cada uma.
    valores_pagos_divididos = None
    if conta.tipo_lancamento == TIPO_LANCAMENTO_PARCELADO and valor_e_total_parcelado:
        n = len(lancamentos)
        valores_nominais = dividir_valor_total_em_parcelas(conta.valor_base, n)
        for lanc, v_nominal in zip(lancamentos, valores_nominais, strict=False):
            lanc.valor = v_nominal
        valores_pagos_divididos = (
            dividir_valor_total_em_parcelas(valor_pago_total, n)
            if valor_pago_total is not None
            else valores_nominais
        )

    pontos_recalcular = set()

    if conta.tipo_lancamento == TIPO_LANCAMENTO_PARCELADO and cartao:
        for idx, lanc in enumerate(lancamentos):
            data_parcela = somar_meses_data(data_pagamento, idx)
            comp = competencia_fatura_cartao(cartao, data_parcela)
            lanc.status = STATUS_PAGO
            if valores_pagos_divididos is not None:
                lanc.valor_pago = valores_pagos_divididos[idx]
            else:
                lanc.valor_pago = (
                    valor_pago_total if valor_pago_total is not None else lanc.valor
                )
            lanc.data_pagamento = data_parcela
            lanc.vencimento = data_parcela
            lanc.competencia = comp
            lanc.forma_pagamento = forma_label
            lanc.cartao_id = cartao.id
            lanc.pago_com_receita_id = None
            pontos_recalcular.add((cartao.id, comp))
    else:
        lanc = lancamentos[0]
        lanc.status = STATUS_PAGO
        if valores_pagos_divididos is not None:
            lanc.valor_pago = valores_pagos_divididos[0]
        else:
            lanc.valor_pago = (
                valor_pago_total if valor_pago_total is not None else lanc.valor
            )
        lanc.data_pagamento = data_pagamento
        lanc.forma_pagamento = forma_label
        if cartao:
            lanc.cartao_id = cartao.id
            lanc.pago_com_receita_id = None
            pontos_recalcular.add(
                (cartao.id, competencia_fatura_cartao(cartao, data_pagamento))
            )
        elif receita:
            lanc.pago_com_receita_id = receita.id
            lanc.cartao_id = None

    db.session.commit()

    for cartao_id, competencia in pontos_recalcular:
        c = Conta.query.get(cartao_id)
        if c:
            recalcular_fatura_cartao(db, c, competencia)
    db.session.commit()


# ---------------------------------------------------------------------------
# Projeção de investimentos (juros compostos mensais simples)
# ---------------------------------------------------------------------------


def projetar_valor_investimento(investimento, na_data=None):
    na_data = na_data or date.today()

    if (
        investimento.valor_atual_manual is not None
        and investimento.data_atualizacao_manual
    ):
        base_valor = Decimal(investimento.valor_atual_manual)
        base_data = investimento.data_atualizacao_manual
    else:
        base_valor = Decimal(investimento.valor_inicial)
        base_data = investimento.data_aplicacao

    if not investimento.taxa_mensal_pct:
        return base_valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    dias = (na_data - base_data).days
    if dias <= 0:
        return base_valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    meses = Decimal(dias) / Decimal(30)
    taxa = Decimal(investimento.taxa_mensal_pct) / Decimal(100)
    fator = (1 + taxa) ** meses
    valor = base_valor * fator
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
