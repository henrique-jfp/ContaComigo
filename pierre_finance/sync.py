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
    
    # Se a resposta for erro 401, sair
    if isinstance(res_accounts, dict) and res_accounts.get("status_code") == 401:
        logger.warning(f"⚠️ Sincronização falhou para usuário {usuario.id}: Chave Pierre Inválida (401).")
        return

    # Se res_accounts não for uma lista, algo deu errado
    if not isinstance(res_accounts, list):
        logger.error(f"Erro ao buscar contas no Pierre para usuário {usuario.id}: {res_accounts}")
        return
    
    accounts_map = {} # external_id -> local_id
    for acc in res_accounts:
        ext_id = acc.get("id")
        if not ext_id: continue
        
        # Busca conta local pelo external_id
        conta_local = db.query(Conta).filter(Conta.external_id == str(ext_id)).first()
        
        if not conta_local:
            # Mapeamento de tipos para o padrão local
            pierre_type = acc.get("type", "BANK")
            tipo_local = "Outro"
            if pierre_type == "BANK": tipo_local = "Conta Corrente"
            elif pierre_type == "CREDIT": tipo_local = "Cartão de Crédito"
            elif pierre_type == "INVESTMENT": tipo_local = "Investimento"

            conta_local = Conta(
                id_usuario=usuario.id,
                nome=acc.get("name", "Conta Open Finance"),
                tipo=tipo_local,
                external_id=str(ext_id)
            )
            db.add(conta_local)
            db.flush() 
            logger.info(f"Nova conta criada via Open Finance: {conta_local.nome}")
        
        accounts_map[str(ext_id)] = conta_local.id

    # 2. Sincronizar Transações
    res_transactions = client.get_transactions(limit=50) 
    
    if not isinstance(res_transactions, list):
        logger.error(f"Erro ao buscar transações no Pierre para usuário {usuario.id}: {res_transactions}")
        return

    novos_lancamentos = 0
    for tx in res_transactions:
        ext_id = tx.get("id")
        if not ext_id: continue
        
        # Verifica se já existe
        existe = db.query(Lancamento).filter(Lancamento.external_id == str(ext_id)).first()
        if existe: continue
        
        descricao = tx.get("description") or tx.get("name") or "Transação Open Finance"
        valor_original = Decimal(str(tx.get("amount", 0)))
        
        # Na maioria das APIs OF, negativo é gasto. 
        # No Pierre OpenAPI, parece que amount é positivo para crédito e negativo para débito? 
        # Geralmente normalizamos: Despesa (Saída) e Receita (Entrada)
        tipo = "Despesa" if valor_original < 0 else "Receita"
        valor = abs(valor_original)
        
        # Categorização automática pelo Alfredo
        cat_id, subcat_id = _categorizar_com_mapa_inteligente(descricao, tipo, db)
        
        # Normalização da forma de pagamento para evitar CheckViolation no banco
        # Valores permitidos: 'Pix', 'Crédito', 'Débito', 'Boleto', 'Dinheiro', 'Nao_informado'
        desc_lower = descricao.lower()
        if "pix" in desc_lower:
            fp = "Pix"
        elif tx.get("accountType") == "CREDIT":
            fp = "Crédito"
        elif tx.get("accountType") == "BANK" or tx.get("accountType") == "PAYMENT_ACCOUNT":
            fp = "Débito"
        else:
            fp = "Nao_informado"

        novo_lancamento = Lancamento(
            id_usuario=usuario.id,
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            data_transacao=datetime.fromisoformat(tx.get("date").replace("Z", "+00:00")).replace(tzinfo=timezone.utc) if tx.get("date") else datetime.now(timezone.utc),
            origem="open_finance",
            external_id=str(ext_id),
            id_categoria=cat_id,
            id_subcategoria=subcat_id,
            forma_pagamento=fp
        )
        db.add(novo_lancamento)
        novos_lancamentos += 1

    db.commit()
    logger.info(f"Sincronização concluída para usuário {usuario.id}. {novos_lancamentos} novas transações.")
    return novos_lancamentos
