
import asyncio
import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import text

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from database.database import get_db
from models import Usuario, Lancamento, ParcelamentoItem, FaturaCartao, Conta

async def run_migration_fix():
    db = next(get_db())
    try:
        target_id = 38
        source_id = 31
        
        print(f"🚀 Iniciando Migração de Dados: {source_id} -> {target_id}")
        
        # 1. Migrar Lançamentos
        count_l = db.query(Lancamento).filter(Lancamento.id_usuario == source_id).update({"id_usuario": target_id})
        print(f"✅ {count_l} lançamentos migrados.")
        
        # 2. Migrar Parcelamentos
        count_p = db.query(ParcelamentoItem).filter(ParcelamentoItem.id_usuario == source_id).update({"id_usuario": target_id})
        print(f"✅ {count_p} parcelamentos migrados.")
        
        # 3. Migrar Faturas
        count_f = db.query(FaturaCartao).filter(FaturaCartao.id_usuario == source_id).update({"id_usuario": target_id})
        print(f"✅ {count_f} faturas migradas.")
        
        # 4. Resolver Contas (Se o 31 tiver contas que o 38 não tem)
        contas_source = db.query(Conta).filter(Conta.id_usuario == source_id).all()
        contas_target = db.query(Conta).filter(Conta.id_usuario == target_id).all()
        target_external_ids = [c.external_id for c in contas_target if c.external_id]
        
        for c in contas_source:
            if c.external_id and c.external_id not in target_external_ids:
                c.id_usuario = target_id
                print(f"📦 Conta '{c.nome}' migrada.")
        
        db.commit()
        print("🎉 Migração concluída com sucesso!")

        # 5. Verificação de Integridade Final
        total = db.query(Lancamento).filter(Lancamento.id_usuario == target_id).count()
        print(f"📊 Total de lançamentos agora no Usuário {target_id}: {total}")
        
        # 6. Limpar Cache do Usuário
        from gerente_financeiro.services import limpar_cache_usuario
        usuario = db.query(Usuario).get(target_id)
        if usuario:
            limpar_cache_usuario(int(usuario.telegram_id))
            print(f"🧹 Cache limpo para o Telegram ID {usuario.telegram_id}")

    except Exception as e:
        print(f"❌ Erro na migração: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_migration_fix())
