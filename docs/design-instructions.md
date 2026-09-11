# Guia de Instruções de Design — Sistema de Gestão Financeira Familiar

## 1. Princípios de Interface (UX/UI Desktop)
- **Densidade de Informação Equilibrada:** Como a aplicação roda localmente em janela nativa via PyWebView, as tabelas de lançamentos e extratos devem apresentar espaçamento interno (padding) confortável, evitando poluição visual mas permitindo visualização de muitos registros sem rolagem excessiva.
- **Feedback Imediato:** Operações de baixa de títulos, rateios complexos e carregamento de dados devem exibir indicadores de carregamento (spinners) e notificações em toast para feedback de sucesso ou erro.
- **Componentização Obrigatória:** Elementos recorrentes (cards de saldo, badges de status, modais de confirmação) devem ser isolados em macros Jinja2 dentro de `app/templates/components/`.

## 2. Paleta de Cores e Tokens CSS
Definição de variáveis globais para consistência visual em todo o layout:

```css
:root {
  --color-primary: #1B365D;
  --color-primary-hover: #142847;
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-danger: #EF4444;
  --color-background: #F8FAFC;
  --color-surface: #FFFFFF;
  --color-text-main: #334155;
  --color-text-muted: #64748B;
  --color-border: #E2E8F0;
  --radius-base: 0.5rem;
  --shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.1);
}