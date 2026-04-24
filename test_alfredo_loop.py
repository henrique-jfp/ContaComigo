import asyncio
import time
import os
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Configuração do ambiente para conectar no Supabase
os.environ["CONTACOMIGO_MODE"] = "BOT"

# Importa o banco de dados e os handlers
from database.database import SessionLocal
from gerente_financeiro.ia_handlers import processar_mensagem_com_alfredo

# Mock do usuário Henrique (id=49, telegram_id=6157591255)
class MockUser:
    def __init__(self):
        self.id = 6157591255
        self.first_name = "Henrique"
        self.full_name = "Henrique jfp"

class MockMessage:
    def __init__(self, text):
        self.text = text
        self.voice = None
        self.reply_text = AsyncMock()
        self.reply_html = AsyncMock()
        self.delete = AsyncMock()
        self.reply_chat_action = AsyncMock()

class MockUpdate:
    def __init__(self, text):
        self.message = MockMessage(text)
        self.effective_user = MockUser()

class MockContext:
    def __init__(self):
        self.user_data = {}

perguntas = [
    "Quanto eu gastei com transporte este mês e como isso se compara com a média da semana passada?",
    "Qual foi o meu maior gasto individual desde o começo do ano?",
    "Se eu continuar gastando com alimentação o que gastei hoje, quanto vou ter de saldo no fim do mês?",
    "Liste os 3 dias em que mais saiu dinheiro da minha conta em abril e o motivo.",
    "Quanto eu já gastei com 'besteira' (lanches/lazer) este mês?",
    "O que mudou no meu perfil de gastos entre o mês passado e este mês?",
    "Qual categoria de despesa cresceu mais em percentual este mês?",
    "Me diga exatamente o que eu ainda preciso pagar até domingo (incluindo agendamentos).",
    "Eu estou tendo muitos gastos por impulso? Me dê exemplos reais.",
    "Qual foi a minha maior receita e qual a maior despesa desta semana?",
    "Quanto eu gastei no total com o Michel (via Pix) este mês?",
    "Meu saldo total acumulado é suficiente para cobrir os agendamentos dos próximos 30 dias?",
    "Qual a minha categoria mais econômica este mês em relação ao mês anterior?",
    "Teve algum gasto recorrente que subiu de preço recentemente?",
    "Quanto eu gastei com Mercado este ano, mês a mês?",
    "Se eu quiser economizar 500 reais extra este mês, qual categoria você recomenda cortar baseado nos meus dados?"
]

import sys
import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

async def run_tests():
    print("=== INICIANDO TESTE DO ALFREDO (BOT-LOOP-DEBUGGER) ===\n")
    for i, pergunta in enumerate(perguntas, 1):
        print(f"\n[{i}/10] PERGUNTA: {pergunta}")
        
        update = MockUpdate(pergunta)
        context = MockContext()
        
        start_time = time.time()
        
        try:
            await processar_mensagem_com_alfredo(update, context)
            
            # Captura a resposta enviada via reply_html ou reply_text
            respostas = []
            for call in update.message.reply_html.call_args_list:
                respostas.append(call[0][0])
            for call in update.message.reply_text.call_args_list:
                respostas.append(call[0][0])
                
            resposta_final = "\n---\n".join(respostas)
            
        except Exception as e:
            resposta_final = f"ERRO INTERNO: {e}"
            
        end_time = time.time()
        elapsed = end_time - start_time
        
        print(f"TEMPO: {elapsed:.2f}s")
        print(f"RESPOSTA:\n{resposta_final}")
        print("="*60)
        
        # Pausa de 30 segundos conforme solicitado (mitigar rate limit)
        if i < len(perguntas):
            print("Aguardando 30 segundos...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(run_tests())
