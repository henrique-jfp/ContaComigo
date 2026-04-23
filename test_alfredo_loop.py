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

class MockUpdate:
    def __init__(self, text):
        self.message = MockMessage(text)
        self.effective_user = MockUser()

class MockContext:
    def __init__(self):
        self.user_data = {}

perguntas = [
    "Qual meu saldo do mês?",
    "Quanto tenho de patrimônio total?",
    "Como estão meus gastos comparados ao mês passado?",
    "Gastei 40 reais no mercado agora.",
    "Me lembre de pagar o Michel 500 reais na quarta-feira que vem.",
    "Qual foi meu maior gasto de todos os tempos?",
    "Crie uma meta de 12 mil reais para uma moto em 17 meses.",
    "Estou correndo risco de fechar no vermelho este mês?",
    "Agendar o pagamento da internet 100 reais todo mês.",
    "Quanto gastei no total este ano?"
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
        
        # Pausa de 10 segundos conforme solicitado
        if i < len(perguntas):
            print("Aguardando 10 segundos...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_tests())
