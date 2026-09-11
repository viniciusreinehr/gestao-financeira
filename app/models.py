from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.extensions import db

# ---------------------------------------------------------------------------
# Choices / constantes
# ---------------------------------------------------------------------------

TIPO_LANCAMENTO_UNICO = "unico"
TIPO_LANCAMENTO_RECORRENTE = "recorrente"
TIPO_LANCAMENTO_PARCELADO = "parcelado"

TIPOS_LANCAMENTO = [
    (TIPO_LANCAMENTO_UNICO, "Único"),
    (TIPO_LANCAMENTO_RECORRENTE, "Recorrente"),
    (TIPO_LANCAMENTO_PARCELADO, "Parcelado"),
]

STATUS_PENDENTE = "pendente"
STATUS_PROVISIONADO = "provisionado"
STATUS_PAGO = "pago"

STATUS_LANCAMENTO = [
    (STATUS_PENDENTE, "Pendente"),
    (STATUS_PROVISIONADO, "Provisionado"),
    (STATUS_PAGO, "Pago"),
]

FORMAS_PAGAMENTO_GENERICAS = [
    "Manual / Boleto",
    "Débito em conta",
    "Débito em folha",
    "Pix",
    "Quitação antecipada",
]

# mantido por compatibilidade (usado como "forma de pagamento padrão" da conta,
# que é só um rótulo simples — não precisa das opções dinâmicas de cartão/receita)
FORMAS_PAGAMENTO = FORMAS_PAGAMENTO_GENERICAS

LOCAIS = ["Casa", "Vinicius", "Gislaine", "Outros"]

REGRAS_DATA_RECEITA = [
    ("dia_fixo", "Dia fixo do mês"),
    ("dia_util", "Enésimo dia útil do mês"),
]

RECORRENCIA_RECEITA_RECORRENTE = "recorrente"
RECORRENCIA_RECEITA_UNICA = "unica"

RECORRENCIAS_RECEITA = [
    (RECORRENCIA_RECEITA_RECORRENTE, "Recorrente (todo mês)"),
    (RECORRENCIA_RECEITA_UNICA, "Receita única"),
]


class BaseModel(db.Model):
    """Classe base abstrata para todos os modelos do SQLAlchemy.

    Define __init__(**kwargs) explicitamente para que analisadores estáticos
    (Pyright / Pylance / Mypy) reconheçam os argumentos nomeados das colunas
    e não recorram a object.__init__.
    """

    __abstract__ = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class Categoria(BaseModel):
    __tablename__ = "categoria"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    cor = db.Column(db.String(20), default="#6c757d")
    icone = db.Column(db.String(40), default="bi-tag")

    contas = db.relationship("Conta", back_populates="categoria")

    def __repr__(self):
        return f"<Categoria {self.nome}>"


class Local(BaseModel):
    """Quem é o responsável/local de uma conta ou receita — ex.: Casa,
    Vinicius, Gislaine. Cadastrável para poder ver o total gasto por
    pessoa/local e para não depender de uma lista fixa no código."""

    __tablename__ = "local"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(60), unique=True, nullable=False)
    cor = db.Column(db.String(20), default="#6c757d")

    contas = db.relationship("Conta", back_populates="local_obj")
    receitas = db.relationship("Receita", back_populates="responsavel_obj")

    def __repr__(self):
        return f"<Local {self.nome}>"


