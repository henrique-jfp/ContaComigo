import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gerente_financeiro.services import _categorizar_com_mapa_inteligente
from gerente_financeiro.ia_handlers import _categorizar_lancamentos_sem_categoria_async
from pierre_finance.categorizador import classificar_nomes_por_regras


class _FakeDB:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.committed = False
        self.closed = False

    def query(self, _model):
        class _FakeQuery:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def limit(self, *args, **kwargs):
                return self

            def all(self):
                return list(self._rows)

            def first(self):
                return self._rows[0] if self._rows else None

        return _FakeQuery(self._rows)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class TestCategorizar(unittest.IsolatedAsyncioTestCase):
    def test_classificar_nomes_por_regras_basico(self):
        cat, sub = classificar_nomes_por_regras("Uber Viagem", "Saída")
        self.assertEqual(cat, "Transporte")

        cat_salario, _ = classificar_nomes_por_regras("Salário mensal da empresa", "Entrada")
        self.assertEqual(cat_salario, "Financeiro")

    async def test_categorizar_lancamentos_sem_categoria_async(self):
        lancs = [
            SimpleNamespace(id=1, descricao="uber casa", tipo="Saída", id_categoria=None, id_subcategoria=None),
            SimpleNamespace(id=2, descricao="padaria pao", tipo="Saída", id_categoria=None, id_subcategoria=None),
        ]
        db = _FakeDB(rows=lancs)

        def _mock_mapa(texto, tipo, _db):
            if "uber" in texto:
                return 1, 10
            if "padaria" in texto:
                return 2, 20
            return None, None

        with patch("gerente_financeiro.ia_handlers._categorizar_com_mapa_inteligente", side_effect=_mock_mapa):
            atualizados, total = await _categorizar_lancamentos_sem_categoria_async(db, usuario_id=100)

        self.assertEqual(total, 2)
        self.assertEqual(atualizados, 2)
        self.assertEqual(lancs[0].id_categoria, 1)
        self.assertEqual(lancs[1].id_categoria, 2)
        self.assertTrue(db.committed)


if __name__ == "__main__":
    unittest.main()
