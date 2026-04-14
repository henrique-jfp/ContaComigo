import os
import sys
from pathlib import Path
from sqlalchemy import text
from database.database import engine

def check_db():
    if not engine:
        print("❌ Engine do banco indisponível")
        return

    with engine.connect() as conn:
        print("\n--- Tabelas e Colunas ---")
        try:
            # Check orcamentos_categoria columns
            res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'orcamentos_categoria'")).fetchall()
            print(f"Colunas orcamentos_categoria: {[r[0] for r in res]}")
            
            # Check agendamentos columns
            res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'agendamentos'")).fetchall()
            print(f"Colunas agendamentos: {[r[0] for r in res]}")
            
            # Check schema_migrations
            res = conn.execute(text("SELECT filename FROM schema_migrations")).fetchall()
            print(f"Migrations aplicadas: {[r[0] for r in res]}")
        except Exception as e:
            print(f"❌ Erro ao consultar tabelas: {e}")

if __name__ == "__main__":
    check_db()
