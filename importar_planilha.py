"""
Importa o histórico de lançamentos da planilha Financeiro.xlsx (aba "Controle")
para o banco SQLite da aplicação, trazendo somente as contas da família
(Casa, Vinicius, Gislaine) e ignorando o que é da Loja.

Uso:
    python importar_planilha.py [caminho_para_Financeiro.xlsx]

Se nenhum caminho for informado, usa "Financeiro.xlsx" na raiz do projeto.
"""

import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import openpyxl

from app import create_app
from app.extensions import db
from app.models import (
    STATUS_PAGO,
    STATUS_PENDENTE,
    TIPO_LANCAMENTO_PARCELADO,
    TIPO_LANCAMENTO_RECORRENTE,
    TIPO_LANCAMENTO_UNICO,
    Categoria,
    Conta,
    Lancamento,
)

# ---------------------------------------------------------------------------
# Mapeamento curado: nome da conta na planilha -> configuração no novo sistema
# ---------------------------------------------------------------------------
# categoria       : nome da Categoria (deve existir no seed de categorias)
# tipo            : unico | recorrente | parcelado
# provisionar     : True para contas variáveis cujo valor deve ser estimado
#                    pela média dos últimos meses até a fatura chegar
CONTA_CONFIG = {
    "Ademicon": {
        "categoria": "Consórcio",
        "tipo": TIPO_LANCAMENTO_PARCELADO,
        "provisionar": False,
    },
    "Aluguel": {
        "categoria": "Locação",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": False,
    },
    "CC Cresol": {
        "categoria": "Cartão de Crédito",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": False,
    },
    "CC Itaú": {
        "categoria": "Cartão de Crédito",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": False,
    },
    "CC Nubank": {
        "categoria": "Cartão de Crédito",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": False,
    },
    "CC Santander": {
        "categoria": "Cartão de Crédito",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": False,
    },
    "Copel": {
        "categoria": "Luz",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": True,
    },
    "Empréstimo Consignado": {
        "categoria": "Empréstimo",
        "tipo": TIPO_LANCAMENTO_PARCELADO,
        "provisionar": False,
    },
    "Empréstimo Cresol": {
        "categoria": "Empréstimo",
        "tipo": TIPO_LANCAMENTO_PARCELADO,
        "provisionar": False,
    },
    "Empréstimo Nubank": {
        "categoria": "Empréstimo",
        "tipo": TIPO_LANCAMENTO_PARCELADO,
        "provisionar": False,
    },
    "Financiamento Creditas": {
        "categoria": "Financiamento",
        "tipo": TIPO_LANCAMENTO_PARCELADO,
        "provisionar": False,
    },
    "Financiamento Santander": {
        "categoria": "Financiamento",
        "tipo": TIPO_LANCAMENTO_PARCELADO,
        "provisionar": False,
    },
    "Financiamento Tucson": {
        "categoria": "Financiamento",
        "tipo": TIPO_LANCAMENTO_PARCELADO,
        "provisionar": False,
    },
    "MEI": {
        "categoria": "Imposto",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": False,
    },
    "Meganet": {
        "categoria": "Internet",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": True,
    },
    "Posto Fox": {
        "categoria": "Combustível",
        "tipo": TIPO_LANCAMENTO_UNICO,
        "provisionar": False,
    },
    "Sanepar": {
        "categoria": "Água",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": True,
    },
    "Seguro Kwid": {
        "categoria": "Seguro",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": False,
    },
    "TIM": {
        "categoria": "Telefonia",
        "tipo": TIPO_LANCAMENTO_RECORRENTE,
        "provisionar": True,
    },
}

# Contas que, mesmo aparecendo sem "Local" preenchido, são claramente
# fornecedores/produtos da Loja (Tordilho Negro) e por isso NUNCA são
# importadas, conforme pedido do usuário.
EXCLUIR_SEMPRE = {
    "Black",
    "Black Erva",
    "Botinas",
    "C. F. Menezes & Carvalho Ltda - Qualitche",
    "Calçados para Dança - Vuollo",
    "Ciarin",
    "E R Confecções - Chapéu Gaucho",
    "Mazutti",
    "Montana",
    "NAY Carro de Som",
    "Pampasul",
    "Pura Raça",
    "Pé na Estrada",
    "Qualitchê",
    "Sokolowski",
    "Tênis Cruz Machado",
    "Élio Squena - Tordilho Negro",
    "Mercado D'amille",
    "Mercado Bom Preço",
    "Mercado São José",
    "MOR",
}

LOCAL_MAP = {
    "casa": "Casa",
    "vini": "Vinicius",
    "vinicius": "Vinicius",
    "gis": "Gislaine",
    "gislaine": "Gislaine",
    "itaú": "Outros",
    "itaú ": "Outros",
}


def normalizar_local(valor):
    if valor is None:
        return "Casa"  # lançamentos sem local preenchido: assume-se família/Casa
    chave = str(valor).strip().lower()
    return LOCAL_MAP.get(chave, valor.strip() if isinstance(valor, str) else "Casa")


def eh_loja(valor):
    return isinstance(valor, str) and valor.strip().lower() == "loja"


def parse_competencia(mes_valor, vencimento):
    if vencimento:
        return f"{vencimento.year:04d}-{vencimento.month:02d}"
    if isinstance(mes_valor, str) and "/" in mes_valor:
        m, a = mes_valor.split("/")
        return f"{int(a):04d}-{int(m):02d}"
    return None


