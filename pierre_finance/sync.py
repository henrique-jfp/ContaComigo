import logging
import asyncio
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from .client import PierreClient
from models import Usuario, Conta, Lancamento, SaldoConta, FaturaCartao, ParcelamentoItem
from .categorizador import categorizar_transacao

logger = logging.getLogger(__name__)

def _normalizar_forma_pagamento(descricao: str, tipo_conta: str) -> str:
    desc_lower = descricao.lower()
    if "pix" in desc_lower:
        return "Pix"
    elif tipo_conta == "CREDIT":
        return "Crédito"
    elif tipo_conta in ["BANK", "PAYMENT_ACCOUNT"]:
        return "Débito"
    return "Nao_informado"

async def sincronizar_carga_inicial(usuario: Usuario, db: Session):
    """
    Realiza a carga inicial: 3 meses de histórico e configura a base de dados.
    """
    if not usuario.pierre_api_key:
        logger.info(f"Usuário {usuario.id} não possui chave Pierre configurada.")
        return {"error": "Sem chave"}

    client = PierreClient(usuario.pierre_api_key)
    
    # 1. Forçar Atualização
    logger.info(f"Iniciando carga inicial Pierre para usuário {usuario.id}...")
    client.manual_update()
    await asyncio.sleep(3) # Aguarda processamento inicial

    # 2. Sincronizar Contas
    res_accounts = client.get_accounts()
    if isinstance(res_accounts, dict) and res_accounts.get("status_code") == 401:
        logger.warning(f"Chave Pierre Inválida para usuário {usuario.id}.")
        return {"error": "Chave inválida"}
        
    if not isinstance(res_accounts, list):
        res_accounts = []

    accounts_map = {}
    contas_salvas = 0
    for acc in res_accounts:
        ext_id = str(acc.get("id"))
        if not ext_id: continue
        
        pierre_type = acc.get("type", "BANK")
        tipo_local = "Outro"
        if pierre_type == "BANK": tipo_local = "Conta Corrente"
        elif pierre_type == "CREDIT": tipo_local = "Cartão de Crédito"
        elif pierre_type == "INVESTMENT": tipo_local = "Investimento"

        conta = db.query(Conta).filter(Conta.external_id == ext_id, Conta.id_usuario == usuario.id).first()
        if not conta:
            conta = Conta(id_usuario=usuario.id, external_id=ext_id)
            db.add(conta)
            contas_salvas += 1
            
        conta.nome = acc.get("name", "Conta Open Finance")
        conta.tipo = tipo_local
        
        if "creditCard" in acc:
            cc = acc["creditCard"]
            if "limit" in cc: conta.limite_cartao = Decimal(str(cc["limit"]))
            if "closingDay" in cc: conta.dia_fechamento = cc["closingDay"]
            if "dueDay" in cc: conta.dia_vencimento = cc["dueDay"]
            
        db.flush()
        accounts_map[ext_id] = conta.id

    # 3. Sincronizar Saldos Diários
    res_balances = client.get_balance()
    hoje = datetime.now(timezone.utc).date()
    
    if isinstance(res_balances, dict) and "accounts" in res_balances:
        for b_acc in res_balances["accounts"]:
            ext_id = str(b_acc.get("accountId") or b_acc.get("id"))
            if ext_id in accounts_map:
                id_conta = accounts_map[ext_id]
                # Verifica se já tem saldo hoje
                ja_tem = db.query(SaldoConta).filter(
                    SaldoConta.id_conta == id_conta, 
                    db.func.date(SaldoConta.capturado_em) == hoje
                ).first()
                if not ja_tem:
                    saldo = Decimal(str(b_acc.get("balance") or b_acc.get("amount") or 0))
                    saldo_disp = Decimal(str(b_acc.get("availableLimit") or 0)) if "availableLimit" in b_acc else None
                    db.add(SaldoConta(id_conta=id_conta, id_usuario=usuario.id, saldo=saldo, saldo_disponivel=saldo_disp))

    # 4. Buscar Transações (Últimos 90 dias)
    startDate = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%d')
    res_transactions = client.get_transactions(startDate=startDate, limit=1000, format="raw")
    
    lancamentos_salvos = 0
    if isinstance(res_transactions, list):
        for tx in res_transactions:
            ext_id = str(tx.get("id"))
            if not ext_id: continue
            
            if db.query(Lancamento).filter(Lancamento.external_id == ext_id, Lancamento.id_usuario == usuario.id).first():
                continue
                
            valor_bruto = Decimal(str(tx.get("amount") or tx.get("value") or 0))
            tipo = "Despesa" if valor_bruto < 0 else "Receita"
            valor = abs(valor_bruto)
            descricao = tx.get("description") or tx.get("name") or "Transação Open Finance"
            
            cat_id, subcat_id = categorizar_transacao(descricao, tipo, db)
            
            acc_type = tx.get("accountType")
            fp = _normalizar_forma_pagamento(descricao, acc_type)
            
            conta_id = accounts_map.get(str(tx.get("accountId")))
            
            dt_str = tx.get("date") or tx.get("createdAt")
            if dt_str:
                dt_obj = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            else:
                dt_obj = datetime.now(timezone.utc)

            novo_lanc = Lancamento(
                id_usuario=usuario.id,
                id_conta=conta_id,
                external_id=ext_id,
                descricao=descricao,
                valor=valor,
                tipo=tipo,
                data_transacao=dt_obj,
                origem="open_finance",
                forma_pagamento=fp,
                id_categoria=cat_id,
                id_subcategoria=subcat_id
            )
            db.add(novo_lanc)
            lancamentos_salvos += 1

    # 5. Faturas Fechadas
    faturas_salvas = 0
    res_bills = client.get_bills()
    if isinstance(res_bills, dict) and "data" in res_bills:
        res_bills = res_bills["data"]
        
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
                faturas_salvas += 1
                
            fatura.valor_total = Decimal(str(bill.get("amount") or bill.get("totalAmount") or 0))
            fatura.status = bill.get("status", "fechada")
            
            if "dueDate" in bill:
                dt_venc = datetime.fromisoformat(bill["dueDate"].replace("Z", "+00:00")).date()
                fatura.data_vencimento = dt_venc
                fatura.mes_referencia = dt_venc.replace(day=1)
            
            if "closingDate" in bill:
                fatura.data_fechamento = datetime.fromisoformat(bill["closingDate"].replace("Z", "+00:00")).date()

    # 6. Parcelamentos
    parcelas_salvas = 0
    res_inst = client.get_installments(start_date=startDate)
    
    inst_list = []
    if isinstance(res_inst, dict):
        inst_list = res_inst.get("purchases") or res_inst.get("installments") or res_inst.get("data") or []
    elif isinstance(res_inst, list):
        inst_list = res_inst

    for inst in inst_list:
        ext_id = str(inst.get("id") or inst.get("transactionId"))
        if not ext_id: continue
        
        conta_id = accounts_map.get(str(inst.get("accountId")))
        
        parcela = db.query(ParcelamentoItem).filter(ParcelamentoItem.external_id == ext_id).first()
        if not parcela:
            parcela = ParcelamentoItem(id_usuario=usuario.id, external_id=ext_id)
            db.add(parcela)
            parcelas_salvas += 1
            
        parcela.id_conta = conta_id
        parcela.descricao = inst.get("description") or inst.get("name") or inst.get("merchant") or "Parcelamento"
        parcela.valor_total = Decimal(str(inst.get("totalAmount") or inst.get("amount") or 0))
        parcela.valor_parcela = Decimal(str(inst.get("amount") or inst.get("value") or 0))
        parcela.parcela_atual = int(inst.get("installmentNumber") or inst.get("currentInstallment") or 1)
        parcela.total_parcelas = int(inst.get("totalInstallments") or inst.get("totalParcelas") or 1)
        
        if "date" in inst or "createdAt" in inst:
            dt_compra = inst.get("date") or inst.get("createdAt")
            parcela.data_compra = datetime.fromisoformat(dt_compra.replace("Z", "+00:00")).date()
            
        if "dueDate" in inst:
            parcela.data_proxima_parcela = datetime.fromisoformat(inst["dueDate"].replace("Z", "+00:00")).date()

    # 7. Finalização
    usuario.pierre_initial_sync_done = True
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()
    
    logger.info(f"Carga inicial Pierre concluída para {usuario.id}: {contas_salvas} contas, {lancamentos_salvos} transações.")
    return {
        "contas": contas_salvas,
        "lancamentos": lancamentos_salvos,
        "faturas": faturas_salvas,
        "parcelamentos": parcelas_salvas
    }

