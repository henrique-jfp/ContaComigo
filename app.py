#!/usr/bin/env python3
"""
🌐 APP - Wrapper Flask para Render
Arquivo de entrada para o servidor web
"""

import os
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar ambiente para Render
os.environ.setdefault('RENDER_SERVICE_TYPE', 'web')

try:
    from database.database import engine as db_engine
    from database.migration_runner import apply_sql_migrations

    if db_engine is not None:
        apply_sql_migrations(db_engine, Path("migrations"))

    # Importar o dashboard Flask
    from analytics.dashboard_app import app
    
    # 🔥 INICIALIZAÇÃO HÍBRIDA (Bot + Dashboard)
    # Quando o gunicorn carrega o 'app', precisamos subir o bot em thread
    try:
        from threading import Thread
        from launcher import start_telegram_bot
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info("🔄 Detectado carregamento da aplicação. Iniciando thread do Bot...")
        
        bot_thread = Thread(
            target=start_telegram_bot,
            kwargs={"enable_health_server": False},
            daemon=True,
        )
        bot_thread.start()
        logger.info("✅ Thread do Bot disparada em background.")
    except Exception as e_bot:
        print(f"⚠️ Falha ao iniciar bot em background: {e_bot}")

    # Configuração para produção
    if __name__ != "__main__":
        # Quando chamado pelo gunicorn
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
    
except Exception as e:
    print(f"❌ Erro ao importar app: {e}")
    # Criar app Flask básico como fallback
    from flask import Flask
    
    app = Flask(__name__)
    
    @app.route('/')
    def health_check():
        return {
            "status": "error",
            "message": f"Erro na inicialização: {str(e)}",
            "service": "ContaComigo"
        }
    
    @app.route('/health')
    def health():
        return {"status": "ok", "service": "ContaComigo"}

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
