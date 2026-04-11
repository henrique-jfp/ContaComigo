import logging
import asyncio
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from .client import PierreClient
from models import Usuario, Conta, Lancamento, SaldoConta, FaturaCartao, ParcelamentoItem
from .categorizador import categorizar_transacao

logger = logging.getLogger(__name__)

def _normalizar_forma_pagamento(descricao: str, account_type: str) -> str:
    desc_lower = descricao.lower()
    if "pix" in desc_lower:
        return "Pix"
    if account_type == "CREDIT":
        return "Crédito"
    if account_type in ["BANK", "PAYMENT_ACCOUNT"]:
        return "Débito"
    return "Nao_informado"

async def sincronizar_carga_inicial(usuario: Usuario, db: Session):
    """
    Realiza a carga inicial: 3 meses de histórico e configura a base de dados local como Source of Truth.
    """
    if not usuario.pierre_api_key:
        logger.info(f"⚠️ Usuário {usuario.id} sem chave Pierre.")
        return {"error": "Sem chave"}

    client = PierreClient(usuario.pierre_api_key)
    
    # 1. Forçar Atualização nos Bancos
    logger.info(f"🔄 Forçando manual_update para usuário {usuario.id}...")
    client.manual_update()
    await asyncio.sleep(3) # Aguarda processamento da API

    # 2. Upsert de Contas
    res_accounts = client.get_accounts()
    if isinstance(res_accounts, dict) and res_accounts.get("status_code") == 401:
        return {"error": "Chave inválida"}
        
    if not isinstance(res_accounts, list): res_accounts = []

    accounts_map = {}
    contas_count = 0
    for acc in res_accounts:
        ext_id = str(acc.get("id"))
        if not ext_id: continue
        
        # Mapeamento de Tipos
        p_type = acc.get("type", "BANK")
        tipo_local = "Outro"
        if p_type == "BANK": tipo_local = "Conta Corrente"
        elif p_type == "CREDIT": tipo_local = "Cartão de Crédito"
        elif p_type == "INVESTMENT": tipo_local = "Investimento"

        conta = db.query(Conta).filter(Conta.external_id == ext_id, Conta.id_usuario == usuario.id).first()
        if not conta:
            conta = Conta(id_usuario=usuario.id, external_id=ext_id)
            db.add(conta)
            contas_count += 1
            
        conta.nome = acc.get("name", "Conta Open Finance")
        conta.tipo = tipo_local
        
        # Dados de Cartão
        if "creditCard" in acc:
            cc = acc["creditCard"]
            if "limit" in cc: conta.limite_cartao = Decimal(str(cc["limit"]))
            if "closingDay" in cc: conta.dia_fechamento = cc["closingDay"]
            if "dueDay" in cc: conta.dia_vencimento = cc["dueDay"]
            
        db.flush()
        accounts_map[ext_id] = conta.id

    # 3. Snapshot de Saldos (Hoje)
    res_balances = client.get_balance()
    hoje = datetime.now(timezone.utc).date()
    
    if isinstance(res_balances, dict) and "accounts" in res_balances:
        for b_acc in res_balances["accounts"]:
            ext_id = str(b_acc.get("accountId") or b_acc.get("id"))
            if ext_id in accounts_map:
                id_conta = accounts_map[ext_id]
                ja_tem = db.query(SaldoConta).filter(
                    SaldoConta.id_conta == id_conta, 
                    func.date(SaldoConta.capturado_em) == hoje
                ).first()
                if not ja_tem:
                    saldo = Decimal(str(b_acc.get("balance") or b_acc.get("amount") or 0))
                    saldo_disp = Decimal(str(b_acc.get("availableLimit") or 0)) if "availableLimit" in b_acc else None
                    db.add(SaldoConta(id_conta=id_conta, id_usuario=usuario.id, saldo=saldo, saldo_disponivel=saldo_disp))

    # 4. Histórico de Transações (90 dias)
    date_90 = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%d')
    res_txs = client.get_transactions(startDate=date_90, limit=1000, format="raw")
    
    txs_count = 0
    if isinstance(res_txs, list):
        for tx in res_txs:
            ext_id = str(tx.get("id"))
            if not ext_id: continue
            
            if db.query(Lancamento).filter(Lancamento.external_id == ext_id).first():
                continue
                
            valor_bruto = Decimal(str(tx.get("amount") or tx.get("value") or 0))
            tipo = "Despesa" if valor_bruto < 0 else "Receita"
            valor = abs(valor_bruto)
            descricao = tx.get("description") or tx.get("name") or "Transação Open Finance"
            
            # Categorização Inteligente Local
            cat_id, subcat_id = categorizar_transacao(descricao, tipo, db)
            
            # Normalização de Pagamento
            fp = _normalizar_forma_pagamento(descricao, tx.get("accountType"))
            
            conta_id = accounts_map.get(str(tx.get("accountId")))
            dt_str = tx.get("date") or tx.get("createdAt")
            dt_obj = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else datetime.now(timezone.utc)

            db.add(Lancamento(
                id_usuario=usuario.id, id_conta=conta_id, external_id=ext_id,
                descricao=descricao, valor=valor, tipo=tipo, data_transacao=dt_obj,
                origem="open_finance", forma_pagamento=fp,
                id_categoria=cat_id, id_subcategoria=subcat_id
            ))
            txs_count += 1

    # 5. Faturas Fechadas
    faturas_count = 0
    res_bills = client.get_bills()
    if isinstance(res_bills, dict) and "data" in res_bills: res_bills = res_bills["data"]
    if isinstance(res_bills, list):
        for bill in res_bills:
            ext_id = str(bill.get("id"))
            if not ext_id: continue
            
            conta_id = accounts_map.get(str(bill.get("accountId")))
            if not conta_id: continue
            
            fatura = db.query(FaturaCartao).filter(FaturaCartao.external_id == ext_id).first()
            if not fatura:
                fatura = FaturaCartao(id_usuario=usuario.id, id_conta=conta_id, external_id=ext_id)
                db.add(fatura)
                faturas_count += 1
                
            fatura.valor_total = Decimal(str(bill.get("amount") or bill.get("totalAmount") or 0))
            fatura.status = bill.get("status", "fechada")
            if "dueDate" in bill:
                dt_venc = datetime.fromisoformat(bill["dueDate"].replace("Z", "+00:00")).date()
                fatura.data_vencimento = dt_venc
                fatura.mes_referencia = dt_venc.replace(day=1)
            if "closingDate" in bill:
                fatura.data_fechamento = datetime.fromisoformat(bill["closingDate"].replace("Z", "+00:00")).date()

    # 6. Parcelamentos
    parcelas_count = 0
    res_inst = client.get_installments(start_date=date_90)
    inst_list = []
    if isinstance(res_inst, dict): inst_list = res_inst.get("purchases") or res_inst.get("installments") or []
    elif isinstance(res_inst, list): inst_list = res_inst

    for inst in inst_list:
        ext_id = str(inst.get("id") or inst.get("transactionId"))
        if not ext_id: continue
        
        parcela = db.query(ParcelamentoItem).filter(ParcelamentoItem.external_id == ext_id).first()
        if not parcela:
            parcela = ParcelamentoItem(id_usuario=usuario.id, external_id=ext_id)
            db.add(parcela)
            parcelas_count += 1
            
        parcela.id_conta = accounts_map.get(str(inst.get("accountId")))
        parcela.descricao = inst.get("description") or inst.get("name") or "Parcelamento"
        parcela.valor_total = Decimal(str(inst.get("totalAmount") or 0))
        parcela.valor_parcela = Decimal(str(inst.get("amount") or 0))
        parcela.parcela_atual = int(inst.get("installmentNumber") or 1)
        parcela.total_parcelas = int(inst.get("totalInstallments") or 1)
        if "date" in inst: parcela.data_compra = datetime.fromisoformat(inst["date"].replace("Z", "+00:00")).date()
        if "dueDate" in inst: parcela.data_proxima_parcela = datetime.fromisoformat(inst["dueDate"].replace("Z", "+00:00")).date()

    # 7. Finalização
    usuario.pierre_initial_sync_done = True
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()
    
    logger.info(f"✅ Carga Inicial concluída para {usuario.id}.")
    return {
        "contas": contas_count, "lancamentos": txs_count,
        "faturas": faturas_count, "parcelamentos": parcelas_count
    }

