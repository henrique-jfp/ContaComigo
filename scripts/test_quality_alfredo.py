
import asyncio
import os
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Configuração de caminhos
sys.path.append(os.getcwd())

import config
from database.database import get_db, get_or_create_user
from gerente_financeiro.ia_handlers import processar_mensagem_com_alfredo
from telegram import Update, User, Message, Chat
from telegram.ext import Application, ContextTypes

# Mock de objetos do Telegram com captura de resposta
class MockMessage:
    def __init__(self, text):
        self.text = text
        self.voice = None
        self.chat = Chat(id=182531653, type="private")
        self.message_id = 999
        self.from_user = User(id=182531653, is_bot=False, first_name="Henrique")
        self.last_response = ""

    async def reply_text(self, text, **kwargs):
        self.last_response = text
        return text

    async def reply_html(self, html, **kwargs):
        self.last_response = html
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
        "Qual foi meu último gasto?",
        "Qual categoria eu mais usei?"
    ],
    "NIVEL_2": [
        "Eu estou gastando mais do que deveria?",
        "Estou melhor ou pior que semana passada?"
    ],
    "NIVEL_3": [
        "O que está sabotando minhas finanças?",
        "Me dá 3 ajustes simples pra melhorar minha situação"
    ],
    "NIVEL_4": [
        "Qual decisão financeira hoje teria mais impacto no meu mês?",
        "Vale a pena eu gastar 100 reais em lazer agora?"
    ],
    "NIVEL_5": [
        "Me dá um puxão de orelha sincero",
        "Resuma minha vida financeira em 1 frase"
    ]
}

async def run_tests():
    print("🚀 REINICIANDO TESTES DE QUALIDADE (ALFREDO 2.0)...")
    relatorio = "# 🎩 ANÁLISE DE QUALIDADE DO ALFREDO\n\n"
    relatorio += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
    
    for nivel, questoes in PERGUNTAS.items():
        print(f"\n--- {nivel} ---")
        relatorio += f"## {nivel}\n\n"
        for q in questoes:
            print(f"Pergunta: {q}")
            update = MockUpdate(q)
            context = MockContext()
            
            try:
                # Intervalo para não estourar Rate Limit durante o teste
                await asyncio.sleep(2) 
                await processar_mensagem_com_alfredo(update, context)
                
                resp = update.message.last_response
                relatorio += f"### ❓ {q}\n"
                relatorio += f"🤖 **Alfredo:** {resp}\n\n"
                relatorio += "---\n\n"
                print(f"Resposta curta: {resp[:100]}...")
            except Exception as e:
                print(f"Erro: {e}")
                relatorio += f"### ❓ {q}\n❌ **ERRO:** {str(e)}\n\n---\n\n"

    with open("docs/QUALIDADE_ALFREDO_RESULTADO.md", "w") as f:
        f.write(relatorio)
    print("\n✅ TESTES DE QUALIDADE FINALIZADOS. Veja em docs/QUALIDADE_ALFREDO_RESULTADO.md")

if __name__ == "__main__":
    asyncio.run(run_tests())