def importar(caminho_planilha):
    wb = openpyxl.load_workbook(caminho_planilha, data_only=True)
    ws = wb["Controle"]

    categorias_cache = {c.nome: c for c in Categoria.query.all()}

    def get_categoria(nome):
        if nome not in categorias_cache:
            cat = Categoria(nome=nome)
            db.session.add(cat)
            db.session.flush()
            categorias_cache[nome] = cat
        return categorias_cache[nome]

    linhas_por_conta = defaultdict(list)

    ignoradas_loja = 0
    ignoradas_sem_config = set()

    for row in ws.iter_rows(min_row=2, values_only=True):
        nome_conta = row[0]
        local = row[1]
        vencimento = row[4]
        mes = row[5]
        valor = row[6]
        valor_pago = row[7]
        data_pagamento = row[8]

        if not nome_conta:
            continue
        if eh_loja(local):
            ignoradas_loja += 1
            continue
        if nome_conta in EXCLUIR_SEMPRE:
            ignoradas_loja += 1
            continue
        if nome_conta not in CONTA_CONFIG:
            ignoradas_sem_config.add(nome_conta)
            continue

        linhas_por_conta[nome_conta].append(
            {
                "local": normalizar_local(local),
                "vencimento": vencimento.date()
                if hasattr(vencimento, "date")
                else vencimento,
                "competencia": parse_competencia(mes, vencimento),
                "valor": valor,
                "valor_pago": valor_pago,
                "data_pagamento": data_pagamento.date()
                if hasattr(data_pagamento, "date")
                else data_pagamento,
            }
        )

    total_contas = 0
    total_lancamentos = 0

    for nome_conta, linhas in linhas_por_conta.items():
        cfg = CONTA_CONFIG[nome_conta]
        linhas.sort(key=lambda item: item["vencimento"] or item["competencia"] or "")

        local_predominante = defaultdict(int)
        for l in linhas:
            local_predominante[l["local"]] += 1
        local_final = max(local_predominante.items(), key=lambda kv: kv[1])[0]

        conta = Conta.query.filter_by(nome=nome_conta).first()
        if not conta:
            valores_validos = [Decimal(str(l["valor"])) for l in linhas if l["valor"]]
            valor_base = valores_validos[-1] if valores_validos else Decimal(0)
            conta = Conta(
                nome=nome_conta,
                categoria=get_categoria(cfg["categoria"]),
                local=local_final,
                tipo_lancamento=cfg["tipo"],
                provisionar=cfg["provisionar"],
                valor_base=valor_base,
                dia_vencimento=(
                    linhas[-1]["vencimento"].day if linhas[-1]["vencimento"] else 10
                ),
                num_parcelas=(
                    len(linhas) if cfg["tipo"] == TIPO_LANCAMENTO_PARCELADO else None
                ),
            )
            db.session.add(conta)
            db.session.flush()
            total_contas += 1

        parcela_num = 0
        for l in linhas:
            if not l["vencimento"] or not l["competencia"]:
                continue

            existe = Lancamento.query.filter_by(
                conta_id=conta.id, competencia=l["competencia"]
            ).first()
            if existe:
                continue

            parcela_num += 1
            try:
                valor = (
                    Decimal(str(l["valor"])) if l["valor"] is not None else Decimal(0)
                )
            except InvalidOperation:
                valor = Decimal(0)

            valor_pago = None
            status = STATUS_PENDENTE
            if l["valor_pago"]:
                try:
                    valor_pago = Decimal(str(l["valor_pago"]))
                    if valor_pago > 0:
                        status = STATUS_PAGO
                except InvalidOperation:
                    valor_pago = None

            lanc = Lancamento(
                conta_id=conta.id,
                competencia=l["competencia"],
                vencimento=l["vencimento"],
                valor=valor,
                valor_pago=valor_pago,
                data_pagamento=l["data_pagamento"] if status == STATUS_PAGO else None,
                parcela_num=(
                    parcela_num if cfg["tipo"] == TIPO_LANCAMENTO_PARCELADO else None
                ),
                status=status,
                forma_pagamento=conta.forma_pagamento_padrao,
            )
            db.session.add(lanc)
            total_lancamentos += 1

        if cfg["tipo"] == TIPO_LANCAMENTO_PARCELADO and not conta.num_parcelas:
            conta.num_parcelas = len(linhas)

    db.session.commit()

    print(f"Contas criadas/atualizadas: {total_contas}")
    print(f"Lançamentos importados: {total_lancamentos}")
    print(f"Linhas ignoradas por serem da Loja: {ignoradas_loja}")
    if ignoradas_sem_config:
        print(
            "\nContas encontradas na planilha SEM mapeamento definido (não importadas):"
        )
        for nome in sorted(ignoradas_sem_config):
            print(f"  - {nome}")
        print(
            "\nSe alguma dessas for uma conta da família que deveria ser importada,\n"
            "adicione-a ao dicionário CONTA_CONFIG em importar_planilha.py e rode de novo."
        )


if __name__ == "__main__":
    caminho = sys.argv[1] if len(sys.argv) > 1 else "Financeiro.xlsx"
    app = create_app()
    with app.app_context():
        importar(caminho)
        from app.utils import gerar_lancamentos_futuros

        criados = gerar_lancamentos_futuros(db, app.config.get("HORIZONTE_MESES", 5))
        print(f"\nLançamentos futuros gerados automaticamente: {criados}")
