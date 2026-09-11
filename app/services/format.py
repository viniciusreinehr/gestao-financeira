from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import ClassVar


class Format:
    MESES_ABREV: ClassVar[tuple[str, ...]] = (
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
    )
    MESES_NOME_COMPLETO: ClassVar[tuple[str, ...]] = (
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
    )

    @staticmethod
    def currency(value: Decimal | float | int | str | None) -> str:
        if value is None:
            value = 0
        dec_val = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        negativo = dec_val < 0
        dec_val = abs(dec_val)
        inteiro, centavos = f"{dec_val:.2f}".split(".")
        inteiro_formatado = f"{int(inteiro):,}".replace(",", ".")
        texto = f"R$ {inteiro_formatado},{centavos}"
        return f"-{texto}" if negativo else texto

    @staticmethod
    def date(value: date | datetime | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return value.strftime("%d/%m/%Y")

    @staticmethod
    def competencia(competencia: str | None) -> str:
        """'2026-09' -> 'Set/2026'"""
        if not competencia:
            return ""
        ano, mes = competencia.split("-")
        return f"{Format.MESES_ABREV[int(mes)]}/{ano}"
