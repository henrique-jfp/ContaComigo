import unittest
from decimal import Decimal

from finance_utils import is_expense_type, is_income_type, normalize_financial_type
from pierre_finance.categorizador import classificar_nomes_por_regras, limpar_descricao, normalizar_tipo
from pierre_finance.sync import _inferir_tipo, _is_self_transfer


class TestFinanceRules(unittest.TestCase):
    def test_normalize_financial_type_unifies_legacy_labels(self):
        self.assertEqual(normalize_financial_type("Entrada"), "Receita")
        self.assertEqual(normalize_financial_type("Receita"), "Receita")
        self.assertEqual(normalize_financial_type("Saída"), "Despesa")
        self.assertEqual(normalize_financial_type("Despesa"), "Despesa")
        self.assertTrue(is_income_type("credit"))
        self.assertTrue(is_expense_type("debit"))

    def test_sync_prefers_transaction_type_when_available(self):
        self.assertEqual(
            _inferir_tipo("Compra em restaurante", Decimal("59.90"), "BANK", "DEBIT"),
            "Despesa"
        )
        self.assertEqual(
            _inferir_tipo("Pagamento salário empresa", Decimal("3000"), "BANK", "CREDIT"),
            "Receita"
        )

    def test_inferir_tipo_sinais_fortes(self):
        self.assertEqual(_inferir_tipo("Pix enviado para João", Decimal("100"), "BANK"), "Despesa")
        self.assertEqual(_inferir_tipo("Pix recebido de Maria", Decimal("200"), "BANK"), "Receita")
        self.assertEqual(_inferir_tipo("Pagamento fatura Nubank", Decimal("500"), "BANK"), "Despesa")

    def test_classificar_nomes_por_regras_identifica_comum(self):
        cat_ifood, sub_ifood = classificar_nomes_por_regras("PIX ENVIADO IFOOD", "Despesa")
        self.assertEqual(cat_ifood, "Alimentação")
        self.assertIn(sub_ifood, ["Delivery", "Restaurante/Delivery", "Supermercado", "Geral"])

        cat_netflix, sub_netflix = classificar_nomes_por_regras("NETFLIX.COM", "Despesa")
        self.assertIn(cat_netflix, ["Serviços e Assinaturas", "Lazer"])
        self.assertEqual(sub_netflix, "Streaming")

    def test_limpeza_descricao_remove_prefixos(self):
        limpa = limpar_descricao("PIX ENVIADO MERCADO LIVRE *12345 01/05")
        self.assertIn("mercado livre", limpa)
        self.assertNotIn("pix enviado", limpa)


if __name__ == "__main__":
    unittest.main()
