# Schema do Banco de Dados — Gestão Financeira

> **Responsável:** 🗄️ DBA (SQLite + Flask-SQLAlchemy 3.1)  
> **Última revisão:** 2026-09-10  
> **Banco:** SQLite — `instance/financeiro.db`

---

## 1. Diagrama de Entidades e Relacionamentos

```
categoria (1) ----< (N) conta
local     (1) ----< (N) conta
local     (1) ----< (N) receita

conta (1) ----< (N) lancamento          [conta_id]
conta (1) ----< (N) lancamento          [cartao_id]  <- cartão que pagou
conta (1) ----< (N) lancamento_rateio   [cartao_id]
conta (1) ----< (N) quitacao

receita (1) ----< (N) lancamento        [pago_com_receita_id]
receita (1) ----< (N) lancamento_rateio [receita_id]
receita (1) ----< (N) receita_recebimento

lancamento (1) ----< (N) lancamento_rateio
```

---

## 2. Tabelas

### 2.1 `categoria`

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-incremento |
| `nome` | VARCHAR(80) | NOT NULL, UNIQUE | Ex.: "Luz", "Mercado" |
| `cor` | VARCHAR(20) | default `#6c757d` | Cor hex para exibição visual |
| `icone` | VARCHAR(40) | default `bi-tag` | Classe Bootstrap Icons |

**Seed padrão:** 15 categorias pré-carregadas (Luz, Água, Internet, Telefonia, Locação, Cartão de Crédito, Financiamento, Empréstimo, Consórcio, Imposto, Seguro, Combustível, Mercado, Investimento, Outros).

---

### 2.2 `local`

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-incremento |
| `nome` | VARCHAR(60) | NOT NULL, UNIQUE | Ex.: "Casa", "Vinicius", "Gislaine" |
| `cor` | VARCHAR(20) | default `#6c757d` | Cor hex para exibição visual |

**Seed padrão:** Casa, Vinicius, Gislaine.

---

### 2.3 `conta`

Representa um **plano de despesa** (recorrente, parcelado ou único).

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `nome` | VARCHAR(120) | NOT NULL | Ex.: "Conta de Luz CPFL" |
| `categoria_id` | INTEGER | FK → categoria.id, NOT NULL | |
| `local` | VARCHAR(40) | | Campo legado (mantido por compatibilidade) |
| `local_id` | INTEGER | FK → local.id | Responsável/local (novo) |
| `tipo_lancamento` | VARCHAR(20) | NOT NULL | `recorrente` / `parcelado` / `unico` |
| `provisionar` | BOOLEAN | default 0 | Valor variável (luz, água) — usa média histórica |
| `dia_vencimento` | INTEGER | default 10 | Dia do mês (1–31) |
| `valor_base` | NUMERIC(12,2) | default 0 | Valor fixo ou ponto de partida do provisionamento |
| `num_parcelas` | INTEGER | | Total de parcelas (apenas tipo `parcelado`) |
| `forma_pagamento_padrao` | VARCHAR(40) | default "Manual / Boleto" | Forma padrão codificada (`generico:Pix`, `cartao:3`) |
| `ativa` | BOOLEAN | default 1 | |
| `quitada` | BOOLEAN | default 0 | Financiamento/empréstimo quitado antecipadamente |
| `observacao` | TEXT | | |
| `eh_cartao` | BOOLEAN | default 0 | Esta conta É um cartão de crédito |
| `dia_fechamento` | INTEGER | | Dia de fechamento da fatura (apenas se `eh_cartao=1`) |
| `criado_em` | DATETIME | default utcnow | |

> ⚠️ **Gap (DBA):** Índice em `(categoria_id, local_id, ativa)` não definido. Listagem de contas com filtro composto executa full-scan.

---

### 2.4 `lancamento`