class Conta(BaseModel):
    """Representa um 'plano' de despesa: luz, água, MEI, um financiamento,
    um cartão de crédito, etc. Os lançamentos mensais (as parcelas /
    ocorrências) ficam em Lancamento."""

    __tablename__ = "conta"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=False)
    local = db.Column(db.String(40), default="Casa")  # mantido por compatibilidade
    local_id = db.Column(db.Integer, db.ForeignKey("local.id"))

    tipo_lancamento = db.Column(
        db.String(20), nullable=False, default=TIPO_LANCAMENTO_RECORRENTE
    )

    # Provisionamento: para contas variáveis (luz, água, internet, telefone)
    # cujo valor exato só se sabe quando a fatura chega.
    provisionar = db.Column(db.Boolean, default=False)

    # Dia de vencimento padrão (1-31) usado para gerar novos lançamentos.
    dia_vencimento = db.Column(db.Integer, default=10)

    # Valor de referência usado quando ainda não há histórico para provisionar
    # ou como valor padrão de contas recorrentes de valor fixo.
    valor_base = db.Column(db.Numeric(12, 2), default=0)

    # Para parcelado: total de parcelas contratadas.
    num_parcelas = db.Column(db.Integer)

    forma_pagamento_padrao = db.Column(db.String(40), default="Manual / Boleto")

    ativa = db.Column(db.Boolean, default=True)
    quitada = db.Column(db.Boolean, default=False)
    observacao = db.Column(db.Text)

    # Cartão de crédito: quando marcado, esta conta representa um cartão em
    # si (ex.: "Nubank", "Itaú"). Outras contas podem ser pagas usando este
    # cartão, e o valor delas entra automaticamente na fatura do mês certo,
    # calculado a partir do dia de fechamento.
    eh_cartao = db.Column(db.Boolean, default=False)
    dia_fechamento = db.Column(db.Integer)  # dia de fechamento da fatura (1-31)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    categoria = db.relationship("Categoria", back_populates="contas")
    local_obj = db.relationship("Local", back_populates="contas")
    lancamentos = db.relationship(
        "Lancamento",
        back_populates="conta",
        cascade="all, delete-orphan",
        order_by="Lancamento.vencimento",
        foreign_keys="Lancamento.conta_id",
    )
    quitacoes = db.relationship(
        "Quitacao", back_populates="conta", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Conta {self.nome}>"

    @property
    def parcelas_pagas(self):
        return sum(1 for l in self.lancamentos if l.status == STATUS_PAGO)

    @property
    def parcelas_abertas(self):
        if self.tipo_lancamento != TIPO_LANCAMENTO_PARCELADO:
            return None
        return [l for l in self.lancamentos if l.status != STATUS_PAGO]


class Lancamento(BaseModel):
    """Uma ocorrência mensal (ou parcela, ou lançamento único) de uma Conta."""

    __tablename__ = "lancamento"

    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False)

    competencia = db.Column(db.String(7), nullable=False)  # "YYYY-MM"
    vencimento = db.Column(db.Date, nullable=False)

    valor = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_provisionado = db.Column(
        db.Numeric(12, 2)
    )  # guarda o valor médio estimado original

    valor_pago = db.Column(db.Numeric(12, 2))
    data_pagamento = db.Column(db.Date)
    forma_pagamento = db.Column(db.String(40))

    # Se este lançamento foi pago com um cartão de crédito cadastrado, aponta
    # para a Conta desse cartão — usado para calcular o total da fatura.
    cartao_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=True)
    # Se foi pago usando o dinheiro de uma receita específica (ex.: a
    # comissão do mês), aponta para ela — usado para mostrar o saldo restante.
    pago_com_receita_id = db.Column(
        db.Integer, db.ForeignKey("receita.id"), nullable=True
    )

    parcela_num = db.Column(db.Integer)  # nº desta parcela (se parcelado)

    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDENTE)
    observacao = db.Column(db.Text)

    conta = db.relationship(
        "Conta", back_populates="lancamentos", foreign_keys=[conta_id]
    )
    cartao = db.relationship("Conta", foreign_keys=[cartao_id])
    pago_com_receita = db.relationship("Receita", foreign_keys=[pago_com_receita_id])
    rateios = db.relationship(
        "LancamentoRateio", back_populates="lancamento", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Lancamento {self.conta.nome if self.conta else '?'} {self.competencia}>"
        )

    @property
    def atrasado(self):
        return self.status != STATUS_PAGO and self.vencimento < date.today()

    @property
    def valor_exibicao(self):
        return (
            self.valor_pago
            if self.status == STATUS_PAGO and self.valor_pago is not None
            else self.valor
        )

    @property
    def pago_totalmente_com_cartao(self):
        """True quando este lançamento foi pago integralmente com um
        cartão de crédito — nesse caso, o valor já está contabilizado na
        fatura do cartão, e não deve ser somado de novo separadamente."""
        return self.status == STATUS_PAGO and bool(self.cartao_id)

    @property
    def absorvido_por_cartao(self):
        """True quando este lançamento está (ou vai estar, quando for
        pago) embutido na fatura de um cartão de crédito — independente
        de já estar pago ou ainda pendente. Uma conta recorrente cuja
        forma de pagamento padrão é um cartão, por exemplo, já nasce com
        cartao_id preenchido bem antes do vencimento, e a fatura do cartão
        já projeta esse valor (ver itens_fatura_cartao). Por isso ela deve
        sair da lista solta do planejamento desde já, não só depois de
        paga — do contrário fica invisível dentro da fatura projetada
        (que já conta com o valor dela) e visível de novo como linha solta
        (contando o valor uma segunda vez)."""
        return bool(self.cartao_id)

    @property
    def valor_contabilizavel_no_mes(self):
        """Valor que este lançamento deve contribuir para os totais do
        planejamento mensal. Lançamentos vinculados a um cartão (pagos ou
        ainda pendentes) contribuem 0 aqui — o valor já está (ou será)
        contabilizado via a fatura projetada do cartão. Num pagamento
        dividido que incluiu uma parte no cartão, só a parte que NÃO foi
        no cartão conta aqui — o resto já está na fatura."""
        if self.cartao_id:
            return Decimal(0)
        if self.status != STATUS_PAGO:
            return self.valor
        valor = Decimal(self.valor_pago if self.valor_pago is not None else self.valor)
        for r in self.rateios:
            if r.tipo == "cartao":
                valor -= Decimal(r.valor or 0)
        return valor

    @property
    def rateios_para_form(self):
        """Lista simples (dicts com valores em texto) usada para pré-preencher
        as linhas de rateio no modal de pagamento, quando reabrindo um
        lançamento que já foi pago dividido entre várias formas."""
        out = []
        for r in self.rateios:
            valor_str = f"{Decimal(r.valor):.2f}".replace(".", ",")
            out.append(
                {
                    "forma": r.forma_pagamento_valor,
                    "valor": valor_str,
                    "label": r.descricao,
                }
            )
        return out

    @property
    def forma_pagamento_valor(self):
        """Valor codificado usado para pré-selecionar a opção certa no
        select de forma de pagamento (ver opcoes_forma_pagamento em utils.py)."""
        if self.cartao_id:
            return f"cartao:{self.cartao_id}"
        if self.pago_com_receita_id:
            return f"receita:{self.pago_com_receita_id}"
        return f"generico:{self.forma_pagamento or ''}"

    @property
    def diferenca_pago_nominal(self):
        """Diferença entre o valor pago e o valor previsto/nominal."""
        if (
            self.status == STATUS_PAGO
            and self.valor_pago is not None
            and self.valor is not None
        ):
            diff = self.valor_pago - self.valor
            if diff != Decimal(0):
                return diff
        return None


