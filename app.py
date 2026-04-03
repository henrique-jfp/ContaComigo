#!/usr/bin/env python3
"""
🌐 APP - Wrapper Flask para Render
Arquivo de entrada para o servidor web
"""

import os
import sys

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar ambiente para Render
os.environ.setdefault('RENDER_SERVICE_TYPE', 'web')

try:
    # Importar o dashboard Flask
    from analytics.dashboard_app import app
    
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