Ocorrência mensal (parcela, recorrência ou lançamento único) de uma `conta`.

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `conta_id` | INTEGER | FK → conta.id, NOT NULL | Conta-mãe |
| `competencia` | VARCHAR(7) | NOT NULL | Formato `YYYY-MM` (ex.: `2026-09`) |
| `vencimento` | DATE | NOT NULL | Data de vencimento |
| `valor` | NUMERIC(12,2) | NOT NULL, default 0 | Valor previsto/contratado |
| `valor_provisionado` | NUMERIC(12,2) | | Média estimada salva no momento da provisão |
| `valor_pago` | NUMERIC(12,2) | | Valor real pago (preenchido ao baixar) |
| `data_pagamento` | DATE | | |
| `forma_pagamento` | VARCHAR(40) | | Label da forma usada |
| `cartao_id` | INTEGER | FK → conta.id | Cartão de crédito que pagou esta conta |
| `pago_com_receita_id` | INTEGER | FK → receita.id | Receita utilizada para pagar |
| `parcela_num` | INTEGER | | Número da parcela (apenas tipo `parcelado`) |
| `status` | VARCHAR(20) | NOT NULL, default `pendente` | `pendente` / `provisionado` / `pago` |
| `observacao` | TEXT | | |

**Índices recomendados (pendentes de implementação):**

```python
# diretriz 02-dba.md
Index("idx_lancamento_competencia_status", Lancamento.competencia, Lancamento.status)
Index("idx_lancamento_conta_competencia", Lancamento.conta_id, Lancamento.competencia)
Index("idx_lancamento_cartao", Lancamento.cartao_id)
Index("idx_lancamento_receita", Lancamento.pago_com_receita_id)
```

> ⚠️ **Gap crítico (DBA):** Nenhum índice composto definido. A query do Dashboard (`competencia == X AND ativa == True`) executa full-scan nas tabelas `lancamento` e `conta` a cada requisição.

---

### 2.5 `lancamento_rateio`

Parte de um pagamento dividido entre múltiplas fontes.

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `lancamento_id` | INTEGER | FK → lancamento.id, NOT NULL | |
| `tipo` | VARCHAR(20) | NOT NULL | `generico` / `cartao` / `receita` |
| `valor` | NUMERIC(12,2) | NOT NULL | Valor desta parte do rateio |
| `cartao_id` | INTEGER | FK → conta.id | Se `tipo=cartao` |
| `receita_id` | INTEGER | FK → receita.id | Se `tipo=receita` |
| `descricao_generica` | VARCHAR(40) | | Se `tipo=generico` (ex.: "Pix") |

---

### 2.6 `receita`

Origem de renda recorrente (salário, comissão) ou única (resgate, venda).

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `tipo` | VARCHAR(60) | NOT NULL | Ex.: "Salário", "Comissão", "Bônus" |
| `origem` | VARCHAR(120) | NOT NULL | Ex.: "Empresa X", "Olist" |
| `responsavel` | VARCHAR(40) | | Campo legado (mantido por compatibilidade) |
| `responsavel_id` | INTEGER | FK → local.id | Responsável (novo) |
| `valor` | NUMERIC(12,2) | NOT NULL, default 0 | Valor previsto |
| `recorrencia` | VARCHAR(20) | NOT NULL, default `recorrente` | `recorrente` / `unica` |
| `regra_data` | VARCHAR(20) | default `dia_fixo` | `dia_fixo` / `dia_util` |
| `dia_fixo` | INTEGER | | Dia do mês (se `regra_data=dia_fixo`) |
| `n_dia_util` | INTEGER | | Enésimo dia útil (se `regra_data=dia_util`) |
| `data_unica` | DATE | | Data exata (se `recorrencia=unica`) |
| `ativo` | BOOLEAN | default 1 | |
| `observacao` | TEXT | | |

---

### 2.7 `receita_recebimento`

Confirmação/baixa de uma receita em um mês específico.

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `receita_id` | INTEGER | FK → receita.id, NOT NULL | |
| `competencia` | VARCHAR(7) | NOT NULL | Formato `YYYY-MM` |
| `valor_recebido` | NUMERIC(12,2) | | Valor real recebido |
| `data_recebimento` | DATE | | |
| `recebido` | BOOLEAN | default 0 | |

---

### 2.8 `investimento`

