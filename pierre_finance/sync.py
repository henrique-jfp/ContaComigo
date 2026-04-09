import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from decimal import Decimal
from .client import PierreClient
from models import Usuario, Conta, Lancamento
from gerente_financeiro.services import _categorizar_com_mapa_inteligente

logger = logging.getLogger(__name__)

async def sincronizar_open_finance(usuario: Usuario, db: Session):
    """
    Sincroniza contas e transações do Pierre Finance para o banco local.
    """
    if not usuario.pierre_api_key:
        logger.info(f"Usuário {usuario.id} não possui chave Pierre configurada.")
        return

    client = PierreClient(usuario.pierre_api_key)
    
    # 1. Sincronizar Contas
    res_accounts = client.get_accounts()
    if isinstance(res_accounts, dict) and res_accounts.get("status_code") == 401:
        logger.warning(f"⚠️ Sincronização falhou para usuário {usuario.id}: Chave Pierre Inválida (401).")
        return
    
    if "error" in res_accounts:
        logger.error(f"Erro ao buscar contas no Pierre para usuário {usuario.id}: {res_accounts['error']}")
        return
    
    accounts_map = {} # external_id -> local_id
    for acc in res_accounts:
        ext_id = acc.get("id")
        if not ext_id: continue
        
        # Busca conta local pelo external_id
        conta_local = db.query(Conta).filter(Conta.external_id == str(ext_id)).first()
        
        if not conta_local:
            # Tenta buscar por nome se for a primeira vez e o usuário já tiver cadastrado manualmente? 
            # Melhor criar uma nova para evitar bagunça.
            conta_local = Conta(
                id_usuario=usuario.id,
                nome=acc.get("name", "Conta Open Finance"),
                tipo=acc.get("type", "Conta Corrente"),
                external_id=str(ext_id)
            )
            db.add(conta_local)
            db.flush() # Para pegar o ID
            logger.info(f"Nova conta criada via Open Finance: {conta_local.nome}")
        
        accounts_map[str(ext_id)] = conta_local.id

    # 2. Sincronizar Transações
    res_transactions = client.get_transactions(limit=50) # Puxa as últimas 50
    if "error" in res_transactions:
        logger.error(f"Erro ao buscar transações no Pierre para usuário {usuario.id}: {res_transactions['error']}")
        return

    novos_lancamentos = 0
    for tx in res_transactions:
        ext_id = tx.get("id")
        if not ext_id: continue
        
        # Verifica se já existe
        existe = db.query(Lancamento).filter(Lancamento.external_id == str(ext_id)).first()
        if existe: continue
        
        descricao = tx.get("description", "Transação Open Finance")
        valor = Decimal(str(tx.get("amount", 0)))
        tipo = "Despesa" if valor < 0 else "Receita"
        valor = abs(valor)
        
        # Categorização automática pelo Alfredo
        cat_id, subcat_id = _categorizar_com_mapa_inteligente(descricao, tipo, db)
        
        # Determina a conta local vinculada
        acc_ext_id = str(tx.get("account_id"))
        id_conta = accounts_map.get(acc_ext_id)
        
        novo_lancamento = Lancamento(
            id_usuario=usuario.id,
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            data_transacao=datetime.fromisoformat(tx.get("date")).replace(tzinfo=timezone.utc) if tx.get("date") else datetime.now(timezone.utc),
            origem="open_finance",
            external_id=str(ext_id),
            id_categoria=cat_id,
            id_subcategoria=subcat_id,
            forma_pagamento="Cartão" if "card" in str(tx.get("type")).lower() else "Transferência"
        )
        db.add(novo_lancamento)
        novos_lancamentos += 1

    db.commit()
    logger.info(f"Sincronização concluída para usuário {usuario.id}. {novos_lancamentos} novas transações.")
    return novos_lancamentos
