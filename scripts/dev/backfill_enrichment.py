import sys
import os
import asyncio
import logging

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.database import SessionLocal
from pierre_finance.enrichment import enriquecer_lancamentos_pendentes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 Iniciando Backfill de Enriquecimento via CNPJ...")
    db = SessionLocal()
    try:
        total_atualizados = 0
        while True:
            # Processa em lotes de 20 (definido no enrichment.py)
            atualizados = await enriquecer_lancamentos_pendentes(db)
            if atualizados == 0:
                break
            total_atualizados += atualizados
            logger.info(f"✅ Lote finalizado. Total acumulado: {total_atualizados}")
            # Pequena pausa entre lotes
            await asyncio.sleep(1)
            
        logger.info(f"✨ Backfill finalizado! Total de lançamentos enriquecidos: {total_atualizados}")
    except Exception as e:
        logger.error(f"❌ Erro durante o backfill: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
