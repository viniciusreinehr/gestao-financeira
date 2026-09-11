# Arquitetura do Sistema — Gestão Financeira Desktop

> **Responsável:** 🏛️ Arquiteto Python + 🔍 Reviewer  
> **Última revisão:** 2026-09-10  
> **Stack:** Python 3 · Flask 3.0 · Flask-SQLAlchemy 3.1 · SQLite · PyWebView 5.x · Waitress 3.0

---

## 1. Visão Geral

O sistema é uma **aplicação desktop offline** empacotada via PyInstaller. A interface é servida por um servidor Flask local (Waitress) e renderizada por uma janela nativa do sistema operacional via PyWebView (WebView2 no Windows).

```
+------------------------------------------+
|            PyWebView (WebView2)           |  <- Janela nativa do OS
|  http://127.0.0.1:5000  (localhost)      |
+------------------+-----------------------+
                   | HTTP
+------------------v-----------------------+
|         Waitress WSGI Server             |  <- Thread daemon
+------------------+-----------------------+
                   | WSGI
+------------------v-----------------------+
|           Flask Application              |
|  +----------+   +----------+            |
|  |  Routes  |   | Jinja2   |            |
|  |Blueprints|   | Templates|            |
|  +----+-----+   +----------+            |
|       |                                  |
|  +----v-----------------------------+    |
|  |      Utils / Services            |    |  <- Regras de negócio
|  +-----------------+----------------+    |
|                    |                     |
|  +-----------------v----------------+    |
|  |  Flask-SQLAlchemy (ORM)          |    |
|  |  SQLite -- instance/financeiro   |    |
|  +----------------------------------+    |
+------------------------------------------+
```

---

## 2. Estrutura de Camadas

### 2.1 Camada de Configuração (`config.py`)

Contém a classe `Config` com todas as variáveis de ambiente e parâmetros operacionais:

| Chave | Descrição |
|---|---|
| `SQLALCHEMY_DATABASE_URI` | Caminho para `instance/financeiro.db` |
| `HORIZONTE_MESES` | Quantos meses futuros gerar lançamentos (padrão: 5) |
| `MESES_MEDIA_PROVISIONAMENTO` | Janela histórica para calcular média de contas variáveis (padrão: 3) |
| `SECRET_KEY` | Chave para sessões Flask |

> ⚠️ **Gap identificado (Reviewer):** `SECRET_KEY` possui valor padrão fixo em código. Para ambientes compartilhados, deve ser lido de variável de ambiente.

---

### 2.2 Camada de Extensões (`app/extensions.py`)

Instância única de `SQLAlchemy` desacoplada da factory de aplicação — padrão correto para evitar importações circulares.

**Pendência crítica:** Os listeners de pragma SQLite devem ser registrados aqui:

```python
# PENDENTE DE IMPLEMENTAÇÃO — diretriz 07-security-integrity.md
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()
```

> ⚠️ **Gap crítico (DBA + Reviewer):** `PRAGMA foreign_keys=ON` e `PRAGMA journal_mode=WAL` **não estão ativados**. Integridade referencial não é aplicada pelo SQLite em tempo de execução.

---

### 2.3 Camada de Modelos (`app/models.py`)

Define os modelos SQLAlchemy. Ver `docs/database-schema.md` para detalhamento completo.

| Modelo | Responsabilidade |
|---|---|
| `Categoria` | Classificação das contas (Luz, Mercado, Cartão de Crédito…) |
| `Local` | Responsável/local (Casa, Vinicius, Gislaine) — cadastrável |
| `Conta` | Plano de despesa recorrente, parcelada ou única |
| `Lancamento` | Ocorrência mensal de uma `Conta` |
| `LancamentoRateio` | Parte de um pagamento dividido entre N origens |
| `Receita` | Entrada de dinheiro recorrente ou única |
| `ReceitaRecebimento` | Confirmação de recebimento de uma `Receita` em um mês |
| `Investimento` | Aplicação financeira com projeção de rendimento composto |
| `Quitacao` | Registro de quitação antecipada de financiamento |

> ⚠️ **Gap crítico (Reviewer):** Campos `Numeric` sem `asdecimal=True`. O valor retornado do banco pode ser `float` ou `str`, violando a regra de proibição de `float` em cálculos financeiros.

---

### 2.4 Camada de Rotas (`app/routes/`)

| Blueprint | Prefixo | Responsabilidade |
|---|---|---|
| `dashboard` | `/` | Visão consolidada mensal, baixa de lançamentos |
| `contas` | `/contas` | CRUD de contas, quitação antecipada |
| `receitas` | `/receitas` | CRUD de receitas e confirmação de recebimentos |
| `investimentos` | `/investimentos` | CRUD de investimentos e projeção |
| `categorias` | `/categorias` | CRUD de categorias |
| `locais` | `/locais` | CRUD de locais/responsáveis |

> ⚠️ **Gap alto (Reviewer — SOLID S):** `dashboard.atualizar_lancamento` e `contas.quitar` contêm lógica de negócio (rateio, quitação, recalculação de faturas) diretamente no controller. Devem ser extraídos para `app/services/`.

---

### 2.5 Camada de Serviços (`app/services/`)