class LancamentoRateio(BaseModel):
    """Uma 'parte' de um pagamento dividido entre múltiplas formas —
    ex.: R$500 do salário + R$160 de um cartão + R$80 de outra receita
    para pagar uma única conta."""

    __tablename__ = "lancamento_rateio"

    id = db.Column(db.Integer, primary_key=True)
    lancamento_id = db.Column(
        db.Integer, db.ForeignKey("lancamento.id"), nullable=False
    )

    tipo = db.Column(db.String(20), nullable=False)  # "generico" | "cartao" | "receita"
    valor = db.Column(db.Numeric(12, 2), nullable=False)

    cartao_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=True)
    receita_id = db.Column(db.Integer, db.ForeignKey("receita.id"), nullable=True)
    descricao_generica = db.Column(db.String(40), nullable=True)

    lancamento = db.relationship("Lancamento", back_populates="rateios")
    cartao = db.relationship("Conta", foreign_keys=[cartao_id])
    receita = db.relationship("Receita", foreign_keys=[receita_id])

    @property
    def forma_pagamento_valor(self):
        if self.tipo == "cartao":
            return f"cartao:{self.cartao_id}"
        if self.tipo == "receita":
            return f"receita:{self.receita_id}"
        return f"generico:{self.descricao_generica or ''}"

    @property
    def descricao(self):
        if self.tipo == "cartao" and self.cartao:
            return f"Cartão de crédito: {self.cartao.nome}"
        if self.tipo == "receita" and self.receita:
            return f"Receita: {self.receita.tipo} - {self.receita.origem}"
        return self.descricao_generica or "Outra forma"


