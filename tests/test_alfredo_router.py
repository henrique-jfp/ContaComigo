import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import requests

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

    def test_intencoes_ampliadas_alfredo(self):
        casos = {
            "Quanto eu tenho hoje disponível?": ia_handlers._intencao_saldo,
            "Quanto gastei essa semana?": ia_handlers._intencao_resumo_semana,
            "Me dá um resumo geral de tudo": ia_handlers._intencao_resumo_mes,
            "Tem alguma conta vencendo hoje?": ia_handlers._intencao_contas,
            "Como esse mês se compara com o anterior?": ia_handlers._intencao_comparacao_financeira,
            "Estou correndo risco financeiro?": ia_handlers._intencao_alerta_financeiro,
            "Gastei muito hoje?": ia_handlers._intencao_alerta_financeiro,
            "Esse valor tá dentro do esperado?": ia_handlers._intencao_alerta_financeiro,
            "Esse gasto foi fora do padrão?": ia_handlers._intencao_alerta_financeiro,
            "Se eu continuar assim, como termino o mês?": ia_handlers._intencao_previsao_financeira,
            "Dá pra eu gastar hoje sem me ferrar?": ia_handlers._intencao_previsao_financeira,
            "Posso continuar gastando hoje?": ia_handlers._intencao_previsao_financeira,
            "Onde eu mais estou gastando dinheiro?": ia_handlers._intencao_analise_gastos,
            "Meu dinheiro tá acabando rápido esse mês?": ia_handlers._intencao_analise_gastos,
            "Estou comprando por impulso?": ia_handlers._intencao_analise_gastos,
            "Quais gastos são desnecessários?": ia_handlers._intencao_analise_gastos,
            "Por que meu dinheiro está acabando tão rápido?": ia_handlers._intencao_analise_gastos,
            "Tem algum hábito financeiro me prejudicando?": ia_handlers._intencao_analise_gastos,
            "Se você fosse meu gerente, o que eu deveria fazer agora?": ia_handlers._intencao_consultoria_financeira,
            "Tô meio perdido com meu dinheiro": ia_handlers._intencao_consultoria_financeira,
            "Fui irresponsável esse mês?": ia_handlers._intencao_consultoria_financeira,
            "Meu padrão de gastos tá saudável?": ia_handlers._intencao_consultoria_financeira,
            "Eu deveria ter feito essa compra?": ia_handlers._intencao_consultoria_financeira,
            "Estou conseguindo guardar dinheiro?": ia_handlers._intencao_metas,
            "Quanto preciso guardar por mês pra chegar lá?": ia_handlers._intencao_metas,
            "Vale a pena eu continuar com essa meta?": ia_handlers._intencao_metas,
        }

        for texto, fn in casos.items():
            self.assertTrue(fn(texto), msg=f"Falhou em: {texto}")

    def test_formatar_resposta_html_remove_font_tags(self):
        html = ia_handlers._formatar_resposta_html("<font color='red'>Alerta</font> **ok**")
        self.assertNotIn("<font", html)
        self.assertIn("Alerta", html)
        self.assertIn("<b>ok</b>", html)

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

    async def test_categorizar_lancamentos_sem_categoria_aplica_ids(self):
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

        with patch.object(ia_handlers, "_categorizar_com_mapa_inteligente", side_effect=_fake_categorizer), \
             patch.object(ia_handlers.config, "GROQ_API_KEY", ""):
            atualizados, pendentes = await ia_handlers._categorizar_lancamentos_sem_categoria_async(db, usuario_id=123)

        self.assertEqual(pendentes, 3)
        self.assertEqual(atualizados, 2)
        self.assertEqual(lancs[0].id_categoria, 10)
        self.assertEqual(lancs[0].id_subcategoria, 99)
        self.assertEqual(lancs[2].id_categoria, 20)
        self.assertTrue(db.committed)

    def test_resumo_contas_local_mostra_vencimentos(self):
        hoje = datetime.now()
        db = _FakeDB(
            rows=[
                SimpleNamespace(id=1, descricao="Internet", valor=120.0, ativo=True, tipo="Saída", proxima_data_execucao=hoje),
                SimpleNamespace(id=2, descricao="Aluguel", valor=1500.0, ativo=True, tipo="Saída", proxima_data_execucao=hoje.replace(day=min(28, hoje.day))),
            ]
        )
        texto = ia_handlers._resumo_contas_local(db, usuario_id=1)
        self.assertTrue("vencendo" in texto.lower() or "não tem conta vencendo" in texto.lower() or "nao tem conta vencendo" in texto.lower())
        self.assertIn("Internet", texto)

    def test_resumo_semana_local_funciona(self):
        db = _FakeDB(
            rows=[
                SimpleNamespace(id=1, descricao="Café", valor=12.0, tipo="Saída", data_transacao=datetime.now(), categoria=None),
                SimpleNamespace(id=2, descricao="Salário", valor=3000.0, tipo="Entrada", data_transacao=datetime.now(), categoria=None),
            ]
        )
        texto = ia_handlers._resumo_semana_local(db, usuario_id=1)
        self.assertIn("semana", texto.lower())
        self.assertIn("insight", texto.lower())

    def test_resumo_alerta_local_evita_titulo_de_relatorio(self):
        db = _FakeDB(
            rows=[
                SimpleNamespace(id=1, descricao="Mercado", valor=150.0, tipo="Saída", data_transacao=datetime.now(), categoria=SimpleNamespace(nome="Alimentação")),
                SimpleNamespace(id=2, descricao="Salário", valor=1000.0, tipo="Entrada", data_transacao=datetime.now(), categoria=SimpleNamespace(nome="Receita")),
            ]
        )
        texto = ia_handlers._resumo_alerta_local(db, usuario_id=1)
        self.assertNotIn("Diagnóstico de risco", texto)
        self.assertIn("Insight", texto)

    async def test_processar_mensagem_rotea_categorizacao_sem_groq(self):
        update = _DummyUpdate("Categorize todos os lançamentos sem categoria")
        context = _DummyContext()
        fake_db = _FakeDB()

        with patch.object(ia_handlers.config, "GROQ_API_KEY", "fake-key"), \
             patch.object(ia_handlers, "get_db", return_value=iter([fake_db])), \
             patch.object(ia_handlers, "_usuario_e_saldo", return_value=(SimpleNamespace(id=1, nome_completo="A", perfil_ia=""), 0.0, 0.0, 0.0)), \
             patch.object(ia_handlers, "_categorizar_lancamentos_sem_categoria_async", return_value=(3, 5)), \
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
             patch.object(ia_handlers, "_usuario_e_saldo", return_value=(SimpleNamespace(id=1, nome_completo="a", perfil_ia=""), 0.0, 0.0, 0.0)), \
             patch.object(ia_handlers, "_forma_pagamento_mais_usada", return_value=("Crédito", 7, 10)), \
             patch.object(ia_handlers, "_groq_chat_completion_async", side_effect=AssertionError("Nao deveria chamar LLM")):
            result = await ia_handlers.processar_mensagem_com_alfredo(update, context)

        self.assertEqual(result, ia_handlers.ConversationHandler.END)
        resposta = "\n".join(update.message.html_replies)
        self.assertIn("Forma de pagamento mais utilizada", resposta)
        self.assertIn("Crédito", resposta)
        self.assertIn("7 de 10", resposta)
        self.assertTrue(fake_db.closed)

    async def test_processar_mensagem_faz_busca_local_quando_groq_cai(self):
        update = _DummyUpdate("comprei arroz?")
        context = _DummyContext()
        fake_db = _FakeDB(
            rows=[
                SimpleNamespace(
                    descricao="Supermercado",
                    valor=25.40,
                    data_transacao=datetime(2026, 1, 2),
                    itens=[SimpleNamespace(nome_item="Arroz integral")],
                )
            ]
        )

        erro = requests.HTTPError("rate limit")

        with patch.object(ia_handlers.config, "GROQ_API_KEY", "fake-key"), \
             patch.object(ia_handlers, "get_db", return_value=iter([fake_db])), \
             patch.object(ia_handlers, "_usuario_e_saldo", return_value=(SimpleNamespace(id=1, nome_completo="A", perfil_ia=""), 0.0, 0.0, 0.0)), \
             patch.object(ia_handlers, "_groq_chat_completion_async", side_effect=erro):
            result = await ia_handlers.processar_mensagem_com_alfredo(update, context)

        self.assertEqual(result, ia_handlers.ConversationHandler.END)
        resposta = "\n".join(update.message.html_replies)
        self.assertIn("Busca de compras", resposta)
        self.assertIn("Arroz integral", resposta)
        self.assertTrue(fake_db.closed)

    async def test_processar_mensagem_prioriza_resposta_local_sem_groq(self):
        prompts = [
            "Tô gastando mais do que deveria?",
            "Quanto eu gastei essa semana?",
            "Meu padrão de gastos tá saudável?",
            "Posso continuar gastando hoje?",
            "Se você fosse meu gerente, o que eu deveria fazer agora?",
        ]

        for prompt in prompts:
            update = _DummyUpdate(prompt)
            context = _DummyContext()
            fake_db = _FakeDB(
                rows=[
                    SimpleNamespace(
                        id=1,
                        descricao="Mercado",
                        valor=120.0,
                        tipo="Saída",
                        data_transacao=datetime.now(),
                        categoria=SimpleNamespace(nome="Alimentação"),
                        itens=[],
                    ),
                    SimpleNamespace(
                        id=2,
                        descricao="Salário",
                        valor=3000.0,
                        tipo="Entrada",
                        data_transacao=datetime.now(),
                        categoria=SimpleNamespace(nome="Receita"),
                        itens=[],
                    ),
                ]
            )

            with patch.object(ia_handlers.config, "GROQ_API_KEY", "fake-key"), \
                 patch.object(ia_handlers, "get_db", return_value=iter([fake_db])), \
                 patch.object(ia_handlers, "_usuario_e_saldo", return_value=(SimpleNamespace(id=1, nome_completo="A", perfil_ia=""), 1000.0, 3000.0, 2000.0)), \
                 patch.object(ia_handlers, "_groq_chat_completion_async", side_effect=AssertionError("Nao deveria chamar LLM")):
                result = await ia_handlers.processar_mensagem_com_alfredo(update, context)

            self.assertEqual(result, ia_handlers.ConversationHandler.END)
            resposta = "\n".join(update.message.html_replies)
            self.assertTrue(len(resposta) > 0)
            self.assertTrue(fake_db.closed)


if __name__ == "__main__":
    unittest.main()