async def sincronizar_incremental(usuario: Usuario, db: Session):
    """
    Atualiza dados novos (últimas 24h) para manter o banco sincronizado.
    """
    if not usuario.pierre_api_key: return 0
    if not usuario.pierre_initial_sync_done:
        res = await sincronizar_carga_inicial(usuario, db)
        return res.get("lancamentos", 0) if isinstance(res, dict) else 0

    client = PierreClient(usuario.pierre_api_key)
    last_sync = usuario.last_pierre_sync_at or datetime.now(timezone.utc)
    start_date = (last_sync - timedelta(hours=24)).strftime('%Y-%m-%d')
    
    accounts_map = {c.external_id: c.id for c in db.query(Conta).filter(Conta.id_usuario == usuario.id).all() if c.external_id}

    # 1. Transações Novas
    res_txs = client.get_transactions(startDate=start_date, limit=100, format="raw")
    novos = 0
    if isinstance(res_txs, list):
        for tx in res_txs:
            ext_id = str(tx.get("id"))
            if not ext_id or db.query(Lancamento).filter(Lancamento.external_id == ext_id).first():
                continue
                
            valor_bruto = Decimal(str(tx.get("amount") or 0))
            tipo = "Despesa" if valor_bruto < 0 else "Receita"
            cat_id, subcat_id = categorizar_transacao(tx.get("description", ""), tipo, db)
            
            db.add(Lancamento(
                id_usuario=usuario.id, id_conta=accounts_map.get(str(tx.get("accountId"))),
                external_id=ext_id, descricao=tx.get("description"), valor=abs(valor_bruto),
                tipo=tipo, data_transacao=datetime.fromisoformat(tx.get("date").replace("Z", "+00:00")),
                origem="open_finance", forma_pagamento=_normalizar_forma_pagamento(tx.get("description", ""), tx.get("accountType")),
                id_categoria=cat_id, id_subcategoria=subcat_id
            ))
            novos += 1

    # 2. Saldos Diários
    res_balances = client.get_balance()
    hoje = datetime.now(timezone.utc).date()
    if isinstance(res_balances, dict) and "accounts" in res_balances:
        for b_acc in res_balances["accounts"]:
            id_conta = accounts_map.get(str(b_acc.get("accountId") or b_acc.get("id")))
            if id_conta and not db.query(SaldoConta).filter(SaldoConta.id_conta == id_conta, func.date(SaldoConta.capturado_em) == hoje).first():
                db.add(SaldoConta(
                    id_conta=id_conta, id_usuario=usuario.id, 
                    saldo=Decimal(str(b_acc.get("balance") or 0)),
                    saldo_disponivel=Decimal(str(b_acc.get("availableLimit") or 0))
                ))

    # 3. Faturas
    res_bills = client.get_bills()
    if isinstance(res_bills, dict) and "data" in res_bills: res_bills = res_bills["data"]
    if isinstance(res_bills, list):
        for bill in res_bills:
            ext_id = str(bill.get("id"))
            fatura = db.query(FaturaCartao).filter(FaturaCartao.external_id == ext_id).first()
            if not fatura:
                conta_id = accounts_map.get(str(bill.get("accountId")))
                if conta_id:
                    fatura = FaturaCartao(id_usuario=usuario.id, id_conta=conta_id, external_id=ext_id)
                    db.add(fatura)
            if fatura:
                fatura.valor_total = Decimal(str(bill.get("amount") or 0))
                fatura.status = bill.get("status", "fechada")

    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()
    return novos
