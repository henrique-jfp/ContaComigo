import os
from sqlalchemy import text
from database.database import engine

def force_migrate():
    sql = """
    ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS external_id VARCHAR UNIQUE;
    ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS periodo VARCHAR DEFAULT 'monthly';
    ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS recorrente BOOLEAN DEFAULT TRUE;
    ALTER TABLE orcamentos_categoria ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;

    ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS external_id VARCHAR UNIQUE;
    ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS origem_externa VARCHAR;
    ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS status VARCHAR;
    """
    
    if not engine:
        print("❌ Engine não disponível")
        return

    print("🚀 Iniciando migração forçada...")
    try:
        with engine.begin() as conn:
            # Executar cada comando separadamente para evitar problemas em transações longas
            for line in sql.strip().split(';'):
                if line.strip():
                    print(f"Executando: {line.strip()[:50]}...")
                    conn.execute(text(line.strip()))
        print("✅ Colunas criadas/verificadas com sucesso!")
    except Exception as e:
        print(f"❌ Erro na migração forçada: {e}")

if __name__ == "__main__":
    force_migrate()
