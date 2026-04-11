"""
Sincronização Open Finance — Pierre Finance
============================================
Motor de carga e atualização incremental de dados bancários.

Correções aplicadas v2:
- Lógica de Receita/Despesa muito mais robusta para dados bancários reais
- Parser de faturas com suporte a todos os formatos que a API pode retornar
- Parser de parcelamentos corrigido para o schema real do endpoint
- Logs detalhados para diagnóstico de falhas silenciosas
"""

import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from .client import PierreClient
from finance_utils import normalize_financial_type
from models import (
    Usuario, Conta, Lancamento, SaldoConta,
    FaturaCartao, ParcelamentoItem, Categoria, Subcategoria,
)
from .categorizador import categorizar_transacao

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_decimal(value) -> Decimal:
    """Converte qualquer valor para Decimal sem explodir."""
    try:
        return Decimal(str(value or 0))
    except InvalidOperation:
        return Decimal("0")


def _parse_iso_date(value: str | None):
    """Tenta parsear uma string ISO 8601 para datetime. Retorna None se falhar."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _normalizar_forma_pagamento(descricao: str, account_type: str) -> str:
    desc_lower = (descricao or "").lower()
    if "pix" in desc_lower:
        return "Pix"
    if account_type == "CREDIT":
        return "Crédito"
    if account_type in ("BANK", "PAYMENT_ACCOUNT"):
        return "Débito"
    return "Nao_informado"


# ---------------------------------------------------------------------------
# Lógica de tipo (Receita / Despesa) — coração do sync
# ---------------------------------------------------------------------------

# Palavras que indicam RECEITA independentemente do sinal ou conta
_SINAIS_RECEITA_FORTE = {
    "salario", "salário", "pagamento salario", "pagamento salário",
    "pix recebido", "ted recebida", "ted recebido", "doc recebido",
    "transferencia recebida", "deposito recebido", "transf.recebida",
    "reembolso", "estorno", "devolucao", "devolução",
    "rendimento", "rendimentos", "juros recebidos", "pro-labore",
    "dividendo", "dividendos", "jcp", "venda", "resgate",
}

# Palavras que indicam DESPESA independentemente do sinal ou conta
_SINAIS_DESPESA_FORTE = {
    "debito automatico", "débito automático",
    "debito em conta", "débito em conta",
    "pagamento fatura", "pagto fatura", "pgt fatura",
    "compra credito", "compra debito", "pix enviado",
    "transferencia enviada", "transf.enviada", "iof", "tarifa",
}

def _inferir_tipo(
    descricao: str,
    valor_bruto: Decimal,
    account_type: str,
    transaction_type: str | None = None,
) -> str:
    desc_norm = (descricao or "").lower()

    # 🛡️ PRIORIDADE 1: Sinais textuais explícitos (overrides)
    for sinal in _SINAIS_RECEITA_FORTE:
        if sinal in desc_norm:
            return "Receita"
            
    for sinal in _SINAIS_DESPESA_FORTE:
        if sinal in desc_norm:
            return "Despesa"

    tipo_tx_norm = normalize_financial_type(transaction_type, default="")
    if tipo_tx_norm in {"Receita", "Despesa"}:
        return tipo_tx_norm

    # 🛡️ PRIORIDADE 2: Lógica por tipo de conta e sinal numérico
    if account_type == "CREDIT":
        # No cartão de crédito (Pierre/Pluggy): 
        # Geralmente valor POSITIVO é COMPRA (Despesa)
        # Valor NEGATIVO é ESTORNO/PAGAMENTO (Receita)
        if valor_bruto < 0:
            return "Receita"
        return "Despesa"

    # Conta corrente / pagamento / investimento:
    # Valor NEGATIVO é SAÍDA (Despesa)
    # Valor POSITIVO é ENTRADA (Receita)
    if valor_bruto < 0:
        return "Despesa"

    return "Receita"


def _upsert_accounts_and_balances(usuario: Usuario, db: Session, client: PierreClient) -> dict[str, int]:
    res_accounts = client.get_accounts()
    accounts_raw = _extrair_lista_de_resposta(res_accounts)

    accounts_map: dict[str, int] = {}
    for acc in accounts_raw:
        ext_id = str(acc.get("id") or acc.get("accountId") or "")
        if not ext_id:
            continue

        conta = db.query(Conta).filter(Conta.external_id == ext_id, Conta.id_usuario == usuario.id).first()
        if not conta:
            conta = Conta(id_usuario=usuario.id, external_id=ext_id)
            db.add(conta)

        conta.nome = acc.get("name") or acc.get("displayName") or "Conta Bancária"
        p_type = acc.get("type", "BANK")
        conta.tipo = {
            "CREDIT": "Cartão de Crédito",
            "INVESTMENT": "Investimento",
            "LOAN": "Empréstimo",
        }.get(p_type, "Conta Corrente")

        cc = acc.get("creditCard") or {}
        if cc:
            conta.limite_cartao = _safe_decimal(cc.get("limit"))
            conta.dia_fechamento = int(cc.get("closingDay") or 0) or conta.dia_fechamento
            conta.dia_vencimento = int(cc.get("dueDay") or 0) or conta.dia_vencimento

        db.flush()
        accounts_map[ext_id] = conta.id

        # Upsert de Saldo: se já existe saldo capturado hoje para esta conta, apenas atualiza
        hoje = datetime.now(timezone.utc).date()
        saldo_existente = db.query(SaldoConta).filter(
            SaldoConta.id_conta == conta.id,
            func.date(SaldoConta.capturado_em) == hoje
        ).first()

        if saldo_existente:
            saldo_existente.saldo = _safe_decimal(acc.get("balance"))
            saldo_existente.saldo_disponivel = _safe_decimal(acc.get("availableBalance") or acc.get("balance"))
            saldo_existente.capturado_em = datetime.now(timezone.utc)
        else:
            db.add(SaldoConta(
                id_usuario=usuario.id,
                id_conta=conta.id,
                saldo=_safe_decimal(acc.get("balance")),
                saldo_disponivel=_safe_decimal(acc.get("availableBalance") or acc.get("balance")),
                capturado_em=datetime.now(timezone.utc)
            ))

    return accounts_map


def _upsert_bill_summaries(usuario: Usuario, db: Session, client: PierreClient, accounts_map: dict[str, int]) -> int:
    res_summary = client.get_bill_summary()
    summaries = _extrair_sumarios_fatura(res_summary)
    updated = 0

    for s in summaries:
        acc_id = str(s.get("accountId") or s.get("account_id") or "")
        conta_id = accounts_map.get(acc_id)
        if not conta_id:
            continue

        dv = _parse_iso_date(s.get("dueDate") or s.get("due_date"))
        ref_date = dv or datetime.now(timezone.utc)
        fake_ext_id = f"bill_{acc_id}_{ref_date.year}_{ref_date.month}"

        fatura = db.query(FaturaCartao).filter(
            FaturaCartao.external_id == fake_ext_id,
            FaturaCartao.id_usuario == usuario.id,
        ).first()
        if not fatura:
            fatura = FaturaCartao(id_usuario=usuario.id, id_conta=conta_id, external_id=fake_ext_id)
            db.add(fatura)

        fatura.valor_total = _safe_decimal(s.get("billAmount") or s.get("amount") or s.get("totalAmount"))
        fatura.data_vencimento = ref_date.date()
        fatura.status = "em_aberto"
        fatura.mes_referencia = ref_date.replace(day=1).date()

        df = _parse_iso_date(s.get("closeDate") or s.get("closing_date"))
        if df:
            fatura.data_fechamento = df.date()
        updated += 1

    return updated


def _upsert_installments(usuario: Usuario, db: Session, client: PierreClient, accounts_map: dict[str, int]) -> int:
    res_inst = client.get_installments()
    inst_list = _extrair_parcelamentos(res_inst)
    updated = 0

    for inst in inst_list:
        ext_id = str(inst.get("id") or inst.get("purchaseId") or "")
        if not ext_id:
            continue

        parcela = db.query(ParcelamentoItem).filter(
            ParcelamentoItem.external_id == ext_id,
            ParcelamentoItem.id_usuario == usuario.id,
        ).first()
        if not parcela:
            parcela = ParcelamentoItem(id_usuario=usuario.id, external_id=ext_id)
            db.add(parcela)

        parcela.id_conta = accounts_map.get(str(inst.get("accountId")))
        parcela.descricao = inst.get("description") or inst.get("name") or "Compra Parcelada"

        v_total = _safe_decimal(inst.get("totalAmount") or inst.get("total"))
        total_p = max(1, int(inst.get("totalInstallments") or inst.get("installments") or 1))

        parcela.valor_total = v_total
        parcela.total_parcelas = total_p
        parcela.valor_parcela = _safe_decimal(inst.get("installmentAmount") or (float(v_total) / total_p))
        parcela.parcela_atual = int(inst.get("installmentNumber") or inst.get("currentInstallment") or 1)

        dp = _parse_iso_date(inst.get("dueDate") or inst.get("nextDueDate"))
        parcela.data_proxima_parcela = dp.date() if dp else parcela.data_proxima_parcela

        dc = _parse_iso_date(inst.get("date") or inst.get("purchaseDate"))
        parcela.data_compra = dc.date() if dc else parcela.data_compra
        updated += 1

    return updated


# ---------------------------------------------------------------------------
# Funções de parsing das respostas da API
# ---------------------------------------------------------------------------

def _extrair_lista_de_resposta(res) -> list:
    if res is None: return []
    if isinstance(res, list): return res
    if isinstance(res, dict):
        # Tenta extrair de chaves comuns de listas
        for key in ["data", "purchases", "bills", "accounts", "transactions"]:
            data = res.get(key)
            if isinstance(data, list): return data
            if isinstance(data, dict): return [data]
        # Se tem chaves de objeto único, retorna como lista de 1
        if any(k in res for k in ["accountId", "id", "transactionId"]):
            return [res]
    return []


def _extrair_sumarios_fatura(res) -> list:
    """Extrai sumários de fatura com múltiplos fallbacks de schema."""
    if not res: return []
    
    # Se vier em 'data', usa o conteúdo de 'data'
    if isinstance(res, dict) and "data" in res:
        res = res["data"]
        
    if isinstance(res, list): return res
    
    if isinstance(res, dict):
        # Formato { "bills": [...] }
        if "bills" in res and isinstance(res["bills"], list):
            return res["bills"]
        # Formato objeto único
        if "billAmount" in res or "accountId" in res:
            return [res]
            
    return []


def _extrair_parcelamentos(res) -> list:
    """Extrai parcelas garantindo que pegamos a lista de 'purchases'."""
    if not res: return []
    
    # O Pierre costuma retornar { "data": { "purchases": [...] } }
    if isinstance(res, dict):
        data = res.get("data", res)
        if isinstance(data, dict):
            purchases = data.get("purchases", data.get("installments"))
            if isinstance(purchases, list):
                return purchases
        elif isinstance(data, list):
            return data
            
    if isinstance(res, list): return res
    return []


# ---------------------------------------------------------------------------
# Carga inicial
# ---------------------------------------------------------------------------

async def sincronizar_carga_inicial(usuario: Usuario, db: Session) -> dict:
    logger.info(f"🚀 [PIERRE SYNC] Iniciando carga inicial para {usuario.telegram_id}")

    if not usuario.pierre_api_key:
        return {"error": "Sem chave API configurada"}

    client = PierreClient(usuario.pierre_api_key)

    # ------------------------------------------------------------------
    # ETAPA 1: Upsert de Contas e Saldos
    # ------------------------------------------------------------------
    accounts_map = _upsert_accounts_and_balances(usuario, db, client)

    # ------------------------------------------------------------------
    # ETAPA 2: Transações (últimos 90 dias)
    # ------------------------------------------------------------------
    date_90 = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%d')
    res_txs = client.get_transactions(startDate=date_90, limit=1000, format="raw")
    txs_raw = _extrair_lista_de_resposta(res_txs)

    cat_cache = {c.nome: c.id for c in db.query(Categoria).all()}
    subcat_cache = {(s.id_categoria, s.nome): s.id for s in db.query(Subcategoria).all()}

    txs_count = 0
    for tx in txs_raw:
        ext_id = str(tx.get("id") or tx.get("transactionId") or "")
        if not ext_id or db.query(Lancamento).filter(Lancamento.external_id == ext_id).first():
            continue

        valor_bruto = _safe_decimal(tx.get("amount") or tx.get("value"))
        acc_type = tx.get("accountType") or (tx.get("account") or {}).get("type") or "BANK"
        tx_type = tx.get("type") or tx.get("transactionType")
        descricao = (tx.get("description") or tx.get("name") or "Transação").strip()

        tipo = _inferir_tipo(descricao, valor_bruto, acc_type, tx_type)
        cat_id, subcat_id = categorizar_transacao(descricao, tipo, db, cat_cache, subcat_cache)

        db.add(Lancamento(
            id_usuario=usuario.id,
            id_conta=accounts_map.get(str(tx.get("accountId"))),
            external_id=ext_id,
            descricao=descricao,
            valor=abs(valor_bruto),
            tipo=tipo,
            data_transacao=_parse_iso_date(tx.get("date")) or datetime.now(timezone.utc),
            origem="open_finance",
            forma_pagamento=_normalizar_forma_pagamento(descricao, acc_type),
            id_categoria=cat_id,
            id_subcategoria=subcat_id,
        ))
        txs_count += 1
        if txs_count % 100 == 0: db.flush()

    # ------------------------------------------------------------------
    # ETAPA 3: Faturas Atuais e Próximas
    # ------------------------------------------------------------------
    _upsert_bill_summaries(usuario, db, client, accounts_map)

    # ------------------------------------------------------------------
    # ETAPA 4: Parcelamentos (O coração do Modo Deus)
    # ------------------------------------------------------------------
    _upsert_installments(usuario, db, client, accounts_map)

    usuario.pierre_initial_sync_done = True
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": "success",
        "lancamentos": txs_count,
        "contas": len(accounts_map)
    }

# ---------------------------------------------------------------------------
# Sincronização incremental
# ---------------------------------------------------------------------------

async def sincronizar_incremental(usuario: Usuario, db: Session) -> int:
    """
    Busca apenas as transações mais recentes (últimas 48h) e insere
    as que ainda não existem no banco local.
    """
    if not usuario.pierre_api_key:
        return 0

    # Se a carga inicial nunca foi feita, delega para ela
    if not usuario.pierre_initial_sync_done:
        res = await sincronizar_carga_inicial(usuario, db)
        return res.get("lancamentos", 0) if isinstance(res, dict) else 0

    client = PierreClient(usuario.pierre_api_key)
    date_48h = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime('%Y-%m-%d')

    accounts_map = _upsert_accounts_and_balances(usuario, db, client)
    res_txs = client.get_transactions(startDate=date_48h, limit=200, format="raw")
    txs_raw = _extrair_lista_de_resposta(res_txs)

    cat_cache: dict[str, int] = {c.nome: c.id for c in db.query(Categoria).all()}
    subcat_cache: dict[tuple, int] = {
        (s.id_categoria, s.nome): s.id for s in db.query(Subcategoria).all()
    }

    novos = 0
    for tx in txs_raw:
        ext_id = str(tx.get("id") or "")
        if not ext_id:
            continue
        if db.query(Lancamento).filter(Lancamento.external_id == ext_id).first():
            continue

        valor_bruto = _safe_decimal(tx.get("amount") or tx.get("value") or 0)
        acc_type = tx.get("accountType") or (tx.get("account") or {}).get("type") or "BANK"
        tx_type = tx.get("type") or tx.get("transactionType")
        descricao = (tx.get("description") or tx.get("name") or "Transação").strip()

        tipo = _inferir_tipo(descricao, valor_bruto, acc_type, tx_type)
        cat_id, subcat_id = categorizar_transacao(descricao, tipo, db, cat_cache, subcat_cache)

        data_tx = (
            _parse_iso_date(tx.get("date"))
            or _parse_iso_date(tx.get("createdAt"))
            or datetime.now(timezone.utc)
        )

        acc_id_tx = str(tx.get("accountId") or "")
        db.add(Lancamento(
            id_usuario=usuario.id,
            id_conta=accounts_map.get(acc_id_tx),
            external_id=ext_id,
            descricao=descricao,
            valor=abs(valor_bruto),
            tipo=tipo,
            data_transacao=data_tx,
            origem="open_finance",
            forma_pagamento=_normalizar_forma_pagamento(descricao, acc_type),
            id_categoria=cat_id,
            id_subcategoria=subcat_id,
        ))
        novos += 1

    faturas_atualizadas = _upsert_bill_summaries(usuario, db, client, accounts_map)
    parcelamentos_atualizados = _upsert_installments(usuario, db, client, accounts_map)

    if novos or faturas_atualizadas or parcelamentos_atualizados:
        db.commit()
        logger.info(
            "[PIERRE SYNC] Incremental: %s transações, %s faturas e %s parcelamentos atualizados",
            novos,
            faturas_atualizadas,
            parcelamentos_atualizados,
        )

    # Atualiza timestamp de última sync
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()

    return novos
