
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
logger = logging.getLogger("TEST-ALFREDO-REAL")

# DADOS DO USUÁRIO REAL
USER_ID = 6157591255
USER_NAME = "Henrique jfp"

async def simulate_message(text):
    from gerente_financeiro.ia_handlers import processar_mensagem_com_alfredo
    from database.database import get_db, get_or_create_user
    from models import Usuario

    # Mock do Update do Telegram
    update = AsyncMock()
    update.effective_user.id = USER_ID
    update.effective_user.full_name = USER_NAME
    update.effective_user.first_name = USER_NAME.split()[0]
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
    
    # Verificar usuário no banco
    db = next(get_db())
    user = db.query(Usuario).filter(Usuario.telegram_id == USER_ID).first()
    
    if not user:
        print(f"⚠️ Usuário {USER_ID} não encontrado! Criando para teste...")
        user = get_or_create_user(db, USER_ID, USER_NAME)
    
    has_pierre = hasattr(user, 'pierre_api_key') and bool(user.pierre_api_key)
    
    print(f"\n[USUÁRIO]: {text}")
    print(f"[STATUS]: ID {user.id} | Pierre: {'Ativo' if has_pierre else 'Inativo'}")
    
    start_time = time.time()
    try:
        await processar_mensagem_com_alfredo(update, context)
    except Exception as e:
        print(f"❌ ERRO NO PROCESSAMENTO: {e}")
        import traceback
        traceback.print_exc()
        
    duration = time.time() - start_time
    
    print(f"[TEMPO]: {duration:.2f}s")
    if not captured_responses:
        print("[ALFREDO]: (Sem resposta capturada)")
    for type, resp in captured_responses:
        # Limpa HTML básico para facilitar leitura no console
        clean_resp = resp.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "")
        print(f"[ALFREDO ({type})]: {clean_resp}")
    
    return captured_responses

async def run_tests():
    perguntas = [
        # NÍVEL 1 & 2 (Sanidade e Tools)
        "Quanto eu tenho de saldo hoje?",
        "Qual o limite disponível do meu cartão?",
        "Me mostra minhas contas cadastradas",
        "Quanto eu gastei com transporte essa semana?",
        "Me mostra meus gastos por categoria esse mês",
        # NÍVEL 3 (Inteligência)
        "Estou gastando muito esse mês?",
        "Meu padrão de gastos está saudável?",
        # NÍVEL 4 (Pierre Ativo - Comportamento Estratégico)
        "Quero gastar mais esse mês, acha uma boa?",
        # NÍVEL 5 (Contexto/Edge)
        "E ontem?",
    ]

    print(f"🚀 INICIANDO TESTE REAL PARA: {USER_NAME} ({USER_ID})")
    print("=" * 60)

    for texto in perguntas:
        await simulate_message(texto)
        print("-" * 60)
        await asyncio.sleep(20) # Delay de 20s conforme solicitado

if __name__ == "__main__":
    asyncio.run(run_tests())
