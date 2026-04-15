
import sys
import os
from sqlalchemy.orm import Session
from database.database import get_db
from pierre_finance.categorizador import aplicar_regras_lancamentos_open_finance
from pierre_finance.categorizador_llm import processar_fallback_outros_llm
import logging
import asyncio

# Configuração de logging básica
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recategorizar_users")

async def recategorizar_users(user_ids: list[int]):
    db = next(get_db())
    try:
        for uid in user_ids:
            logger.info(f"🚀 Iniciando recategorização para o usuário {uid}...")
            
            # Etapa 1: Aplicar regras locais a TUDO (para corrigir o que estava errado)
            n_regras = aplicar_regras_lancamentos_open_finance(db, uid, escopo="tudo")
            logger.info(f"✅ Regras locais aplicadas: {n_regras} lançamentos atualizados.")
            
            # Etapa 2: Aplicar LLM para o que sobrou em 'Outros'
            # n_llm = await processar_fallback_outros_llm(db, uid)
            # logger.info(f"🧠 LLM Fallback: {n_llm} lançamentos refinados.")
            
            logger.info(f"🏁 Finalizado recategorização para o usuário {uid}.\n")
    finally:
        db.close()

if __name__ == "__main__":
    users = [25, 26, 27]
    asyncio.run(recategorizar_users(users))
