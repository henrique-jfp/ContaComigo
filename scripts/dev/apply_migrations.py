import sys
import os
import logging
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.database import engine
from database.migration_runner import apply_sql_migrations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("🔄 Aplicando migrations pendentes...")
        migrations_dir = Path("migrations")
        if not migrations_dir.exists():
            print(f"❌ Diretório de migrations não encontrado em {migrations_dir.absolute()}")
            return

        result = apply_sql_migrations(engine, migrations_dir)
        print(f"✅ Migrations finalizadas!")
        print(f"   - Aplicadas: {len(result['applied'])}")
        print(f"   - Ignoradas: {len(result['skipped'])}")
        
        if result['applied']:
            print("\nNovas migrations aplicadas:")
            for m in result['applied']:
                print(f"   - {m}")
                
    except Exception as e:
        print(f"❌ Erro ao aplicar migrations: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
