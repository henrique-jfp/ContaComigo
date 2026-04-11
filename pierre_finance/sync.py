import logging
import asyncio
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from .client import PierreClient
from models import Usuario, Conta, Lancamento, SaldoConta, FaturaCartao, ParcelamentoItem, Categoria, Subcategoria
from .categorizador import categorizar_transacao

logger = logging.getLogger(__name__)

def _normalizar_forma_pagamento(descricao: str, account_type: str) -> str:
    desc_lower = descricao.lower()
    if "pix" in desc_lower: return "Pix"
    if account_type == "CREDIT": return "Crédito"
    if account_type in ["BANK", "PAYMENT_ACCOUNT"]: return "Débito"
    return "Nao_informado"

async def sincronizar_carga_inicial(usuario: Usuario, db: Session):
    logger.error("🚀🚀🚀 INICIANDO CARGA INICIAL - MOTOR V3 (CORRIGIDO) 🚀🚀🚀")
    if not usuario.pierre_api_key: return {"error": "Sem chave"}

    client = PierreClient(usuario.pierre_api_key)
    client.manual_update()
    await asyncio.sleep(3)

    # 1. Upsert de Contas
    res_accounts = client.get_accounts()
    if not isinstance(res_accounts, list): res_accounts = []
    accounts_map = {}
    contas_count = 0
    for acc in res_accounts:
        ext_id = str(acc.get("id"))
        p_type = acc.get("type", "BANK")
        tipo_local = "Conta Corrente"
        if p_type == "CREDIT": tipo_local = "Cartão de Crédito"
        elif p_type == "INVESTMENT": tipo_local = "Investimento"

        conta = db.query(Conta).filter(Conta.external_id == ext_id, Conta.id_usuario == usuario.id).first()
        if not conta:
            conta = Conta(id_usuario=usuario.id, external_id=ext_id)
            db.add(conta)
            contas_count += 1
        conta.nome = acc.get("name", "Conta Open Finance")
        conta.tipo = tipo_local
        if "creditCard" in acc:
            cc = acc["creditCard"]
            if "limit" in cc: conta.limite_cartao = Decimal(str(cc["limit"]))
            if "closingDay" in cc: conta.dia_fechamento = cc["closingDay"]
            if "dueDay" in cc: conta.dia_vencimento = cc["dueDay"]
        db.flush()
        accounts_map[ext_id] = conta.id

    # 2. Transações
    date_90 = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%d')
    res_txs = client.get_transactions(startDate=date_90, limit=1000, format="raw")
    cat_cache = {c.nome: c.id for c in db.query(Categoria).all()}
    subcat_cache = {(s.id_categoria, s.nome): s.id for s in db.query(Subcategoria).all()}

    txs_count = 0
    if isinstance(res_txs, list):
        for tx in res_txs:
            ext_id = str(tx.get("id"))
            if not ext_id or db.query(Lancamento).filter(Lancamento.external_id == ext_id).first(): continue
            
            valor_bruto = Decimal(str(tx.get("amount") or tx.get("value") or 0))
            acc_type = tx.get("accountType", "BANK")
            descricao = tx.get("description") or tx.get("name") or "Transação"
            desc_lower = descricao.lower()

            if acc_type == "CREDIT" and any(f in desc_lower for f in ["crédito liberado", "pix no crédito"]) and valor_bruto > 0: continue

            ganhos_reais = ["salario", "salário", "pix recebido", "ted recebida", "reembolso", "estorno"]
            if valor_bruto < 0: tipo = "Despesa"
            else: tipo = "Receita" if any(g in desc_lower for g in ganhos_reais) else "Despesa"
                
            cat_id, subcat_id = categorizar_transacao(descricao, tipo, db, cat_cache, subcat_cache)
            db.add(Lancamento(
                id_usuario=usuario.id, id_conta=accounts_map.get(str(tx.get("accountId"))),
                external_id=ext_id, descricao=descricao, valor=abs(valor_bruto),
                tipo=tipo, data_transacao=datetime.fromisoformat((tx.get("date") or tx.get("createdAt")).replace("Z", "+00:00")),
                origem="open_finance", forma_pagamento=_normalizar_forma_pagamento(descricao, acc_type),
                id_categoria=cat_id, id_subcategoria=subcat_id
            ))
            txs_count += 1

    # 3. Faturas (CORREÇÃO DE FORMATO)
    faturas_count = 0
    res_summary = client.get_bill_summary()
    summaries = []
    if isinstance(res_summary, dict):
        if "accountId" in res_summary: summaries = [res_summary]
        elif "data" in res_summary and isinstance(res_summary["data"], list): summaries = res_summary["data"]
    elif isinstance(res_summary, list): summaries = res_summary

    for summary in summaries:
        acc_id = str(summary.get("accountId"))
        conta_id = accounts_map.get(acc_id)
        if not conta_id: continue
        fake_ext_id = f"aberta_{acc_id}_{datetime.now().year}_{datetime.now().month}"
        fatura = db.query(FaturaCartao).filter(FaturaCartao.external_id == fake_ext_id).first()
        if not fatura:
            fatura = FaturaCartao(id_usuario=usuario.id, id_conta=conta_id, external_id=fake_ext_id)
            db.add(fatura)
            faturas_count += 1
        fatura.valor_total = Decimal(str(summary.get("billAmount") or summary.get("amount") or 0))
        fatura.status = "em_aberto"
        if "dueDate" in summary:
            try: fatura.data_vencimento = datetime.fromisoformat(str(summary["dueDate"]).replace("Z", "+00:00")).date()
            except: pass

    # 4. Parcelamentos (CORREÇÃO DE FORMATO)
    parcelas_count = 0
    res_inst = client.get_installments(start_date=date_90)
    inst_list = []
    if isinstance(res_inst, dict): inst_list = res_inst.get("purchases") or []
    elif isinstance(res_inst, list): inst_list = res_inst

    for inst in inst_list:
        ext_id = str(inst.get("id") or inst.get("purchaseId"))
        if not ext_id or ext_id.lower() == "none": continue
        parcela = db.query(ParcelamentoItem).filter(ParcelamentoItem.external_id == ext_id).first()
        if not parcela:
            parcela = ParcelamentoItem(id_usuario=usuario.id, external_id=ext_id)
            db.add(parcela)
            parcelas_count += 1
        parcela.id_conta = accounts_map.get(str(inst.get("accountId")))
        parcela.descricao = inst.get("description") or "Parcelamento"
        v_total = inst.get("totalAmount") or 0
        parcela.valor_total = Decimal(str(v_total))
        parcela.valor_parcela = Decimal(str(inst.get("installmentAmount") or (float(v_total)/max(1, int(inst.get("totalInstallments", 1))))))
        parcela.parcela_atual = int(inst.get("installmentNumber") or inst.get("installmentsPaid") or 1)
        parcela.total_parcelas = int(inst.get("totalInstallments") or 1)
        if "purchaseDate" in inst:
            try: parcela.data_compra = datetime.fromisoformat(str(inst["purchaseDate"]).replace("Z", "+00:00")).date()
            except: pass

    usuario.pierre_initial_sync_done = True
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()
    logger.error(f"✅ CARGA FINALIZADA: {txs_count} txs, {faturas_count} faturas, {parcelas_count} parcelas")
    return {"lancamentos": txs_count, "faturas": faturas_count, "parcelamentos": parcelas_count}

async def sincronizar_incremental(usuario: Usuario, db: Session):
    if not usuario.pierre_api_key: return 0
    if not usuario.pierre_initial_sync_done:
        res = await sincronizar_carga_inicial(usuario, db)
        return res.get("lancamentos", 0) if isinstance(res, dict) else 0
    client = PierreClient(usuario.pierre_api_key)
    # Reutiliza lógica da carga inicial simplificada aqui se necessário...
    db.commit()
    return 0