async def sincronizar_incremental(usuario: Usuario, db: Session):
    """
    Atualiza apenas dados novos desde a última sincronização.
    """
    if not usuario.pierre_api_key:
        return 0
        
    if not usuario.pierre_initial_sync_done:
        logger.info(f"Usuário {usuario.id} requer carga inicial.")
        res = await sincronizar_carga_inicial(usuario, db)
        return res.get("lancamentos", 0) if isinstance(res, dict) else 0

    client = PierreClient(usuario.pierre_api_key)
    
    # 1. Start Date = última sync - 24 horas (overlap)
    last_sync = usuario.last_pierre_sync_at or datetime.now(timezone.utc)
    start_date = (last_sync - timedelta(hours=24)).strftime('%Y-%m-%d')
    
    # Buscar contas para map (cache)
    accounts_map = {c.external_id: c.id for c in db.query(Conta).filter(Conta.id_usuario == usuario.id).all() if c.external_id}

    # 2. Atualizar Transações
    res_transactions = client.get_transactions(startDate=start_date, limit=100, format="raw")
    novos_lancamentos = 0
    
    if isinstance(res_transactions, list):
        for tx in res_transactions:
            ext_id = str(tx.get("id"))
            if not ext_id: continue
            
            if db.query(Lancamento).filter(Lancamento.external_id == ext_id).first():
                continue
                
            valor_bruto = Decimal(str(tx.get("amount") or tx.get("value") or 0))
            tipo = "Despesa" if valor_bruto < 0 else "Receita"
            valor = abs(valor_bruto)
            descricao = tx.get("description") or tx.get("name") or "Transação Open Finance"
            
            cat_id, subcat_id = categorizar_transacao(descricao, tipo, db)
            acc_type = tx.get("accountType")
            fp = _normalizar_forma_pagamento(descricao, acc_type)
            conta_id = accounts_map.get(str(tx.get("accountId")))
            
            dt_str = tx.get("date") or tx.get("createdAt")
            if dt_str:
                dt_obj = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            else:
                dt_obj = datetime.now(timezone.utc)

            novo_lanc = Lancamento(
                id_usuario=usuario.id,
                id_conta=conta_id,
                external_id=ext_id,
                descricao=descricao,
                valor=valor,
                tipo=tipo,
                data_transacao=dt_obj,
                origem="open_finance",
                forma_pagamento=fp,
                id_categoria=cat_id,
                id_subcategoria=subcat_id
            )
            db.add(novo_lanc)
            novos_lancamentos += 1

    # 3. Atualizar Saldos Diários
    res_balances = client.get_balance()
    hoje = datetime.now(timezone.utc).date()
    if isinstance(res_balances, dict) and "accounts" in res_balances:
        for b_acc in res_balances["accounts"]:
            ext_id = str(b_acc.get("accountId") or b_acc.get("id"))
            if ext_id in accounts_map:
                id_conta = accounts_map[ext_id]
                ja_tem = db.query(SaldoConta).filter(
                    SaldoConta.id_conta == id_conta, 
                    db.func.date(SaldoConta.capturado_em) == hoje
                ).first()
                if not ja_tem:
                    saldo = Decimal(str(b_acc.get("balance") or b_acc.get("amount") or 0))
                    saldo_disp = Decimal(str(b_acc.get("availableLimit") or 0)) if "availableLimit" in b_acc else None
                    db.add(SaldoConta(id_conta=id_conta, id_usuario=usuario.id, saldo=saldo, saldo_disponivel=saldo_disp))

    # 4. Faturas Fechadas
    res_bills = client.get_bills()
    if isinstance(res_bills, dict) and "data" in res_bills:
        res_bills = res_bills["data"]
        
    if isinstance(res_bills, list):
        for bill in res_bills:
            ext_id = str(bill.get("id"))
            if not ext_id: continue
            
            fatura = db.query(FaturaCartao).filter(FaturaCartao.external_id == ext_id).first()
            if not fatura:
                conta_id = accounts_map.get(str(bill.get("accountId")))
                if conta_id:
                    fatura = FaturaCartao(id_usuario=usuario.id, id_conta=conta_id, external_id=ext_id)
                    db.add(fatura)
                    
            if fatura:
                fatura.valor_total = Decimal(str(bill.get("amount") or bill.get("totalAmount") or 0))
                fatura.status = bill.get("status", "fechada")
                if "dueDate" in bill:
                    dt_venc = datetime.fromisoformat(bill["dueDate"].replace("Z", "+00:00")).date()
                    fatura.data_vencimento = dt_venc
                    fatura.mes_referencia = dt_venc.replace(day=1)

    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()
    
    logger.info(f"Sync Incremental Pierre concluída para {usuario.id}. {novos_lancamentos} novas transações.")
    return novos_lancamentos
