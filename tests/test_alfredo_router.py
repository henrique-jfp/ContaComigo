import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gerente_financeiro import ia_handlers


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


class _FakeDB:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.committed = False
        self.closed = False

    def query(self, _model):
        return _FakeQuery(self._rows)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class _DummyMessage:
    def __init__(self, text):
        self.text = text
        self.voice = None
        self.html_replies = []
        self.text_replies = []

    async def reply_html(self, text, **kwargs):
        self.html_replies.append(text)
        return None

    async def reply_text(self, text, **kwargs):
        self.text_replies.append(text)
        return None


class _DummyUpdate:
    def __init__(self, text):
        self.message = _DummyMessage(text)
        self.effective_user = SimpleNamespace(id=123, full_name="Teste Usuario")


class _DummyContext:
    def __init__(self):
        self.user_data = {}


class TestAlfredoRouter(unittest.IsolatedAsyncioTestCase):
    def test_intencao_categorizar_sem_categoria(self):
        self.assertTrue(
            ia_handlers._intencao_categorizar_sem_categoria(
                "Categorize todos os lançamentos que estão sem categorias"
            )
        )

    def test_resumo_categoria_gastos_ignora_entradas(self):
        rows = [
            SimpleNamespace(tipo="Entrada", valor=1000, categoria=None),
            SimpleNamespace(tipo="Saída", valor=100, categoria=SimpleNamespace(nome="Alimentação")),
            SimpleNamespace(tipo="Saída", valor=50, categoria=None),
        ]
        top = ia_handlers._resumo_categoria_gastos_por_lancamentos(rows, limite=5)
        self.assertEqual(top[0][0], "Alimentação")
        self.assertAlmostEqual(top[0][1], 100.0)
        self.assertEqual(top[1][0], "Sem categoria")
        self.assertAlmostEqual(top[1][1], 50.0)

    def test_categorizar_lancamentos_sem_categoria_aplica_ids(self):
        lancs = [
            SimpleNamespace(id=1, descricao="uber casa", tipo="Saída", id_categoria=None, id_subcategoria=None),
            SimpleNamespace(id=2, descricao="", tipo="Saída", id_categoria=None, id_subcategoria=None),
            SimpleNamespace(id=3, descricao="salario", tipo="Entrada", id_categoria=None, id_subcategoria=None),
        ]
        db = _FakeDB(rows=lancs)

        def _fake_categorizer(texto, tipo_transacao, _db):
            if "uber" in texto:
                return 10, 99
            if "salario" in texto and tipo_transacao == "Receita":
                return 20, None
            return None, None

        with patch.object(ia_handlers, "_categorizar_com_mapa_inteligente", side_effect=_fake_categorizer):
            atualizados, pendentes = ia_handlers._categorizar_lancamentos_sem_categoria(db, usuario_id=123)

        self.assertEqual(pendentes, 3)
        self.assertEqual(atualizados, 2)
        self.assertEqual(lancs[0].id_categoria, 10)
        self.assertEqual(lancs[0].id_subcategoria, 99)
        self.assertEqual(lancs[2].id_categoria, 20)
        self.assertTrue(db.committed)

    async def test_processar_mensagem_rotea_categorizacao_sem_groq(self):
        update = _DummyUpdate("Categorize todos os lançamentos sem categoria")
        context = _DummyContext()
        fake_db = _FakeDB()

        with patch.object(ia_handlers.config, "GROQ_API_KEY", "fake-key"), \
             patch.object(ia_handlers, "get_db", return_value=iter([fake_db])), \
             patch.object(ia_handlers, "_usuario_e_saldo", return_value=(SimpleNamespace(id=1), 0.0, 0.0, 0.0)), \
             patch.object(ia_handlers, "_categorizar_lancamentos_sem_categoria", return_value=(3, 5)), \
             patch.object(ia_handlers, "_groq_chat_completion_async", side_effect=AssertionError("Nao deveria chamar LLM")):
            result = await ia_handlers.processar_mensagem_com_alfredo(update, context)

        self.assertEqual(result, ia_handlers.ConversationHandler.END)
        self.assertTrue(any("Categorização automática concluída" in txt for txt in update.message.html_replies))
        self.assertTrue(fake_db.closed)

    async def test_processar_mensagem_forma_pagamento_mais_usada(self):
        update = _DummyUpdate("Qual forma de pagamento eu mais utilizo?")
        context = _DummyContext()
        fake_db = _FakeDB()

        with patch.object(ia_handlers.config, "GROQ_API_KEY", "fake-key"), \
             patch.object(ia_handlers, "get_db", return_value=iter([fake_db])), \
             patch.object(ia_handlers, "_usuario_e_saldo", return_value=(SimpleNamespace(id=1), 0.0, 0.0, 0.0)), \
             patch.object(ia_handlers, "_forma_pagamento_mais_usada", return_value=("Crédito", 7, 10)), \
             patch.object(ia_handlers, "_groq_chat_completion_async", side_effect=AssertionError("Nao deveria chamar LLM")):
            result = await ia_handlers.processar_mensagem_com_alfredo(update, context)

        self.assertEqual(result, ia_handlers.ConversationHandler.END)
        resposta = "\n".join(update.message.html_replies)
        self.assertIn("Forma de pagamento mais utilizada", resposta)
        self.assertIn("Crédito", resposta)
        self.assertIn("7 de 10", resposta)
        self.assertTrue(fake_db.closed)


if __name__ == "__main__":
    unittest.main()
