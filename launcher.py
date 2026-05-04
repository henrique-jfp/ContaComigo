"""
🚀 CONTA COMIGO - Launcher Principal
Launcher unificado, robusto e otimizado para produção.
"""

# ContaComigo Launcher - v2.2.0 (Premium Dashboard Update)
import os
import sys
import logging
import signal
import asyncio
import inspect
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
    if mode_str in {'local', 'local_dev', 'both', 'all'}:
        logger.info("🔍 Modo detectado: LOCAL_DEV (via CONTACOMIGO_MODE)")
        return AppSettings(mode=ExecutionMode.LOCAL_DEV)

    # 2. Detecção automática de ambiente de produção
    if os.getenv('RAILWAY_ENVIRONMENT'):
        logger.info("🔍 Modo detectado: LOCAL_DEV (ambiente Railway, serviço único)")
        return AppSettings(mode=ExecutionMode.LOCAL_DEV)
    
    # Exemplo para Render (mais robusto que checar a variável 'RENDER')
    if os.getenv('RENDER_INSTANCE_ID'):
        service_type = os.getenv('RENDER_SERVICE_TYPE', 'web')
        if service_type == 'web':
            logger.info("🔍 Modo detectado: LOCAL_DEV (Render Web Service - Híbrido)")
            return AppSettings(mode=ExecutionMode.LOCAL_DEV)
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

import threading

_BOT_STARTED_LOCK = threading.Lock()
_BOT_STARTED = False

def start_telegram_bot(enable_health_server: bool = True):
    """Inicia o bot do Telegram"""
    global _BOT_STARTED
    with _BOT_STARTED_LOCK:
        if _BOT_STARTED:
            logger.warning("⚠️ Tentativa de iniciar segunda instância do bot ignorada.")
            return
        _BOT_STARTED = True

    try:
        logger.info("🤖 Iniciando bot do Telegram...")
        logger.info(f"📍 Python version: {sys.version}")
        logger.info(f"📍 Working directory: {os.getcwd()}")
        logger.info(f"📍 TELEGRAM_TOKEN presente: {bool(os.getenv('TELEGRAM_TOKEN'))}")
        
        # 🏥 INICIAR HEALTH CHECK SERVER EM THREAD SEPARADA
        # (Para Koyeb/Render que precisam de health checks HTTP)
        if enable_health_server and os.getenv('PORT'):
            health_thread = Thread(target=start_health_check_server, daemon=True)
            health_thread.start()
            logger.info("✅ Health check server iniciado em thread separada")
        
        try:
            logger.info("📦 Importando módulo bot...")
            from bot import create_application
            import telegram.error
            logger.info("✅ Módulo bot importado com sucesso!")
            
            logger.info("🔧 Criando aplicação do bot...")
            application = create_application()
            logger.info("✅ Aplicação criada!")
            
            if application:
                # python-telegram-bot 22+ exige um event loop ativo na thread.
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    logger.info("🔁 Event loop criado para a thread do bot.")

                logger.info("🚀 Iniciando polling do bot (isso pode demorar 10-30s)...")
                
                # Loop de retry para o bot em caso de conflito (múltiplas instâncias no Render)
                retry_count = 0
                max_retries = 5
                while retry_count < max_retries:
                    try:
                        polling_result = None
                        if inspect.iscoroutinefunction(application.run_polling):
                            coro = application.run_polling(
                                allowed_updates=None,
                                drop_pending_updates=True,
                                stop_signals=(),
                            )
                            if loop.is_running():
                                polling_result = asyncio.run_coroutine_threadsafe(coro, loop).result()
                            else:
                                polling_result = loop.run_until_complete(coro)
                        else:
                            polling_result = application.run_polling(
                                allowed_updates=None,
                                drop_pending_updates=True,
                                stop_signals=(),
                            )
                            if asyncio.iscoroutine(polling_result):
                                if loop.is_running():
                                    polling_result = asyncio.run_coroutine_threadsafe(polling_result, loop).result()
                                else:
                                    polling_result = loop.run_until_complete(polling_result)
                        _ = polling_result
                        break # Se retornar normalmente, sai do loop
                    except telegram.error.Conflict:
                        retry_count += 1
                        logger.warning(f"⚠️ Conflito de instâncias detectado (Tentativa {retry_count}/{max_retries}). Aguardando 10s...")
                        import time
                        time.sleep(10)
                    except Exception as e:
                        logger.error(f"❌ Erro durante o polling do bot: {e}")
                        break
                
                logger.info("✅ Thread do bot encerrada.")
            else:
                logger.error("❌ Falha ao criar aplicação do bot")
                # Não damos sys.exit(1) aqui para não derrubar o dashboard
                
        except Exception as e:
            logger.error(f"❌ ERRO FATAL ao importar/iniciar bot: {e}", exc_info=True)
            import traceback
            logger.error(f"📋 Traceback completo:\n{traceback.format_exc()}")
            # Se for um erro de importação ou configuração inicial crítica, talvez queiramos parar
            # Mas em modo Híbrido, queremos que o Dashboard continue se possível

        
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
    """Aplica migrations SQL com rastreamento de versao."""
    try:
        logger.info("🔄 Verificando migrations pendentes...")
        from pathlib import Path
        from database.database import engine
        from database.migration_runner import apply_sql_migrations

        if engine is None:
            logger.warning("⚠️ Engine do banco indisponivel; migrations nao aplicadas")
            return

        summary = apply_sql_migrations(engine, Path("migrations"))
        logger.info(
            "✅ Migrations processadas: aplicadas=%s ignoradas=%s",
            len(summary.get("applied", [])),
            len(summary.get("skipped", [])),
        )
        
        # 🧹 LIMPEZA TEMPORÁRIA DESATIVADA (Causava perda de dados no restart)
        # try:
        #    from scripts.cleanup_bad_data import cleanup_bad_transactions
        #    cleanup_bad_transactions()
        # except Exception as e:
        #    logger.warning(f"⚠️ Falha na limpeza de dados: {e}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao aplicar migrations: {e}")
        raise

