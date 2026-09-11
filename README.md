# Gestão Financeira da Família

Aplicativo em **Flask + SQLite** para controle financeiro doméstico: contas a
pagar (com provisionamento automático de contas variáveis), receitas mensais,
investimentos e um dashboard com visão do mês atual e dos próximos dois
meses.

## 1. Instalação

Requer Python 3.10+.

```bash
cd gestao-financeira
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Rodar o aplicativo

```bash
python run.py
```

Isso abre uma **janela própria** do sistema (via pywebview), sem precisar
de navegador — veja a seção 7 para gerar isso como um executável
independente. Se o seu Linux não tiver as bibliotecas gráficas necessárias
(veja a seção 7), ele cai automaticamente para abrir no navegador em
**http://localhost:5000**. O banco e as categorias padrão são criados
automaticamente no primeiro uso.

### Modo desenvolvimento (para mexer no código)

Se você for alterar o código (templates, rotas, etc.) e quiser ver as
mudanças na hora, sem precisar reiniciar manualmente, use:

```bash
python dev.py
```

Isso sobe o servidor de debug do próprio Flask — recarrega sozinho a cada
alteração salva e mostra o stack trace detalhado no navegador se der erro.
Diferente do `run.py`, ele **não** abre janela nativa nem navegador
sozinho; acesse manualmente **http://127.0.0.1:5000**. Use `run.py` (ou o
executável) só para o uso do dia a dia depois que terminar de mexer.

## 4. Como o sistema está organizado

O layout é responsivo (Bootstrap 5) e funciona bem no celular — o menu vira
um menu de hambúrguer, os cartões empilham verticalmente, tabelas largas
ganham rolagem horizontal em vez de quebrar o layout, e as abas de mês do
dashboard rolam de lado em vez de empilhar em várias linhas numa tela
estreita. Os botões de ação nas tabelas também têm uma área de toque um
pouco maior em telas pequenas, para facilitar acertar o certo.

### Contas (menu "Controle / Contas")

Cada **Conta** cadastrada representa um "plano" de despesa recorrente (Copel,
MEI, Aluguel...) ou um contrato com fim definido (Ademicon, um financiamento,
um empréstimo). Toda Conta tem um **tipo de lançamento**:

- **Único** — acontece uma vez só (ex.: uma multa, um conserto).
- **Recorrente** — repete todo mês, indefinidamente, até você desativar a
  conta (ex.: MEI, aluguel, cartão de crédito).
- **Parcelado** — tem um número definido de parcelas e um fim (ex.: Ademicon,
  financiamentos, empréstimos). O sistema controla quantas parcelas já
  foram pagas e quantas faltam.

O sistema mantém automaticamente lançamentos gerados para o **mês atual +
os 5 meses seguintes (6 meses no total, um por aba no dashboard)** sempre
que você abre o dashboard ou a lista de
contas — não precisa gerar nada manualmente.

### Lançando algo retroativo (esqueceu de cadastrar antes)

Ao criar uma conta nova, o campo **"Data em que a conta foi feita"** deixa
em branco por padrão (assume hoje), mas você pode preencher com uma data
passada — útil para uma compra do mês passado que só lembrou de lançar
agora. O primeiro lançamento já nasce na competência certa (não no mês
atual), e o dia de vencimento da conta é sincronizado automaticamente com
o dia informado.

### Local / Responsável

Quem é o "local" ou responsável de uma conta (Casa, Vinicius, Gislaine...)
agora é cadastrável, no menu **"Locais"** — não é mais uma lista fixa. Lá
você cadastra novos, escolhe uma **cor** para facilitar identificar
visualmente (aparece como uma bolinha colorida do lado do nome em toda a
interface), e a listagem já mostra, para cada um, quantas contas ativas
estão vinculadas e o custo mensal total delas, com um botão **"Detalhar"**
que abre a lista completa de contas e receitas daquela pessoa/local.

Se você já usava o sistema antes dessa mudança, os valores de local que já
estavam em uso (Casa, Vinicius, Gislaine, Outros) são migrados automaticamente
para o cadastro novo na primeira vez que você abrir o sistema depois de
atualizar — nada se perde.

### Excluir uma conta

Na página de detalhe da conta (ou pelo ícone de lixeira na lista de
contas), o botão **"Excluir"** abre um modal de confirmação — a exclusão
remove a conta e **todos** os lançamentos dela (pagos e pendentes), e não
pode ser desfeita. Se a conta for um **cartão de crédito**, as compras que
foram pagas com ele continuam existindo normalmente, só deixam de estar
vinculadas a esse cartão.

A lista de contas também tem um filtro por **situação** (Ativa / Inativa /
Quitada), além dos filtros de categoria e local já existentes.

### Provisionamento (contas variáveis)

Marque a opção **"Provisionar automaticamente"** em contas cujo valor varia
todo mês e só se sabe quando a fatura chega (luz, água, internet, telefone).
O sistema:

1. Calcula a **média das últimas 3 faturas pagas** dessa conta.
2. Gera o lançamento do mês seguinte já com esse valor estimado, marcado
   como "Provisionado".
3. Quando a fatura real chegar, você abre a conta, clica em **"Atualizar"**
   no lançamento do mês e informa o valor real e o vencimento certo. Ao
   marcar como pago, esse valor real passa a entrar na média dos próximos
   provisionamentos.

O número de meses usados na média pode ser ajustado em `config.py`
(`MESES_MEDIA_PROVISIONAMENTO`).

### Forma de pagamento / débito automático

Todo lançamento tem um campo **Forma de pagamento**, com três grupos de
opções:

- **Geral**: Manual/Boleto, Débito em conta, Débito em folha, Pix, Quitação
  antecipada.
- **Cartões de crédito**: um item para cada cartão que você cadastrar (veja
  a seção seguinte) — escolher um deles é o que faz o valor entrar
  automaticamente na fatura certa.
- **Pago com o dinheiro de uma receita**: um item para cada receita ativa
  cadastrada — útil para saber quanto de uma receita específica (ex.: a
  comissão do mês) já foi usado e quanto ainda sobra.

Isso resolve o caso de contas que "já aparecem como pagas" por serem débito
automático — agora dá pra registrar explicitamente que aquele lançamento é
"Débito em conta" ou "Débito em folha", em vez de tratá-lo como um
pagamento manual qualquer.

### Cartão de crédito (contas pagas nele entram na fatura certa)

Para cadastrar um cartão, crie uma conta normal e marque a opção **"Esta
conta é um Cartão de Crédito"**. Em vez dos campos de contas comuns, você
informa:

- **Dia de fechamento** — a partir desse dia (inclusive), uma compra já
  entra na fatura do mês seguinte; antes desse dia, entra na fatura do mês
  corrente. Ex.: fecha dia 1 → uma compra feita no dia 1 já cai na fatura
  do mês seguinte, não na que está fechando naquele momento.
- **Dia de vencimento** — quando a fatura vence.

Depois de cadastrado, o cartão aparece como opção de **Forma de pagamento**
ao dar baixa em qualquer outra conta. Ao escolher "pagar com o cartão X",
o sistema:

1. Vincula aquele lançamento ao cartão, usando a **data de pagamento**
   informada para decidir em qual fatura ele cai (antes ou depois do
   fechamento).
2. Soma automaticamente o valor na fatura correspondente — que é, ela
   mesma, um lançamento normal da conta do cartão, e pode ser paga/dada
   baixa como qualquer outra conta quando a fatura de verdade chegar.
3. Recalcula tudo sozinho se você editar o valor, a data de pagamento, ou
   desfizer o pagamento de uma compra vinculada ao cartão.

Na página de detalhe do cartão, cada fatura mostra um link "N compra(s)"
que expande a lista de tudo que caiu ali (conta, valor e data), para
conferir a conta. Essa mesma expansão aparece também na tabela de
**Planejamento** do dashboard — a linha da fatura do cartão em cada mês
tem um "N item(ns) da fatura" que abre a listinha do que a compõe.

**Sem contar duas vezes:** uma conta paga integralmente com um cartão
**não aparece mais como linha separada** no Planejamento nem entra de novo
no total do mês — ela já está representada dentro da fatura do cartão (e
você vê o detalhe dela expandindo o "N item(ns) da fatura"). O mesmo vale
para o "Custo mensal total estimado" no topo da lista de Contas: uma conta
que é sempre paga com um cartão específico não soma separadamente ali, pra
não contar o mesmo gasto duas vezes.

Na lista de Contas, essas contas absorvidas por um cartão aparecem
**tabuladas logo abaixo dele**, com uma seta indicando o vínculo — assim
fica claro o que compõe a fatura daquele cartão só de olhar a lista.

### Lançar uma compra já paga com o cartão (à vista ou parcelada)

Ao cadastrar uma nova conta, tem a opção **"Já foi paga (lançar como paga
agora)"** — use para uma compra que você já fez, seja no cartão ou em
qualquer outra forma. Informe a forma de pagamento, a data e (se for
diferente do valor de referência) o valor realmente pago.

- **Conta única** paga com o cartão: uma compra à vista comum — o valor
  entra na fatura certa, calculada pela data da compra e o fechamento do
  cartão.
- **Conta parcelada** paga com o cartão: é tratada como uma **compra
  parcelada de verdade** — todas as parcelas já são marcadas como pagas de
  uma vez, cada uma caindo automaticamente na fatura de um mês seguinte
  (mantendo o mesmo dia da compra original). Você não precisa "dar baixa"
  mês a mês; isso já reflete como o cartão realmente cobra parcelamentos.
- **Conta recorrente** paga com o cartão: marca só a primeira ocorrência
  como paga; os meses seguintes continuam sendo gerados normalmente,
  aguardando confirmação quando cada cobrança realmente acontecer.
- Se a conta parcelada for paga com uma forma **que não seja cartão**
  (Pix, receita, etc.), só a primeira parcela é marcada como paga — para
  quitar todas de uma vez nesse caso, use o botão "Quitar antecipadamente"
  depois de criada.

**Valor total vs. valor de cada parcela:** quando a conta é **parcelada**,
aparece a opção **"O valor de referência (e o valor pago) acima é o total
da compra"** (marcada por padrão). Com ela marcada, o valor que você
digitou é o **total da compra** — o sistema divide entre as parcelas
automaticamente (a última parcela absorve os centavos de arredondamento,
do jeito que uma compra parcelada de verdade funciona: ex. R$74,98 em 5x
vira 4x de R$15,00 + 1x de R$14,98, não 5x de R$74,98). Desmarque só se o
valor que você digitou já é o valor de **cada** parcela individualmente.

Duas conveniências automáticas nesse formulário:
- Ao preencher a **data do pagamento**, o **dia de vencimento** da conta é
  atualizado sozinho para o mesmo dia (você pode ajustar depois se quiser).
- O campo **Forma de pagamento padrão** de qualquer conta (usado nos
  lançamentos gerados automaticamente) também lista os cartões cadastrados
  — escolher um deles já deixa os lançamentos futuros pré-vinculados a
  esse cartão.

### Pagamento dividido entre várias formas

Às vezes uma conta é paga usando mais de uma fonte de dinheiro — ex.:
R$500 do salário, R$160 de uma mensalidade e R$80 de uma comissão, tudo
para pagar uma única conta de R$740. No modal de pagamento, marque
**"Dividir esse pagamento entre mais de uma forma"** e adicione uma linha
para cada parte (forma + valor). Um contador mostra o total já dividido
comparado ao valor pago, para conferir se bate.

Cada parte é registrada separadamente: se uma das partes for um cartão de
crédito, só aquele valor entra na fatura (não a conta inteira); se for uma
receita, só aquele valor conta no gasto/saldo dela. Reabrir o pagamento
depois traz as linhas já preenchidas do jeito que foram salvas.

### Competência de um lançamento

No modal de "Atualizar"/"Pagar" de um lançamento, além do vencimento, dá
pra escolher explicitamente o **mês e ano de competência** (dois seletores
de lista, não texto livre). É a competência que decide em qual aba de mês
o lançamento aparece no dashboard — normalmente é o mesmo mês do
vencimento, mas às vezes você quer separar os dois (ex.: uma conta que
vence no início do mês mas você trata como competência do mês anterior).
Ao salvar, o sistema monta a string interna (`"2026-12"`) a partir do que
foi selecionado.

Ao editar um lançamento **já pago**, o valor e a data de pagamento reais
vêm pré-preenchidos (não a data de hoje) — e a caixa "marcar como pago"
já vem marcada, para editar os detalhes sem correr o risco de reverter o
pagamento sem querer.

### Corrigir o valor de um lançamento errado (e propagar a correção)

Descobriu que uma parcela estava cadastrada com o valor errado (ex.: uma
parcela de empréstimo estava como R$ 2.500,80, mas na verdade é
R$ 2.420,10)? Corrigir só o **valor de referência** da conta não muda os
lançamentos que já foram gerados — para isso, tem duas formas de propagar
a correção:

1. **Na hora de editar a conta**: marque a caixa "Corrigi o valor acima —
   aplicar também aos lançamentos ainda não pagos" antes de salvar.
2. **A qualquer momento depois**: na página de detalhe da conta, use o
   botão **"Atualizar lançamentos em aberto"**.

Nos dois casos, o sistema aplica o novo valor (ou, se a conta for
provisionada, recalcula a média) a **todos os lançamentos ainda não
pagos** dessa conta — os que já foram pagos nunca são alterados, para não
reescrever o histórico real. Há também a opção de ajustar o dia de
vencimento desses lançamentos junto, se o dia cadastrado na conta também
mudou.

### Quitação antecipada de financiamento

Na página de detalhe de uma Conta do tipo **Parcelado**, existe o botão
**"Quitar antecipadamente"**. Você informa o valor total pago na quitação e
a data; o sistema:

1. Pega todas as parcelas ainda em aberto dessa conta.
2. Divide o valor da quitação igualmente entre elas.
3. Marca todas como **pagas**, na data informada, com a forma de pagamento
   "Quitação antecipada" — dando baixa de uma vez em tudo que estava
   pendente, com o valor já atualizado.

Importante: uma conta parcelada sempre tem **todas** as suas parcelas
geradas de uma vez, assim que é criada (ex.: um empréstimo em 6x já nasce
com as 6 parcelas cadastradas, mesmo que algumas vençam daqui a vários
meses) — isso garante que a quitação sempre divida pelo número real de
parcelas em aberto, e não apenas pelas que "já tinham aparecido" no
dashboard.

### Receitas (entradas mensais e receitas únicas)

Cadastre cada origem de receita com **Tipo** (Salário, Comissão, Resgate de
aplicação, Venda de item...), **Origem** (empresa/cliente), **Responsável**
e **Valor**. No campo **Recorrência**, escolha:

- **Recorrente** — entra todo mês, com uma **regra de data**:
  - **Dia fixo do mês** (ex.: todo dia 1º).
  - **Enésimo dia útil do mês** (ex.: "5º dia útil", como no exemplo da
    comissão da Delfino Cotas).
- **Receita única** — entra uma vez só, numa **data específica** que você
  informa (ex.: resgate de uma aplicação, venda de um item, um bônus
  pontual). Ela só aparece no dashboard no mês exato dessa data — nos
  outros meses, some sozinha, sem precisar desativar manualmente.

O dashboard já calcula a data prevista de cada receita recorrente para o
mês atual e os próximos meses, encaixa as receitas únicas no mês certo, e
mostra o saldo previsto (receitas − despesas) de cada mês.

### Confirmar o valor real recebido (previsão vs. realizado)

Receitas variáveis (ex.: uma comissão que muda todo mês) são cadastradas
com um **valor de previsão**, mas o valor real de cada mês costuma ser
diferente. Na seção "Entradas" do dashboard (mês atual), cada receita tem
um botão **"Confirmar valor"**: você informa o valor que realmente entrou
naquele mês e a data.

A partir daí:

- A receita passa a aparecer com o badge **"Confirmado"** (em vez de
  "Previsto"), mostrando o valor real e a diferença em relação à previsão
  (ex.: previsão de R$ 400, confirmado R$ 800 → mostra "+R$ 400,00").
- O **total de receitas do mês e o saldo previsto** (receitas − despesas)
  passam a usar o valor real confirmado em vez da previsão — dando a visão
  real do mês que você pediu.
- Se confirmar por engano, tem um link **"desfazer"** que remove a
  confirmação e volta a mostrar a previsão original.

Isso não altera o valor de previsão cadastrado na receita (que continua
sendo usado nos meses seguintes) — cada mês guarda sua própria confirmação
independente.

Se uma receita foi usada como **forma de pagamento** de alguma conta (veja
a seção anterior), a listagem de "Entradas" também mostra, embaixo dela,
quanto já foi gasto com esse dinheiro naquele mês e o **saldo** restante
(previsão ou valor confirmado, menos o que já foi usado para pagar contas).

### Planejamento dos próximos meses (ordenação e diferenças de valor)

Na tabela de cada mês (abas "Planejamento" do dashboard, e também na
página de detalhe de cada conta), os lançamentos aparecem em duas partes:

1. **A pagar** — ordenados por vencimento, do mais próximo para o mais
   distante.
2. **Pagas** — ordenados por data de pagamento, da mais recente para a
   mais antiga.

Cada linha também mostra a **forma de pagamento** usada. E quando uma
conta paga teve juros ou desconto (o valor pago foi diferente do valor
original), aparece a diferença embaixo do valor — "pago a mais" em
vermelho quando pagou mais que o previsto, "pago a menos" em verde quando
pagou menos.

### Investimentos

Cadastre CDBs e afins informando banco, valor inicial aplicado e data. Se
você souber a **taxa mensal aproximada** (ex.: equivalente ao CDI), o
sistema projeta sozinho o valor atualizado por juros compostos. Se preferir,
pode simplesmente clicar em **"Atualizar valor"** de tempos em tempos e
digitar o saldo real que aparece no extrato do banco — o sistema passa a
projetar a partir dali.

### Categorias

Podem ser editadas/criadas livremente em "Categorias". Uma categoria só
pode ser excluída se não tiver nenhuma conta vinculada.

## 5. Máscaras de exibição

- Datas: `dd/mm/AAAA` em toda a interface.
- Valores: `R$ 123.456,78` (formatação brasileira, com filtro Jinja
  `| moeda` e `| data` usados em todos os templates).
- Os campos de valor em formulários (`data-money`) aplicam uma máscara de
  digitação automática em JavaScript (`app/static/js/main.js`).

## 6. Estrutura do projeto

```
gestao-financeira/
├── app/
│   ├── __init__.py          # application factory, seed de categorias
│   ├── extensions.py        # instância do SQLAlchemy
│   ├── models.py            # Categoria, Conta, Lancamento, Receita, Investimento, Quitacao
│   ├── utils.py              # formatação, provisionamento, geração de lançamentos, projeção
│   ├── routes/
│   │   ├── dashboard.py      # dashboard + baixa/atualização de lançamentos
│   │   ├── contas.py         # CRUD de contas + quitação
│   │   ├── receitas.py       # CRUD de receitas
│   │   ├── investimentos.py  # CRUD de investimentos
│   │   └── categorias.py     # CRUD de categorias
│   ├── templates/
│   └── static/
├── config.py
├── run.py
├── requirements.txt
└── instance/financeiro.db    # banco SQLite (criado automaticamente)
```

## 7. Gerar um executável — um programa de verdade, com janela própria

Dá para empacotar tudo em um único executável que abre como um **programa
desktop de verdade**, com sua própria janela — sem aba de navegador, sem
terminal aparecendo. Isso é feito com duas ferramentas:

- **PyInstaller** — empacota o Python e o Flask num único arquivo.
- **pywebview** — abre uma janela nativa do sistema operacional (usa o
  motor de navegador que já vem instalado no Windows/Mac/Linux) apontando
  para o servidor Flask, que roda escondido em segundo plano. Visualmente é
  indistinguível de um programa desktop comum.

### Gerar o executável

```bash
pip install -r requirements.txt
pip install -r requirements-build.txt
python build.py
```

Isso cria `dist/GestaoFinanceira` (Linux/Mac) ou `dist/GestaoFinanceira.exe`
(Windows — gere rodando esse mesmo comando dentro do Windows, já que o
PyInstaller empacota para o sistema operacional em que ele é executado).

Por padrão o executável abre **direto em uma janela própria**, sem console.
Se quiser ver os logs/erros na primeira execução (útil para depurar),
gere com `python build.py --console`.

### Dependências de sistema do pywebview (importante!)

O `pip install pywebview` sozinho é suficiente no **Windows** (ele usa o
WebView2, que já vem com o Windows 10/11 ou é instalado automaticamente
junto com o Edge) e costuma bastar no **Mac**. No **Linux**, é preciso
instalar também os pacotes do sistema operacional (não só via pip) para o
motor gráfico, por exemplo, no Ubuntu/Debian:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

Se o pywebview não conseguir carregar (falta alguma dessas dependências no
Linux, por exemplo), o programa **cai automaticamente para o modo
navegador** (abre a URL no navegador padrão e mantém uma janela de log
aberta) — ele nunca trava por causa disso.

### Uso do dia a dia

- Copie o arquivo `dist/GestaoFinanceira(.exe)` para onde quiser (ex.: Área
  de Trabalho, uma pasta "Financeiro" no seu PC).
- Ao rodar pela primeira vez, ele cria uma pasta `instance/` do lado dele
  com o banco `financeiro.db` — **mantenha o executável e essa pasta
  juntos** (não separe um do outro, senão o sistema não vai achar seus
  dados).
- A janela abre e fecha como qualquer programa: fechar a janela encerra o
  sistema (não fica nada rodando escondido).
- Se quiser um atalho na Área de Trabalho / barra de tarefas, é só criar um
  atalho normal do sistema operacional apontando para esse executável — no
  Windows dá pra até trocar o ícone do atalho (clique direito → Propriedades
  → Alterar ícone).

### Observações

- Ele roda com o servidor **waitress** por baixo dos panos (mais estável
  que o modo de desenvolvimento do Flask), então é seguro para uso do dia a
  dia.
- Se o Windows Defender/antivírus alertar na primeira execução (comum com
  executáveis gerados por PyInstaller, por não terem assinatura digital),
  basta permitir a execução — o programa é local e não acessa a internet.
- Para atualizar o executável depois de alguma mudança no código, rode
  `python build.py` de novo; seus dados em `instance/financeiro.db`
  continuam intactos, só o executável é substituído.

### "Rodei o executável e não aconteceu nada" (comum ao compartilhar com outra pessoa)

Como o executável final não tem janela de terminal, se algo falhar bem no
início ele pode simplesmente fechar sem mostrar nada visualmente. As causas
mais comuns, em ordem de probabilidade:

1. **WebView2 Runtime não instalado no Windows da pessoa.** É o motivo mais
   comum. O pywebview usa o WebView2 (o motor do Edge) para abrir a janela;
   a maioria dos Windows 10/11 atualizados já tem, mas versões mais antigas
   podem não ter. É gratuito e leve — baixe e instale em
   https://developer.microsoft.com/microsoft-edge/webview2/ (a opção
   "Evergreen Bootstrapper" resolve). Se estiver faltando, o próprio
   programa já detecta isso, registra no log e abre no navegador padrão
   como alternativa — então mesmo sem o WebView2 o app deveria abrir (só
   que no navegador em vez de janela própria).
2. **Windows Defender/SmartScreen bloqueou silenciosamente.** Isso é comum
   quando o `.exe` é baixado via WhatsApp, Telegram, e-mail, etc., já que
   não tem assinatura digital. Peça para a pessoa checar se apareceu algum
   aviso "Windows protegeu seu PC" (às vezes escondido atrás de outras
   janelas) e clicar em "Mais informações" → "Executar assim mesmo". Também
   vale checar a Central de Segurança do Windows → Proteção contra vírus →
   Histórico de proteção, para ver se o arquivo foi colocado em quarentena.
3. **Outro programa já está usando a porta 5000** (raro, mas acontece).
4. **Um processo anterior do próprio app ficou travado em segundo plano.**
   Peça para checar no Gerenciador de Tarefas se já não tem um
   `GestaoFinanceira.exe` rodando, e finalizar antes de abrir de novo.

**Para diagnosticar à distância:** o programa sempre grava um arquivo
`erro.log` na mesma pasta onde o executável está, mesmo quando não tem
janela de terminal — é só pedir para a pessoa abrir esse arquivo (com o
Bloco de Notas) e te mandar o conteúdo, ou anexar o arquivo. Ele mostra
exatamente o que aconteceu (porta ocupada, WebView2 ausente, etc.).

Se quiser ver os erros na hora, sem precisar olhar o `erro.log` depois, gere
uma versão de depuração com janela de terminal visível:

```bash
python build.py --console
```

## 8. Build automático para Windows, Mac e Linux (GitHub Actions)

Se você colocar este projeto num repositório do GitHub, já existe um
workflow pronto em `.github/workflows/build.yml` que gera os três
executáveis automaticamente — sem precisar ter Windows, Mac e Linux à mão.
Ele roda em máquinas do próprio GitHub (de graça, para repositórios
públicos) e builda em paralelo para os três sistemas usando o mesmo
`build.py` deste projeto.

**Quando ele roda:**
- Automaticamente a cada push na branch `main` ou em Pull Requests.
- Manualmente, a qualquer momento, pela aba **Actions** do repositório no
  GitHub → escolha o workflow "Build executáveis" → botão **"Run workflow"**.
- Ao criar uma tag de versão (ex.: `git tag v1.0.0 && git push --tags`) —
  nesse caso, além de gerar os três executáveis, ele **também publica uma
  Release no GitHub** com os três já anexados, prontos para qualquer
  pessoa baixar direto da aba "Releases" do repositório, sem precisar
  saber nada de Python ou compilar nada.

**Onde baixar o resultado:**
- Sem tag: aba **Actions** → clique na execução → seção "Artifacts" no
  final da página → baixe `GestaoFinanceira-Windows`, `GestaoFinanceira-macOS`
  ou `GestaoFinanceira-Linux`.
- Com tag (release): aba **Releases** do repositório.

O `.app` do Mac vem compactado em `.zip` (porque é uma pasta, não um
arquivo único) — é só descompactar e usar normalmente.

Você não precisa editar esse arquivo pra nada funcionar — ele já usa o
mesmo `build.py` e as mesmas dependências (`requirements.txt` e
`requirements-build.txt`) documentadas nas seções anteriores.

## 9. Próximos passos sugeridos (não implementados, mas fáceis de adicionar)

- Autenticação simples (login único da família) se for hospedar fora da
  rede local.
- Gráfico de evolução mensal de gastos por categoria (Chart.js já dá pra
  plugar direto nos dados que o dashboard já calcula).
- Exportar relatório mensal em PDF/Excel.
