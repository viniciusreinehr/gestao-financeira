from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    STATUS_PAGO,
    Conta,
    Lancamento,
    LancamentoRateio,
    Receita,
    ReceitaRecebimento,
)
from app.utils import (
    competencia_str,
    format_competencia,
    itens_fatura_cartao,
    somar_meses,
)


def obter_gastos_por_receita_em_lote(competencia: str) -> dict[int, Decimal]:
    """Calcula os gastos associados a cada receita em uma competência de forma
    otimizada (2 queries agrupadas), eliminando o problema de N+1 queries."""
    gastos: dict[int, Decimal] = {}

    diretos = (
        db.session.query(
            Lancamento.pago_com_receita_id, func.sum(Lancamento.valor_pago)
        )
        .filter(
            Lancamento.competencia == competencia,
            Lancamento.status == STATUS_PAGO,
            Lancamento.pago_com_receita_id.isnot(None),
        )
        .group_by(Lancamento.pago_com_receita_id)
        .all()
    )
    for receita_id, total in diretos:
        if receita_id:
            gastos[receita_id] = gastos.get(receita_id, Decimal(0)) + Decimal(
                total or 0
            )

    rateios = (
        db.session.query(LancamentoRateio.receita_id, func.sum(LancamentoRateio.valor))
        .join(Lancamento, LancamentoRateio.lancamento_id == Lancamento.id)
        .filter(
            Lancamento.competencia == competencia,
            Lancamento.status == STATUS_PAGO,
            LancamentoRateio.receita_id.isnot(None),
        )
        .group_by(LancamentoRateio.receita_id)
        .all()
    )
    for receita_id, total in rateios:
        if receita_id:
            gastos[receita_id] = gastos.get(receita_id, Decimal(0)) + Decimal(
                total or 0
            )

    return gastos


def obter_resumo_mes(ano: int, mes: int) -> dict[str, Any]:
    """Gera o resumo consolidado de despesas e lançamentos do mês,
    utilizando joinedload para carregar contas e categorias em uma única query."""
    comp = competencia_str(ano, mes)

    lancs_todos = (
        Lancamento.query.options(
            joinedload(Lancamento.conta).joinedload(Conta.categoria),
            joinedload(Lancamento.conta).joinedload(Conta.local_obj),
        )
        .join(Conta, Lancamento.conta_id == Conta.id)
        .filter(Lancamento.competencia == comp, Conta.ativa)
        .all()
    )

    lancs = [l for l in lancs_todos if not l.pago_totalmente_com_cartao]

    abertos = sorted(
        (l for l in lancs if l.status != STATUS_PAGO), key=lambda l: l.vencimento
    )
    pagos = sorted(
        (l for l in lancs if l.status == STATUS_PAGO),
        key=lambda l: l.data_pagamento or l.vencimento,
        reverse=True,
    )
    lancamentos_ordenados = abertos + pagos

    for l in lancamentos_ordenados:
        if l.conta.eh_cartao:
            l.itens_fatura = itens_fatura_cartao(l.conta, l.competencia)

    total = sum((l.valor_contabilizavel_no_mes for l in lancs), Decimal(0))
    pago = sum(
        (l.valor_contabilizavel_no_mes for l in lancs if l.status == STATUS_PAGO),
        Decimal(0),
    )
    pendente = total - pago

    return {
        "ano": ano,
        "mes": mes,
        "competencia": comp,
        "label": format_competencia(comp),
        "lancamentos": lancamentos_ordenados,
        "total": total,
        "pago": pago,
        "pendente": pendente,
    }


def obter_receitas_previstas(
    ano: int, mes: int
) -> tuple[list[dict[str, Any]], Decimal]:
    """Retorna as receitas previstas para a competência com saldos e gastos pré-calculados."""
    comp = competencia_str(ano, mes)
    receitas = Receita.query.filter_by(ativo=True).all()
    recebimentos = {
        rr.receita_id: rr
        for rr in ReceitaRecebimento.query.filter_by(
            competencia=comp, recebido=True
        ).all()
    }

    gastos_map = obter_gastos_por_receita_em_lote(comp)

    itens = []
    total = Decimal(0)
    for r in receitas:
        dt = r.data_prevista(ano, mes)
        if dt is None:
            continue

        recebimento = recebimentos.get(r.id)
        confirmado = recebimento is not None
        valor_exibicao = (
            Decimal(recebimento.valor_recebido) if confirmado else Decimal(r.valor or 0)
        )
        valor_previsto = Decimal(r.valor or 0)
        gasto = gastos_map.get(r.id, Decimal(0))
        diferenca_previsto = valor_exibicao - valor_previsto

        itens.append(
            {
                "receita": r,
                "data": dt,
                "confirmado": confirmado,
                "recebimento": recebimento,
                "valor_previsto": valor_previsto,
                "valor_exibicao": valor_exibicao,
                "diferenca_previsto": diferenca_previsto,
                "gasto": gasto,
                "saldo": valor_exibicao - gasto,
            }
        )
        total += valor_exibicao

    itens.sort(key=lambda i: i["data"])
    return itens, total


def calcular_custo_por_categoria(
    lancamentos: list[Lancamento], total_mes: Decimal
) -> list[dict[str, Any]]:
    """Calcula o percentual e custo agrupado por categoria no mês,
    evitando operações matemáticas no Jinja2."""
    custo_map: dict[int, dict[str, Any]] = {}
    for l in lancamentos:
        cat = l.conta.categoria
        if cat.id not in custo_map:
            custo_map[cat.id] = {
                "id": cat.id,
                "nome": cat.nome,
                "cor": cat.cor,
                "icone": cat.icone,
                "valor": Decimal(0),
                "pct": 0.0,
            }
        custo_map[cat.id]["valor"] += l.valor_contabilizavel_no_mes

    lista = sorted(custo_map.values(), key=lambda c: c["valor"], reverse=True)
    if total_mes > 0:
        for item in lista:
            item["pct"] = float((item["valor"] / total_mes) * 100)

    return lista


def obter_dados_completos_dashboard(horizonte_meses: int) -> dict[str, Any]:
    """Orquestra a montagem completa de todos os dados do dashboard."""
    hoje = date.today()
    meses = []
    for i in range(horizonte_meses + 1):
        ano, mes = somar_meses(hoje.year, hoje.month, i)
        resumo = obter_resumo_mes(ano, mes)
        receitas_itens, receitas_total = obter_receitas_previstas(ano, mes)
        resumo["receitas"] = receitas_itens
        resumo["receitas_total"] = receitas_total
        resumo["saldo_previsto"] = receitas_total - resumo["total"]
        meses.append(resumo)

    mes_atual = meses[0]
    proximos_vencimentos = [
        l for l in mes_atual["lancamentos"] if l.status != STATUS_PAGO
    ]
    proximos_vencimentos.sort(key=lambda l: l.vencimento)
    atrasados = [l for l in proximos_vencimentos if l.atrasado]

    custo_categoria = calcular_custo_por_categoria(
        mes_atual["lancamentos"], mes_atual["total"]
    )

    return {
        "hoje": hoje,
        "meses": meses,
        "mes_atual": mes_atual,
        "proximos_vencimentos": proximos_vencimentos,
        "atrasados": atrasados,
        "custo_categoria": custo_categoria,
    }