def main() -> None:
    """
    Ponto de entrada principal da aplicação.
    Orquestra a inicialização baseada nas configurações detectadas.
    """
    logger.info("🚀 Iniciando Conta Comigo...")
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if not load_environment():
        logger.error("❌ Falha ao carregar ambiente. Encerrando...")
        sys.exit(1)

    settings = get_settings()

    if settings.mode == ExecutionMode.LOCAL_DEV:
        logger.info(f"🔄 [INSTANCE:{os.getenv('INSTANCE_ID', 'unknown')}] MODO HÍBRIDO ATIVADO")
        
        # 1. Aplicar migrações de forma SÍNCRONA antes de tudo
        logger.info("1. Aplicando migrações críticas...")
        try:
            apply_migrations()
            logger.info("✅ Migrações aplicadas com sucesso.")
        except Exception as e:
            logger.error(f"❌ FALHA CRÍTICA NAS MIGRAÇÕES: {e}")
            # Em produção, talvez queiramos continuar, mas aqui é a causa do erro 500
        
        # 2. Thread do Bot em paralelo
        logger.info("2. Iniciando Thread do Bot...")
        bot_thread = Thread(
            target=start_telegram_bot,
            kwargs={"enable_health_server": False},
            daemon=True,
        )
        bot_thread.start()

        # 3. Disparar Dashboard (Processo Principal)
        logger.info("3. Disparando Dashboard (Main Process)...")
        start_dashboard()
    elif settings.mode == ExecutionMode.BOT:
        apply_migrations()
        start_telegram_bot()
    elif settings.mode == ExecutionMode.DASHBOARD:
        apply_migrations()
        start_dashboard()
    else:
        logger.error(f"❌ Modo de execução desconhecido: {settings.mode}. Encerrando.")
        sys.exit(1)

if __name__ == "__main__":
    main()