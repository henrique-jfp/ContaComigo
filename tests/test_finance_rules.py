from decimal import Decimal

from finance_utils import is_expense_type, is_income_type, normalize_financial_type
from pierre_finance.categorizador import _deve_classificar_como_transferencia
from pierre_finance.sync import _inferir_tipo


def test_normalize_financial_type_unifies_legacy_labels():
    assert normalize_financial_type("Entrada") == "Receita"
    assert normalize_financial_type("Receita") == "Receita"
    assert normalize_financial_type("Saída") == "Despesa"
    assert normalize_financial_type("Despesa") == "Despesa"
    assert is_income_type("credit")
    assert is_expense_type("debit")


def test_sync_prefers_transaction_type_when_available():
    assert _inferir_tipo("Compra em restaurante", Decimal("59.90"), "BANK", "DEBIT") == "Despesa"
    assert _inferir_tipo("Pagamento salário empresa", Decimal("3000"), "BANK", "CREDIT") == "Receita"


def test_transfer_rule_does_not_override_identifiable_merchant():
    assert not _deve_classificar_como_transferencia("PIX ENVIADO IFOOD", "ifood")
    assert not _deve_classificar_como_transferencia("PIX ENVIADO NETFLIX", "netflix")


def test_transfer_rule_keeps_real_bank_transfer_patterns():
    assert _deve_classificar_como_transferencia("PIX ENVIADO NUBANK", "nubank")
    assert _deve_classificar_como_transferencia("TRANSFERENCIA ENVIADA MESMA TITULARIDADE", "mesma titularidade")
