import os
import sys
import asyncio
import logging
from sqlalchemy.orm import Session

# Adicionar o diretório raiz ao path para permitir imports do projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import get_db
from models import Usuario, Lancamento
from pierre_finance.categorizador import aplicar_regras_lancamentos_open_finance
from pierre_finance.categorizador_llm import processar_fallback_outros_llm

# Configurar logging para terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def recategorizar_todos_usuarios():
    """Percorre todos os usuários e aplica a recategorização completa."""
    db = next(get_db())
    try:
        # Buscar usuários que possuem integração Open Finance configurada
        usuarios = db.query(Usuario).filter(Usuario.pierre_api_key.isnot(None)).all()
        
        logger.info(f"🚀 Iniciando recategorização em lote para {len(usuarios)} usuários.")
        
        total_regras = 0
        total_llm = 0
        
        for user in usuarios:
            logger.info(f"👤 Processando Usuário: {user.first_name or user.telegram_id} (ID: {user.id})")
            
            try:
                # 1. Aplicar regras locais (palavras-chave novas) em TUDO
                # Usamos escopo='tudo' para forçar a revisão de lançamentos já categorizados
                n_regras = aplicar_regras_lancamentos_open_finance(db, user.id, escopo="tudo")
                logger.info(f"   ✅ Regras locais: {n_regras} lançamentos atualizados.")
                
                # 2. Refinamento por LLM (Fallback Outros)
                # Pega o que as regras não resolveram e envia para a IA
                n_llm = await processar_fallback_outros_llm(db, user.id)
                logger.info(f"   🧠 Inteligência Artificial: {n_llm} lançamentos refinados.")
                
                total_regras += n_regras
                total_llm += n_llm
                
            except Exception as e:
                logger.error(f"   ❌ Erro ao processar usuário {user.id}: {e}")
                continue
        
        logger.info("--- RELATÓRIO FINAL ---")
        logger.info(f"Total de usuários processados: {len(usuarios)}")
        logger.info(f"Total atualizado por Regras: {total_regras}")
        logger.info(f"Total atualizado por IA: {total_llm}")
        logger.info("🎉 Manutenção concluída com sucesso!")

    finally:
        db.close()

if __name__ == "__main__":
    # Rodar o script assíncrono
    asyncio.run(recategorizar_todos_usuarios())
