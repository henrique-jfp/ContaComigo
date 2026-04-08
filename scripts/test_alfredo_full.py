
import asyncio
import os
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Configuração de caminhos para importar os módulos do projeto
sys.path.append(os.getcwd())

import config
from database.database import get_db, get_or_create_user
from gerente_financeiro.ia_handlers import processar_mensagem_com_alfredo
from telegram import Update, User, Message, Chat
from telegram.ext import Application, ContextTypes

# Mock de objetos do Telegram para teste via Terminal
class MockMessage:
    def __init__(self, text, voice=None):
        self.text = text
        self.voice = voice
        self.chat = Chat(id=182531653, type="private") # Seu ID para teste
        self.message_id = 999
        self.from_user = User(id=182531653, is_bot=False, first_name="Henrique")

    async def reply_text(self, text, **kwargs):
        print(f"ALFREDO RESPONDED (Text): {text[:100]}...")
        return text

    async def reply_html(self, html, **kwargs):
        print(f"ALFREDO RESPONDED (HTML): {html[:100]}...")
        return html

class MockUpdate:
    def __init__(self, text):
        self.message = MockMessage(text)
        self.effective_user = self.message.from_user
        self.effective_chat = self.message.chat

class MockContext:
    def __init__(self):
        self.user_data = {}

PERGUNTAS = {
    "NIVEL_1": [
        "Quanto eu tenho de saldo hoje?",
        "Quanto eu gastei hoje?",
        "Quanto eu gastei essa semana?",
        "Qual foi meu último gasto?",
        "Qual categoria eu mais usei?"
    ],
    "NIVEL_2": [
        "Eu estou gastando mais do que deveria?",
        "Meu padrão de gasto está normal?",
        "Estou melhor ou pior que semana passada?"
    ],
    "NIVEL_3": [
        "O que está sabotando minhas finanças?",
        "Se eu continuar assim, como termino o mês?",
        "Me dá 3 ajustes simples pra melhorar minha situação"
    ],
    "NIVEL_4": [
        "Qual decisão financeira hoje teria mais impacto no meu mês?",
        "Esse gasto de 45 reais no mercado foge do meu padrão saudável?"
    ],
    "NIVEL_5": [
        "Me dá um puxão de orelha sincero",
        "O que você faria no meu lugar agora?",
        "Resuma minha vida financeira em 1 frase"
    ]
}

async def run_tests():
    print("🚀 INICIANDO BATERIA DE TESTES DO ALFREDO...")
    relatorio = "# 🎩 RELATÓRIO DE TESTES DO ALFREDO\n\n"
    relatorio += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
    
    for nivel, questoes in PERGUNTAS.items():
        relatorio += f"## 🟢 {nivel}\n\n"
        print(f"Testing {nivel}...")
        for q in questoes:
            print(f"Question: {q}")
            update = MockUpdate(q)
            context = MockContext()
            
            try:
                # Captura a saída do reply_html/reply_text através de um hack simples de interceptação
                # No código real, processar_mensagem_com_alfredo envia a mensagem.
                # Para o teste, vamos apenas rodar e ver se não explode e ler o log.
                await processar_mensagem_com_alfredo(update, context)
                
                relatorio += f"**Pergunta:** {q}\n"
                relatorio += f"**Status:** ✅ Processado (Verifique logs para a resposta exata)\n\n"
            except Exception as e:
                relatorio += f"**Pergunta:** {q}\n"
                relatorio += f"**Erro:** ❌ {str(e)}\n\n"
                print(f"Error on question '{q}': {e}")

    with open("docs/RELATORIO_ALFREDO_TESTE_COMPLETO.md", "w") as f:
        f.write(relatorio)
    print("✅ TESTES FINALIZADOS. Relatório gerado em docs/RELATORIO_ALFREDO_TESTE_COMPLETO.md")

if __name__ == "__main__":
    asyncio.run(run_tests())
