from __future__ import annotations


INCOME_TYPES = {"entrada", "receita", "credit", "credito", "crédito"}
EXPENSE_TYPES = {"saida", "saída", "despesa", "debit", "debito", "débito"}


def normalize_financial_type(raw_value: str | None, default: str = "Despesa") -> str:
    raw = str(raw_value or "").strip().lower()
    if raw in INCOME_TYPES:
        return "Receita"
    if raw in EXPENSE_TYPES:
        return "Despesa"
    return default


def is_income_type(raw_value: str | None) -> bool:
    return normalize_financial_type(raw_value, default="Despesa") == "Receita"


def is_expense_type(raw_value: str | None) -> bool:
    return normalize_financial_type(raw_value, default="Receita") == "Despesa"
