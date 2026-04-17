#!/usr/bin/env python3
"""
🔐 SECRET FILES LOADER - Carregar variáveis de ambiente de arquivos secretos
Prioridade: Secret Files > Environment Variables > .env local
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def load_secret_env_file():
    """
    🎯 RENDER SECRET FILES: Carregar .env do secret file
    Arquivo: /etc/secrets/environment_variables
    """
    secret_env_path = '/etc/secrets/environment_variables'
    
    if not os.path.exists(secret_env_path):
        logger.info("⚠️ Secret environment file não encontrado - usando env vars normais")
        return False
    
    try:
        logger.info("🔐 Carregando variáveis de ambiente do Secret File...")
        
        with open(secret_env_path, 'r') as f:
            lines = f.readlines()
        
        loaded_vars = 0
        for line in lines:
            line = line.strip()
            
            # Ignorar comentários e linhas vazias
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # PRIORIDADE: Se a variável já existe no ambiente (setada no Render), NÃO sobrescrever
                if key in os.environ and os.environ[key]:
                    logger.debug(f"⏭️ Mantendo valor do sistema para: {key}")
                    continue
                
                os.environ[key] = value
                loaded_vars += 1
        
        logger.info(f"🎉 {loaded_vars} variáveis carregadas do Secret File!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar Secret File: {e}")
        return False

def setup_environment():
    """
    🚀 Setup completo do ambiente
    1. Secret Files (.env)
    2. Environment Variables (Render)
    3. Local .env (desenvolvimento)
    """
    
    # 1. Tentar carregar do Secret File primeiro
    if load_secret_env_file():
        logger.info("✅ Usando configuração do Secret File")
        return
    
    # 2. Se não tiver Secret File, usar env vars normais
    if os.getenv('RENDER_SERVICE_NAME'):
        logger.info("✅ Usando Environment Variables do Render")
        return
    
    # 3. Ambiente local - tentar .env
    try:
        from dotenv import load_dotenv
        # O arquivo .env fica na raiz do projeto, no mesmo nível de secret_loader.py
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"✅ Arquivo .env local carregado de: {env_path}")
        else:
            logger.warning(f"⚠️ Nenhum arquivo .env encontrado em: {env_path}")
    except ImportError:
        logger.warning("⚠️ python-dotenv não instalado - pulando .env local")

def validate_required_vars():
    """Validar se as variáveis críticas estão presentes"""
    required_vars = [
        'TELEGRAM_TOKEN',
        'DATABASE_URL',
        'GEMINI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Variáveis obrigatórias ausentes: {missing_vars}")
        return False
    
    logger.info("✅ Todas as variáveis obrigatórias estão presentes")
    return True

# Auto-executar na importação
if __name__ == "__main__":
    setup_environment()
    validate_required_vars()
else:
    # Executar automaticamente quando importado
    setup_environment()