class Receita(BaseModel):
    """Origem de receita: recorrente mensal (salário, comissão) ou única
    (ex.: resgate de aplicação, venda de um item)."""

    __tablename__ = "receita"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(60), nullable=False)  # Salário, Comissão, Bônus...
    origem = db.Column(db.String(120), nullable=False)  # Olist, Delfino Cotas...
    responsavel = db.Column(
        db.String(40), default="Casa"
    )  # mantido por compatibilidade
    responsavel_id = db.Column(db.Integer, db.ForeignKey("local.id"))
    valor = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    recorrencia = db.Column(
        db.String(20), nullable=False, default=RECORRENCIA_RECEITA_RECORRENTE
    )

    # usados quando recorrencia == "recorrente"
    regra_data = db.Column(db.String(20), default="dia_fixo")
    dia_fixo = db.Column(db.Integer)  # usado se regra_data == dia_fixo
    n_dia_util = db.Column(db.Integer)  # usado se regra_data == dia_util

    # usado quando recorrencia == "unica"
    data_unica = db.Column(db.Date)

    ativo = db.Column(db.Boolean, default=True)
    observacao = db.Column(db.Text)

    recebimentos = db.relationship(
        "ReceitaRecebimento", back_populates="receita", cascade="all, delete-orphan"
    )
    responsavel_obj = db.relationship("Local", back_populates="receitas")

    def data_prevista(self, ano, mes):
        return calcular_data_receita(self, ano, mes)


class ReceitaRecebimento(BaseModel):
    """Confirmação/baixa de uma receita em um mês específico (opcional)."""

    __tablename__ = "receita_recebimento"

    id = db.Column(db.Integer, primary_key=True)
    receita_id = db.Column(db.Integer, db.ForeignKey("receita.id"), nullable=False)
    competencia = db.Column(db.String(7), nullable=False)
    valor_recebido = db.Column(db.Numeric(12, 2))
    data_recebimento = db.Column(db.Date)
    recebido = db.Column(db.Boolean, default=False)

    receita = db.relationship("Receita", back_populates="recebimentos")


class Investimento(BaseModel):
    __tablename__ = "investimento"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    banco = db.Column(db.String(80))
    tipo = db.Column(
        db.String(40), default="CDB"
    )  # CDB, Tesouro Direto, Poupança, Ações...
    valor_inicial = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    data_aplicacao = db.Column(db.Date, nullable=False, default=date.today)

    # taxa mensal composta usada para projetar o valor atualizado
    # (ex.: 0.009 = 0,9% a.m. equivalente ao CDI). Opcional.
    taxa_mensal_pct = db.Column(db.Numeric(6, 4))

    # alternativa: usuário atualiza manualmente o valor de tempos em tempos
    valor_atual_manual = db.Column(db.Numeric(14, 2))
    data_atualizacao_manual = db.Column(db.Date)

    vencimento = db.Column(db.Date)
    liquidez_diaria = db.Column(db.Boolean, default=True)
    ativo = db.Column(db.Boolean, default=True)
    observacao = db.Column(db.Text)

    def valor_projetado(self, na_data=None):
        from app.utils import projetar_valor_investimento

        return projetar_valor_investimento(self, na_data)


class Quitacao(BaseModel):
    """Registro de quitação antecipada de um financiamento/empréstimo
    parcelado: as parcelas em aberto são recalculadas com base no valor
    total pago para encerrar a dívida."""

    __tablename__ = "quitacao"

    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False)
    data_quitacao = db.Column(db.Date, nullable=False, default=date.today)
    valor_quitacao = db.Column(db.Numeric(14, 2), nullable=False)
    parcelas_restantes = db.Column(db.Integer)
    observacao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    conta = db.relationship("Conta", back_populates="quitacoes")


# Import tardio para evitar ciclo (calcular_data_receita usa utils, que usa models)
from app.utils import calcular_data_receita  # noqa: E402