Aplicação financeira com projeção de rendimento composto.

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `nome` | VARCHAR(120) | NOT NULL | Ex.: "CDB Banco Inter" |
| `banco` | VARCHAR(80) | | |
| `tipo` | VARCHAR(40) | default `CDB` | CDB, Tesouro Direto, Poupança, Ações… |
| `valor_inicial` | NUMERIC(14,2) | NOT NULL, default 0 | Aporte inicial |
| `data_aplicacao` | DATE | NOT NULL | |
| `taxa_mensal_pct` | NUMERIC(6,4) | | Taxa mensal composta (ex.: `0.9000` = 0,9% a.m.) |
| `valor_atual_manual` | NUMERIC(14,2) | | Valor atualizado manualmente |
| `data_atualizacao_manual` | DATE | | Data da última atualização manual |
| `vencimento` | DATE | | |
| `liquidez_diaria` | BOOLEAN | default 1 | |
| `ativo` | BOOLEAN | default 1 | |
| `observacao` | TEXT | | |

> ⚠️ **Gap (Arquiteto):** A projeção de rendimento em `utils.projetar_valor_investimento()` usa `(1 + taxa) ** meses` onde `meses = dias / 30`. A divisão `Decimal / Decimal` com expoente `Decimal` pode resultar em perda de precisão pois `**` com `Decimal` não é totalmente determinístico para expoentes fracionários. Deve ser validado e eventualmente convertido para `math.exp` ou projeção mês-a-mês.

---

### 2.9 `quitacao`

Registro de quitação antecipada de financiamento/empréstimo.

| Coluna | Tipo | Restrição | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `conta_id` | INTEGER | FK → conta.id, NOT NULL | |
| `data_quitacao` | DATE | NOT NULL | |
| `valor_quitacao` | NUMERIC(14,2) | NOT NULL | Valor total pago para quitar |
| `parcelas_restantes` | INTEGER | | Parcelas que foram baixadas |
| `observacao` | TEXT | | |
| `criado_em` | DATETIME | default utcnow | |

---

## 3. Estratégia de Migração

A migração é feita via função `_migrar_schema()` em `app/__init__.py`, usando `SQLAlchemy inspect` + `ALTER TABLE` direto.

**Histórico de migrações realizadas:**

| Coluna adicionada | Tabela | Motivo |
|---|---|---|
| `recorrencia` | `receita` | Suporte a receitas únicas vs. recorrentes |
| `data_unica` | `receita` | Data de receitas únicas |
| `responsavel_id` | `receita` | FK para tabela `local` (migração do campo texto) |
| `eh_cartao` | `conta` | Marcar conta como cartão de crédito |
| `dia_fechamento` | `conta` | Dia de fechamento da fatura do cartão |
| `local_id` | `conta` | FK para tabela `local` (migração do campo texto) |
| `cartao_id` | `lancamento` | Cartão que pagou o lançamento |
| `pago_com_receita_id` | `lancamento` | Receita usada para pagar o lançamento |

---

## 4. Configuração SQLite Recomendada (Pendente)

```python
# app/extensions.py — A SER IMPLEMENTADO
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")  # leituras concorrentes sem bloqueio
    cursor.execute("PRAGMA foreign_keys=ON;")  # integridade referencial
    cursor.execute("PRAGMA synchronous=NORMAL;")  # performance balanceada com WAL
    cursor.close()
```

---

## 5. Campos Monetários — Regra Crítica

Todos os campos de valor devem usar `db.Numeric(precision, scale, asdecimal=True)` para garantir retorno como `Decimal` e não como `float`:

```python
# CORRETO (a ser adotado)
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column

valor: Mapped[Decimal] = mapped_column(
    db.Numeric(precision=12, scale=2, asdecimal=True),
    nullable=False,
    default=Decimal("0"),
)

# INCORRETO (estado atual)
valor = db.Column(db.Numeric(12, 2), nullable=False, default=0)
```

> ⚠️ **Gap crítico:** Nenhum modelo atual usa `asdecimal=True` nem a API `Mapped[T]`. A ausência pode causar `float` silencioso retornado do banco, violando cálculos financeiros.
