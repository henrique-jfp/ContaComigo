import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import asyncio
import google.generativeai as genai
import config
from models import Usuario, Lancamento, Categoria
import json
from database.database import get_db

logger = logging.getLogger(__name__)

PROMPT_PERFIL = """
Você é um analista e psicólogo financeiro. Seu trabalho é criar ou atualizar o perfil comportamental-financeiro do usuário de forma super concisa.
Analise o histórico e os hábitos recentes a seguir.
Responda com UM ÚNICO PARÁGRAFO extremamente direto (sem rodeios, sem introduções) que descreva: O estilo de vida da pessoa, onde ela mais gasta, se tem problemas para economizar, e qual abordagem ela parece preferir na comunicação.
Esta descrição será injetada como instrução de sistema para o Bot conversar com ela.

DADOS RECENTES:
{dados_json}
"""

async def atualizar_perfil_usuario(usuario: Usuario, db: Session):
    if not config.GEMINI_API_KEY:
        return
        
    try:
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\""))
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Pega as últimas 30 transações do usuário
        lancamentos_recentes = db.query(Lancamento).filter(Lancamento.id_usuario == usuario.id).order_by(Lancamento.data_transacao.desc()).limit(30).all()
        
        if not lancamentos_recentes:
            return # Sem dados para analisar
            
        dados_resumo = []
        for l in lancamentos_recentes:
            cat_nome = l.categoria.nome if getattr(l, "categoria", None) else "Desconhecida"
            dados_resumo.append({
                "valor": float(l.valor) if l.valor else 0,
                "descricao": l.descricao,
                "tipo": l.tipo,
                "categoria": cat_nome
            })
            
        prompt = PROMPT_PERFIL.format(dados_json=json.dumps(dados_resumo, indent=2, ensure_ascii=False))
        
        # Chamada assíncrona
        response = await model.generate_content_async(prompt)
        
        if response and response.text:
            usuario.perfil_ia = response.text.replace('\n', ' ').strip()
            usuario.data_ultima_analise_perfil = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"🧠 Perfil IA atualizado para o usuário {usuario.id}")
            
    except Exception as e:
        logger.error(f"❌ Erro ao gerar perfil IA para usuário {usuario.id}: {e}")

async def job_atualizar_perfis_ia(context):
    """Job que roda a cada semana para atualizar perfis que estão muito antigos."""
    db = next(get_db())
    try:
        limite_data = datetime.now(timezone.utc) - timedelta(days=7)
        # Pegar usuários cujo perfil nunca foi analisado ou tem mais de 7 dias
        usuarios = db.query(Usuario).filter(
            (Usuario.data_ultima_analise_perfil == None) | 
            (Usuario.data_ultima_analise_perfil < limite_data)
        ).all()
        
        for u in usuarios:
            await atualizar_perfil_usuario(u, db)
            await asyncio.sleep(5)  # Protege o limite de 15 Requisições por Minuto do Gemini Free Tier
            
    except Exception as e:
        logger.error(f"Erro no job_atualizar_perfis_ia: {e}")
    finally:
        db.close()
