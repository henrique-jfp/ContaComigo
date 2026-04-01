"""
🚀 CONTA COMIGO - Launcher Principal
Launcher unificado, robusto e otimizado para produção.
"""

import os
import sys
import logging
import signal
from enum import Enum, auto
from threading import Thread
from dataclasses import dataclass

# Configuração de logging no nível do módulo para ser consistente
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Define os modos de execução possíveis para a aplicação."""
    BOT = auto()
    DASHBOARD = auto()
    LOCAL_DEV = auto() # Modo que roda ambos, bot e dashboard

@dataclass(frozen=True)
class AppSettings:
    """Configurações da aplicação derivadas do ambiente."""
    mode: ExecutionMode

def get_settings() -> AppSettings:
    """
    Determina o modo de execução com base nas variáveis de ambiente.
    A lógica é explícita e prioriza a configuração manual.
    """
    # 1. Prioridade máxima: Variável de ambiente explícita
    mode_str = os.getenv('CONTACOMIGO_MODE', '').lower()
    if mode_str == 'bot':
        logger.info("🔍 Modo detectado: BOT (via CONTACOMIGO_MODE)")
        return AppSettings(mode=ExecutionMode.BOT)
    if mode_str == 'dashboard':
        logger.info("🔍 Modo detectado: DASHBOARD (via CONTACOMIGO_MODE)")
        return AppSettings(mode=ExecutionMode.DASHBOARD)

    # 2. Detecção automática de ambiente de produção
    if os.getenv('RAILWAY_ENVIRONMENT'):
        logger.info("🔍 Modo detectado: BOT (ambiente Railway)")
        return AppSettings(mode=ExecutionMode.BOT)
    
    # Exemplo para Render (mais robusto que checar a variável 'RENDER')
    if os.getenv('RENDER_INSTANCE_ID'):
        service_type = os.getenv('RENDER_SERVICE_TYPE', 'web')
        if service_type == 'web':
            logger.info("🔍 Modo detectado: DASHBOARD (Render Web Service)")
            return AppSettings(mode=ExecutionMode.DASHBOARD)
        else: # 'worker' ou outro tipo
            logger.info("🔍 Modo detectado: BOT (Render Worker)")
            return AppSettings(mode=ExecutionMode.BOT)

    # 3. Fallback para ambiente de desenvolvimento local
    logger.info("🔍 Modo detectado: LOCAL_DEV (nenhum ambiente de produção detectado)")
    return AppSettings(mode=ExecutionMode.LOCAL_DEV)

def load_environment():
    """Carrega variáveis de ambiente"""
    try:
        # Tentar carregar .env se existir localmente
        if os.path.exists('.env'):
            from dotenv import load_dotenv
            load_dotenv()
            logger.info("✅ Arquivo .env carregado")
        
        # Verificar variáveis essenciais
        required_vars = [
            'TELEGRAM_TOKEN',
            'DATABASE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"❌ Variáveis de ambiente faltando: {missing_vars}")
            return False
        
        logger.info("✅ Todas as variáveis essenciais estão configuradas")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar ambiente: {e}")
        return False

def start_health_check_server():
    """Inicia servidor HTTP simples para health checks (Koyeb/Render)"""
    from flask import Flask
    
    health_app = Flask(__name__)
    
    @health_app.route('/')
    @health_app.route('/health')
    @health_app.route('/healthz')
    def health():
        return {'status': 'healthy', 'service': 'ContaComigo Bot'}, 200
    
    port = int(os.getenv('PORT', 8000))
    logger.info(f"🏥 Health check server iniciado na porta {port}")
    
    # Rodar em modo silencioso
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)
    
    health_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def start_telegram_bot():
    """Inicia o bot do Telegram"""
    try:
        logger.info("🤖 Iniciando bot do Telegram...")
        logger.info(f"📍 Python version: {sys.version}")
        logger.info(f"📍 Working directory: {os.getcwd()}")
        logger.info(f"📍 TELEGRAM_TOKEN presente: {bool(os.getenv('TELEGRAM_TOKEN'))}")
        
        # 🏥 INICIAR HEALTH CHECK SERVER EM THREAD SEPARADA
        # (Para Koyeb/Render que precisam de health checks HTTP)
        if os.getenv('PORT'):
            health_thread = Thread(target=start_health_check_server, daemon=True)
            health_thread.start()
            logger.info("✅ Health check server iniciado em thread separada")
        
        try:
            logger.info("📦 Importando módulo bot...")
            from bot import create_application
            logger.info("✅ Módulo bot importado com sucesso!")
            
            logger.info("🔧 Criando aplicação do bot...")
            application = create_application()
            logger.info("✅ Aplicação criada!")
            
            if application:
                logger.info("🚀 Iniciando polling do bot (isso pode demorar 10-30s)...")
                application.run_polling(allowed_updates=None, drop_pending_updates=True)
                logger.info("✅ Bot iniciado com sucesso!")
            else:
                logger.error("❌ Falha ao criar aplicação do bot")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"❌ ERRO FATAL ao importar/iniciar bot: {e}", exc_info=True)
            import traceback
            logger.error(f"📋 Traceback completo:\n{traceback.format_exc()}")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Erro no bot do Telegram: {e}", exc_info=True)
        sys.exit(1)

def start_dashboard():
    """Inicia o dashboard Flask"""
    try:
        logger.info("📊 Iniciando dashboard Flask...")
        from analytics.dashboard_app import app
        
        port = int(os.getenv('PORT', 10000))
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no dashboard: {e}")
        sys.exit(1)

def signal_handler(signum, frame):
    """Handler para sinais de sistema"""
    logger.info("🛑 Sinal de parada recebido. Encerrando...")
    sys.exit(0)

def apply_migrations():
    """Aplica migrations pendentes no banco de dados"""
    try:
        logger.info("🔄 Verificando migrations pendentes...")
        
        # Importar após carregar ambiente
        from pathlib import Path
        import psycopg2
        
        DATABASE_URL = os.getenv("DATABASE_URL")

        
        if not migration_file.exists():
            logger.warning(f"⚠️  Migration não encontrada: {migration_file}")
            return
        
        # Conectar e aplicar
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Verificar se tabelas já existem
        cursor.execute("""
            try:
                logger.info("🔄 Verificando migrations pendentes...")
                from pathlib import Path
                import psycopg2
                DATABASE_URL = os.getenv("DATABASE_URL")
                MIGRATIONS_DIR = Path("migrations")
                if not MIGRATIONS_DIR.exists():
                    logger.warning(f"⚠️  Diretório de migrations não encontrado: {MIGRATIONS_DIR}")
                    return
                migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
                if not migration_files:
                    logger.warning(f"⚠️  Nenhum arquivo de migration encontrado em {MIGRATIONS_DIR}")
                    return
                conn = psycopg2.connect(DATABASE_URL)
                cursor = conn.cursor()
                for migration_file in migration_files:
                    logger.info(f"➡️  Aplicando migration: {migration_file}")
                    with open(migration_file, 'r', encoding='utf-8') as f:
                        sql_content = f.read()
                    cursor.execute(sql_content)
                    conn.commit()
                    logger.info(f"✅ Migration aplicada: {migration_file}")
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"❌ Erro ao aplicar migrations: {e}")
                # Não falhar a aplicação por causa de migration
                # As tabelas podem já existir ou ser criadas depois
    if settings.mode == ExecutionMode.BOT:
        start_telegram_bot()
    elif settings.mode == ExecutionMode.DASHBOARD:
        try:
            logger.info("🔄 Verificando migrations pendentes...")
            from pathlib import Path
            import psycopg2
            DATABASE_URL = os.getenv("DATABASE_URL")
            MIGRATIONS_DIR = Path("migrations")
            if not MIGRATIONS_DIR.exists():
                logger.warning(f"⚠️  Diretório de migrations não encontrado: {MIGRATIONS_DIR}")
                return
            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            if not migration_files:
                logger.warning(f"⚠️  Nenhum arquivo de migration encontrado em {MIGRATIONS_DIR}")
                return
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            for migration_file in migration_files:
                logger.info(f"➡️  Aplicando migration: {migration_file}")
                with open(migration_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                cursor.execute(sql_content)
                conn.commit()
                logger.info(f"✅ Migration aplicada: {migration_file}")
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Erro ao aplicar migrations: {e}")
            # Não falhar a aplicação por causa de migration
            # As tabelas podem já existir ou ser criadas depois