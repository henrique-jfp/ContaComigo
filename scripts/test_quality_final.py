
import asyncio
import os
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Configuração de caminhos
sys.path.append(os.getcwd())

# Força recarregamento do .env limpo
load_dotenv(override=True)

import config
from database.database import get_db, get_or_create_user
from gerente_financeiro.ia_handlers import processar_mensagem_com_alfredo
from telegram import Update, User, Message, Chat
from telegram.ext import Application, ContextTypes

# Mock de objetos do Telegram
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

# Testes Reduzidos para Focar em Qualidade (1 de cada nível para evitar Rate Limit mesmo com 10s)
PERGUNTAS = {
    "NIVEL_1": ["Quanto eu tenho de saldo hoje?", "Qual foi meu último gasto?"],
    "NIVEL_2": ["Eu estou gastando mais do que deveria?"],
    "NIVEL_3": ["O que está sabotando minhas finanças?"],
    "NIVEL_4": ["Vale a pena eu gastar 100 reais em lazer agora?"],
    "NIVEL_5": ["Me dá um puxão de orelha sincero", "Resuma minha vida financeira em 1 frase"]
}

async def run_tests():
    print("🚀 INICIANDO TESTE DE QUALIDADE (PAUSA 10S)...")
    print(f"GROQ KEY: {config.GROQ_API_KEY[:10]}...")
    print(f"GEMINI KEY: {config.GEMINI_API_KEY[:10]}...")
    
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
                # Pausa de 10 segundos para respeitar RPM (Requests Per Minute)
                await asyncio.sleep(10) 
                await processar_mensagem_com_alfredo(update, context)
                
                resp = update.message.last_response
                relatorio += f"### ❓ {q}\n"
                relatorio += f"🤖 **Alfredo:**\n{resp}\n\n"
                relatorio += "---\n\n"
                print("✅ Respondido.")
            except Exception as e:
                print(f"❌ Erro: {e}")
                relatorio += f"### ❓ {q}\n❌ **ERRO:** {str(e)}\n\n---\n\n"

    with open("docs/QUALIDADE_ALFREDO_FINAL.md", "w") as f:
        f.write(relatorio)
    print("\n✅ TESTE CONCLUÍDO. Resultados em docs/QUALIDADE_ALFREDO_FINAL.md")

if __name__ == "__main__":
    asyncio.run(run_tests())