Atualmente contém apenas `format.py`. A camada não está suficientemente estruturada — a maior parte das regras de negócio reside em `app/utils.py`.

| Funcionalidade | Estado Atual | Estado Desejado |
|---|---|---|
| Formatação de moeda/data | `utils.py` + `services/format.py` (duplicado) | Apenas `services/format.py` |
| Geração de lançamentos futuros | `utils.py` (função livre) | `services/lancamento_service.py` |
| Rateio de pagamentos | `dashboard.py` (controller) | `services/payment_splitter.py` |
| Cálculo de fatura de cartão | `utils.py` (função livre) | `services/cartao_service.py` |
| Projeção de investimentos | `utils.py` (função livre) | `services/investimento_service.py` |
| Provisionamento de contas | `utils.py` (função livre) | `services/provisionamento_service.py` |

---

### 2.6 Camada de Utilitários (`app/utils.py`)

Arquivo de **633 linhas** que centraliza: formatação, cálculos de data, provisionamento, lógica de cartão de crédito, geração de lançamentos, rateio e projeção de investimentos.

> ⚠️ **Gap alto (Reviewer — SOLID I):** `utils.py` é uma **"God Module"**. Deve ser decomposto em serviços especializados. Após a decomposição, `utils.py` deve conter apenas helpers de data/calendário puros.

---

## 3. Fluxo de Inicialização (`run.py`)

```
main()
  +-- Thread(daemon=True): _iniciar_servidor()  <- Waitress serve(app)
  +-- _aguardar_servidor()                      <- polling urllib (40x * 150ms)
  +-- webview.create_window() + webview.start() <- PyWebView (bloqueante)
       +-- Fallback: webbrowser.open()           <- se PyWebView indisponível
```

Erros fatais são gravados em `erro.log` e exibidos via `ctypes.windll.user32.MessageBoxW`.

---

## 4. Padrões Estabelecidos

### 4.1 Valores Monetários
- Uso correto de `decimal.Decimal` com `ROUND_HALF_UP` em `utils.py`
- ORM não garante `asdecimal=True` — retorno pode ser `float` (gap crítico)

### 4.2 Migração de Schema
Migração manual via `ALTER TABLE` em `_migrar_schema()`. Toda nova coluna de modelo deve ter `ALTER TABLE` correspondente nessa função.

### 4.3 Formatação Duplicada
`format_currency`, `format_date` e `format_competencia` existem em `utils.py` e em `services/format.py`. Os filtros Jinja2 em `__init__.py` devem delegar para `Format.*` e as funções livres em `utils.py` devem ser removidas (DRY).

---

## 5. Débitos Técnicos

| # | Severidade | Área | Descrição | Responsável |
|---|---|---|---|---|
| 1 | 🔴 Crítico | `extensions.py` | `PRAGMA foreign_keys=ON` e `journal_mode=WAL` ausentes | DBA |
| 2 | 🔴 Crítico | `models.py` | Campos `Numeric` sem `asdecimal=True` — risco de `float` | DBA + Arquiteto |
| 3 | 🟠 Alto | `dashboard.py` | Lógica de rateio e recalculação de fatura no controller | Arquiteto |
| 4 | 🟠 Alto | `contas.py` | Lógica de quitação antecipada no controller | Arquiteto |
| 5 | 🟠 Alto | `utils.py` | God Module — deve ser decomposto em serviços | Arquiteto |
| 6 | 🟡 Médio | `services/format.py` | Duplicação com `utils.py` | Arquiteto |
| 7 | 🟡 Médio | `models.py` | API legada `db.Column` em vez de `Mapped[T] = mapped_column(...)` | Arquiteto |
| 8 | 🟡 Médio | Geral | Ausência de type hints nas funções de `utils.py` e rotas | Reviewer |
| 9 | 🟡 Médio | `routes/` | N+1 queries em listagens sem `joinedload`/`selectinload` | DBA |
| 10 | 🟡 Médio | `models.py` | Índices compostos ausentes para queries do Dashboard | DBA |
| 11 | 🟢 Baixo | `config.py` | `SECRET_KEY` com valor padrão hardcoded | Reviewer |
| 12 | 🟢 Baixo | Geral | Ausência de suíte de testes (`tests/`) | Tester |

---

## 6. Arquitetura Desejada (Pós-Refatoração)

```
app/
+-- __init__.py                    <- Application factory
+-- extensions.py                  <- db + pragma listeners (WAL + FK)
+-- models.py                      <- Mapped[T] + asdecimal=True + índices
+-- routes/
|   +-- dashboard.py               <- parse request -> service -> render
|   +-- contas.py
|   +-- receitas.py
|   +-- investimentos.py
|   +-- categorias.py
|   +-- locais.py
+-- services/
|   +-- format.py                  <- FormatService (moeda, data, competência)
|   +-- lancamento_service.py      <- Geração de lançamentos futuros
|   +-- payment_splitter.py        <- PaymentSplitter (rateio Decimal preciso)
|   +-- cartao_service.py          <- Fatura (fechamento vs. vencimento)
|   +-- investimento_service.py    <- Projeção juros compostos
|   +-- provisionamento_service.py <- Média de provisionamento
+-- utils.py                       <- Apenas helpers data/calendário
```
