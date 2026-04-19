
import asyncio
import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import or_

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from database.database import get_db
from models import Lancamento, Conta

async def cleanup_faturas():
    db = next(get_db())
    try:
        user_id = 42
        termos = ["pagamento on line", "pagamento fatura", "pagamento de fatura", "pagamento efetuado", "pagamento recebido"]
        
        print("🛠️ Iniciando limpeza de faturas duplicadas...")
        
        # Busca todos os lançamentos que parecem pagamentos de fatura
        query = db.query(Lancamento).filter(
            Lancamento.id_usuario == user_id,
            Lancamento.tipo != 'Transferência'
        )
        
        count = 0
        for l in query.all():
            desc = str(l.descricao).lower()
            if any(t in desc for t in termos):
                # Se for um pagamento, convertemos para transferência
                print(f"✅ Convertendo: {l.descricao} | R$ {l.valor} -> Transferência")
                l.tipo = "Transferência"
                l.id_categoria = None # Remove categoria de despesa
                count += 1
        
        db.commit()
        print(f"🎉 Total de {count} pagamentos de fatura neutralizados.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(cleanup_faturas())
