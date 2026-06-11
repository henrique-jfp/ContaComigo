
import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Usuario, Lancamento, Categoria
from gerente_financeiro.ai_service import _smart_ai_completion_async

logger = logging.getLogger(__name__)

CACHE_FILE = "user_insights_cache.json"

def _load_cache() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_cache(cache: Dict[str, Any]):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao salvar cache de insights: {e}")

async def get_dynamic_alfredo_insight(db: Session, usuario: Usuario, total_balance: float, categories: Dict[str, float], installments: List[Dict[str, Any]]) -> str:
    """
    Gera um insight dinâmico do Alfredo que muda a cada 8 horas.
    Retorna 2 conselhos reais e 1 comentário engraçado/curioso.
    """
    now = datetime.now(timezone.utc)
    slot = now.hour // 8
    slot_date = now.strftime("%Y-%m-%d")
    cache_key = f"{usuario.id}_{slot_date}_{slot}"
    
    cache = _load_cache()
    
    if cache_key in cache:
        # Verifica se o insight ainda é válido (mesmo dia e mesmo slot)
        return cache[cache_key]

    # Se não está no cache, gera um novo
    logger.info(f"Gerando novo insight dinâmico para usuário {usuario.id} (Slot {slot})")
    
    # Busca gastos recentes para dar contexto ao "comentário curioso"
    sete_dias_atras = now - timedelta(days=7)
    recent_txs = db.query(Lancamento.descricao, Lancamento.valor).filter(
        Lancamento.id_usuario == usuario.id,
        Lancamento.data_transacao >= sete_dias_atras,
        Lancamento.valor < 0
    ).order_by(func.abs(Lancamento.valor).desc()).limit(10).all()
    
    tx_list = [f"{t.descricao}: R$ {abs(t.valor):.2f}" for t in recent_txs]
    
    prompt = f"""Você é o Alfredo, um assistente financeiro inteligente e com personalidade. 
Analise os dados financeiros do usuário abaixo e gere um insight curto para o dashboard.

DADOS:
- Saldo Atual: R$ {total_balance:.2f}
- Principais Categorias (90 dias): {json.dumps(categories, ensure_ascii=False)}
- Parcelamentos Ativos: {len(installments)} itens
- Gastos Recentes (últimos 7 dias): {", ".join(tx_list)}

REGRAS DO INSIGHT:
1. Deve conter 2 conselhos financeiros REAIS e ÚTEIS baseados nos números (curtos).
2. O 3º item deve ser um comentário ENGRAÇADO, CURIOSO ou uma PIADINHA sobre as finanças ou um dos gastos recentes.
3. Seja direto, use no máximo 3 frases curtas.
4. Mantenha um tom de "amigo sincero" que entende de dinheiro.
5. NÃO use termos robóticos como "com base nos seus dados".
6. Responda APENAS o texto do insight, sem prefixos.

EXEMPLO:
Você gastou bastante com Uber esse mês, que tal uma caminhada? Suas parcelas do Mercado Livre estão acabando, aguente firme. E vi que gastou na 'Doceria da Tia', se o doce for tão bom quanto seu prejuízo, eu quero um pedaço!

INSIGHT:"""

    messages = [{"role": "user", "content": prompt}]
    
    try:
        # Tenta usar a IA
        response = await _smart_ai_completion_async(messages)
        if response and isinstance(response, str):
            insight = response.strip().replace('"', '')
        else:
            # Fallback se a IA falhar
            insight = "Dica do Alfredo: Mantenha o foco nos seus objetivos e evite gastos desnecessários hoje!"
    except Exception as e:
        logger.error(f"Erro ao gerar insight via AI: {e}")
        insight = "Alfredo: O sistema de IA está descansando, mas eu continuo de olho no seu saldo!"

    # Atualiza o cache (limpa slots antigos para não crescer infinitamente)
    # Mantemos apenas os slots do dia atual para este usuário
    keys_to_delete = [k for k in cache.keys() if k.startswith(f"{usuario.id}_") and not k.startswith(f"{usuario.id}_{slot_date}")]
    for k in keys_to_delete:
        del cache[k]
        
    cache[cache_key] = insight
    _save_cache(cache)
    
    return insight
