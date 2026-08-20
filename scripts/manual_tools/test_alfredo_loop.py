import asyncio
import time
import os
import json
import sys
import codecs
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Forçar saída em UTF-8 para evitar erros de encode no terminal
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

# Configuração do ambiente
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
        self.reply_chat_action = AsyncMock()
        self.delete = AsyncMock()

class MockUpdate:
    def __init__(self, text):
        self.message = MockMessage(text)
        self.effective_user = MockUser()

class MockContext:
    def __init__(self):
        self.user_data = {}

perguntas = [
    "Qual a porcentagem exata do meu patrimônio total que eu comprometi com gastos reais este mês?",
    "Se eu mantiver o ritmo de gastos desta semana até o fim do ano, qual será meu saldo acumulado em dezembro?",
    "Qual subcategoria mais cresceu em valor absoluto nos últimos 30 dias e como isso afetou meu lucro mensal?",
    "Identifique 3 gastos recorrentes que podem ser 'vazamentos' de dinheiro e quanto eles custam por ano.",
    "Comparando os últimos 15 dias com o mês passado, estou sendo mais disciplinado com 'besteiras'?",
    "Quanto do meu saldo disponível hoje já está 'reservado' para compromissos que vencem nos próximos 15 dias?",
    "Qual o gasto mais 'fora da curva' (anomalia) que você encontrou no meu histórico recente?",
    "Se eu cortar 20% de 'Alimentação Fora', em quantos meses antecipo minha meta de 12 mil reais?",
    "Liste as 5 maiores entradas de abril e me diga se elas são recorrentes ou pontuais.",
    "Qual dia da semana é historicamente o meu 'dia mais caro' em gastos variáveis?",
    "Tem algum gasto fixo que parou de aparecer e eu posso ter esquecido de pagar?",
    "Se eu recebesse um bônus de 2 mil reais hoje, qual meta você recomendaria focar e por quê?",
    "Qual a diferença real entre meus limites de orçamento e o que eu realmente gastei este mês?",
    "Alfredo, analise se meus gastos com transporte estão correlacionados com o aumento de despesas em lazer.",
    "Quanto eu gastei com taxas e juros este ano e o que isso representa em relação ao meu lucro mensal médio?",
    "Diagnóstico Final: Baseado em todos os dados do MiniApp, eu estou construindo patrimônio ou apenas 'pagando incêndio'?"
]

async def run_tests():
    print("=== INICIANDO EXAME DE ALTA COMPLEXIDADE — ALFREDO 4.0 ===\n")
    for i, pergunta in enumerate(perguntas, 1):
        print(f"\n[{i}/16] PERGUNTA: {pergunta}")
        
        update = MockUpdate(pergunta)
        context = MockContext()
        
        start_time = time.time()
        
        try:
            await processar_mensagem_com_alfredo(update, context)
            
            respostas = []
            for call in update.message.reply_html.call_args_list: respostas.append(call[0][0])
            for call in update.message.reply_text.call_args_list: respostas.append(call[0][0])
            resposta_final = "\n---\n".join(respostas)
            
        except Exception as e:
            resposta_final = f"ERRO INTERNO: {e}"
            
        elapsed = time.time() - start_time
        print(f"⏱️ TEMPO: {elapsed:.2f}s")
        print(f"🤖 ALFREDO:\n{resposta_final}")
        print("="*60)
        
        if i < len(perguntas):
            print("⏳ Aguardando 60 segundos para evitar Rate Limit...")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_tests())
