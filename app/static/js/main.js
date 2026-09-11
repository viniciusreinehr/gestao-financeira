// Máscara simples de moeda BRL (formata enquanto digita: 123456 -> 1.234,56)
function aplicarMascaraMoeda(input) {
    input.addEventListener("input", () => {
        let digitos = input.value.replace(/\D/g, "");
        if (!digitos) {
            input.value = "";
            return;
        }
        digitos = digitos.replace(/^0+(?=\d)/, "");
        while (digitos.length < 3) digitos = "0" + digitos;
        const centavos = digitos.slice(-2);
        let inteiro = digitos.slice(0, -2);
        inteiro = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        input.value = `${inteiro},${centavos}`;
    });
}

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input[data-money]").forEach(aplicarMascaraMoeda);
    const valorPagoInput = document.getElementById("inputValorPago");
    if (valorPagoInput) valorPagoInput.addEventListener("input", atualizarTotalRateado);
});

// Preenche e abre o modal de atualização/baixa de lançamento.
function abrirModalLancamento(btn) {
    const modalEl = document.getElementById("modalLancamento");
    if (!modalEl) return;

    const id = btn.dataset.id;
    const nome = btn.dataset.nome;
    const valor = btn.dataset.valor;
    const vencimento = btn.dataset.vencimento;
    const competencia = btn.dataset.competencia; // "YYYY-MM"
    const formaValor = btn.dataset.formaValor; // ex.: "generico:Pix", "cartao:3"
    const marcarPago = btn.dataset.marcarPago === "1";
    const jaPago = btn.dataset.jaPago === "1";
    const valorPagoReal = btn.dataset.valorPago; // valor_pago real, se já pago
    const dataPagamentoReal = btn.dataset.dataPagamento; // data_pagamento real (ISO), se já pago

    const form = document.getElementById("formLancamento");
    form.action = `/lancamentos/${id}/atualizar`;

    document.getElementById("modalLancamentoTitulo").textContent = nome;
    document.getElementById("inputValor").value = valor;
    document.getElementById("inputVencimento").value = vencimento;

    const selectForma = document.getElementById("inputFormaPagamento");
    if (formaValor && selectForma) {
        selectForma.value = formaValor;
        // se a opção não existir mais (ex.: cartão/receita removidos), evita ficar em branco
        if (selectForma.value !== formaValor && selectForma.options.length) {
            selectForma.selectedIndex = 0;
        }
    }

    const selectMes = document.getElementById("inputMesCompetencia");
    const selectAno = document.getElementById("inputAnoCompetencia");
    if (competencia && selectMes && selectAno) {
        const [ano, mes] = competencia.split("-");
        selectMes.value = String(parseInt(mes, 10));
        selectAno.value = ano;
    }

    const checkPago = document.getElementById("inputPago");
    const dataPagamento = document.getElementById("inputDataPagamento");
    const valorPago = document.getElementById("inputValorPago");

    // Se já está pago, mantém marcado (editar detalhes não deve reverter o
    // pagamento sem querer) e mostra o valor/data reais do pagamento. Se
    // ainda não está pago, usa o padrão sugerido (hoje / valor nominal).
    checkPago.checked = jaPago || marcarPago;
    dataPagamento.value = dataPagamentoReal || new Date().toISOString().slice(0, 10);
    valorPago.value = valorPagoReal || valor;
    document.getElementById("totalAPagarRateio").textContent = valorPago.value;

    // Pagamento dividido: se já existir um rateio salvo para este
    // lançamento, pré-preenche as linhas; senão, começa no modo simples.
    const linhasContainer = document.getElementById("linhasRateio");
    linhasContainer.innerHTML = "";
    let rateiosExistentes = [];
    try {
        rateiosExistentes = JSON.parse(btn.dataset.rateios || "[]");
    } catch (e) {
        rateiosExistentes = [];
    }
    document.getElementById("inputDividir").checked = rateiosExistentes.length > 0;
    rateiosExistentes.forEach((r) => adicionarLinhaRateio(r.forma, r.valor));
    toggleDividirPagamento();

    new bootstrap.Modal(modalEl).show();
}

// Alterna entre forma de pagamento única e pagamento dividido em várias formas.
function toggleDividirPagamento() {
    const marcado = document.getElementById("inputDividir").checked;
    document.getElementById("blocoDividir").style.display = marcado ? "" : "none";
    document.getElementById("inputFormaPagamentoWrapper").style.display = marcado ? "none" : "";
    if (marcado && document.getElementById("linhasRateio").children.length === 0) {
        adicionarLinhaRateio();
        adicionarLinhaRateio();
    }
    atualizarTotalRateado();
}

// Adiciona uma linha de rateio (forma + valor), clonando as opções do
// select principal de forma de pagamento para manter as mesmas escolhas.
function adicionarLinhaRateio(formaValor, valorTexto) {
    const template = document.getElementById("templateLinhaRateio");
    const clone = template.content.cloneNode(true);

    const select = clone.querySelector("select");
    select.innerHTML = document.getElementById("inputFormaPagamento").innerHTML;
    if (formaValor) select.value = formaValor;

    const input = clone.querySelector('input[name="rateio_valor[]"]');
    if (valorTexto) input.value = valorTexto;
    aplicarMascaraMoeda(input);
    input.addEventListener("input", atualizarTotalRateado);

    document.getElementById("linhasRateio").appendChild(clone);
    atualizarTotalRateado();
}

function removerLinhaRateio(botao) {
    botao.closest(".linha-rateio").remove();
    atualizarTotalRateado();
}

function _paraNumero(texto) {
    const limpo = (texto || "0").replace(/\./g, "").replace(",", ".");
    const n = parseFloat(limpo);
    return isNaN(n) ? 0 : n;
}

function _formatarMoeda(n) {
    return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function atualizarTotalRateado() {
    let total = 0;
    document.querySelectorAll('input[name="rateio_valor[]"]').forEach((inp) => {
        total += _paraNumero(inp.value);
    });
    const totalPago = _paraNumero(document.getElementById("inputValorPago").value);
    const spanTotal = document.getElementById("totalRateado");
    spanTotal.textContent = _formatarMoeda(total);
    spanTotal.className = Math.abs(total - totalPago) < 0.005 ? "text-success fw-semibold" : "text-danger fw-semibold";
    document.getElementById("totalAPagarRateio").textContent = document.getElementById("inputValorPago").value || "0,00";
}

// Preenche e abre o modal de confirmação de recebimento de receita.
function abrirModalReceita(btn) {
    const modalEl = document.getElementById("modalReceita");
    if (!modalEl) return;

    const id = btn.dataset.id;
    const nome = btn.dataset.nome;
    const competencia = btn.dataset.competencia;
    const previsto = btn.dataset.previsto;
    const valorAtual = btn.dataset.valorAtual;

    const form = document.getElementById("formReceita");
    form.action = `/receitas/${id}/confirmar`;

    document.getElementById("modalReceitaTitulo").textContent = `Confirmar recebimento — ${nome}`;
    document.getElementById("modalReceitaPrevisto").textContent = `Previsão cadastrada: R$ ${previsto}`;
    document.getElementById("inputReceitaCompetencia").value = competencia;
    document.getElementById("inputReceitaValor").value = valorAtual || previsto;
    document.getElementById("inputReceitaData").value = new Date().toISOString().slice(0, 10);

    new bootstrap.Modal(modalEl).show();
}
