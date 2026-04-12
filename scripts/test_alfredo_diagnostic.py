
import os
import asyncio
import logging
import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import sys

# Adiciona o diretório raiz ao path
sys.path.append(os.getcwd())

# Configura logging para capturar o que a IA está tentando fazer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TEST-ALFREDO")

async def simulate_message(text, user_id=123456, user_name="Test User", has_pierre=False):
    from gerente_financeiro.ia_handlers import processar_mensagem_com_alfredo
    from database.database import get_db, get_or_create_user
    from models import Usuario

    # Mock do Update do Telegram
    update = AsyncMock()
    update.effective_user.id = user_id
    update.effective_user.full_name = user_name
    update.effective_user.first_name = user_name.split()[0]
    update.message.text = text
    update.message.voice = None
    
    # Mock do Contexto
    context = MagicMock()
    context.user_data = {}

    # Captura de resposta
    captured_responses = []
    
    async def reply_html(text, **kwargs):
        captured_responses.append(("HTML", text))
        return AsyncMock()
    
    async def reply_text(text, **kwargs):
        captured_responses.append(("TEXT", text))
        return AsyncMock()

    update.message.reply_html = reply_html
    update.message.reply_text = reply_text
    
    # Garantir que o usuário existe e configurar Pierre
    db = next(get_db())
    user = get_or_create_user(db, user_id, user_name)
    if hasattr(user, 'pierre_api_key'):
        user.pierre_api_key = "test_key" if has_pierre else None
    db.commit()

    print(f"\n[USUÁRIO]: {text}")
    print(f"[PIERRE]: {'Ativo' if has_pierre else 'Inativo'}")
    
    start_time = time.time()
    await processar_mensagem_com_alfredo(update, context)
    duration = time.time() - start_time
    
    print(f"[TEMPO]: {duration:.2f}s")
    for type, resp in captured_responses:
        print(f"[ALFREDO ({type})]: {resp}")
    
    return captured_responses

async def run_tests():
    perguntas = [
        # NÍVEL 1
        ("Quanto eu tenho de saldo hoje?", False),
        ("Qual o limite disponível do meu cartão?", False),
        ("Me mostra minhas contas cadastradas", False),
        ("Qual foi meu último gasto?", False),
        # NÍVEL 2
        ("Quanto eu gastei com transporte essa semana?", False),
        ("Qual categoria eu mais gasto?", False),
        # NÍVEL 3
        ("Estou gastando muito esse mês?", False),
        ("Meu padrão de gastos está saudável?", False),
        # NÍVEL 4
        ("Quero gastar mais esse mês, acha uma boa?", False), # Sem Pierre
        ("Quero gastar mais esse mês, acha uma boa?", True),  # Com Pierre
        # NÍVEL 5
        ("E ontem?", False),
    ]

    for texto, pierre in perguntas:
        await simulate_message(texto, has_pierre=pierre)
        print("-" * 50)
        await asyncio.sleep(20) # Delay solicitado

if __name__ == "__main__":
    asyncio.run(run_tests())
