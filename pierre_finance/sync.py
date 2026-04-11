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
import asyncio
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from .client import PierreClient
from models import (
    Usuario, Conta, Lancamento, SaldoConta,
    FaturaCartao, ParcelamentoItem, Categoria, Subcategoria,
)
from .categorizador import categorizar_transacao, normalizar_descricao

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

# Palavras que indicam RECEITA mesmo em conta corrente
_SINAIS_RECEITA = {
    "salario", "salário", "pagamento salario", "pagamento salário",
    "pix recebido", "ted recebida", "ted recebido", "doc recebido",
    "transferencia recebida", "deposito recebido",
    "reembolso", "estorno", "devolucao", "devolução",
    "rendimento", "rendimentos", "juros recebidos",
    "dividendo", "dividendos", "jcp",
    "bolsa", "beneficio", "benefício", "auxilio", "auxílio",
    "fgts", "seguro desemprego", "inss recebido",
    "venda ", "mercado livre", "mercadolivre", "olx", "enjoei",
}

# Palavras que indicam DESPESA mesmo com valor positivo (ex: crédito liberado)
_SINAIS_DESPESA_FORCADOS = {
    "debito automatico", "débito automático",
    "debito em conta", "débito em conta",
    "pagamento fatura", "pagto fatura", "pgt fatura",
    "compra credito", "compra debito",
}

# Para cartão de crédito: transações com valor NEGATIVO geralmente são créditos/estornos
# e com valor POSITIVO são compras (despesas)
def _inferir_tipo(
    descricao: str,
    valor_bruto: Decimal,
    account_type: str,
) -> str:
    desc_norm = (descricao or "").lower()

    # 🛡️ PRIORIDADE MÁXIMA: Sinais claros de ganho
    ganhos = ["recebido", "salario", "salário", "reembolso", "estorno", "rendimento", "dividendo", "recebimento"]
    if any(g in desc_norm for g in ganhos):
        return "Receita"

    # Verifica sinais de despesa forçada
    for sinal in _SINAIS_DESPESA_FORCADOS:
        if sinal in desc_norm:
            return "Despesa"

    if account_type == "CREDIT":
        # No cartão: positivo = compra (despesa), negativo = estorno (receita)
        if valor_bruto < 0:
            return "Receita"
        return "Despesa"

    # Conta corrente / pagamento:
    if valor_bruto < 0:
        return "Despesa"

    # Valor positivo em conta corrente
    return "Receita"


# ---------------------------------------------------------------------------
# Funções de parsing das respostas da API
# ---------------------------------------------------------------------------

def _extrair_lista_de_resposta(res) -> list:
    """
    A API Pierre pode retornar dados em vários formatos:
    - Uma lista direta
    - Um dict com chave 'data' sendo lista
    - Um dict com chave 'data' sendo dict (objeto único)
    Retorna sempre uma lista.
    """
    if res is None:
        return []
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        if "error" in res:
            logger.warning(f"[PIERRE SYNC] Resposta de erro: {res.get('error')}")
            return []
        data = res.get("data") or res.get("purchases") or res.get("bills")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        # Pode ser o próprio objeto
        if "accountId" in res or "id" in res:
            return [res]
    return []


def _extrair_sumarios_fatura(res) -> list:
    """
    Parser específico para get-bill-summary que tem um formato único.
    Retorna lista de summaries normalizados.
    """
    if res is None:
        return []

    summaries = []

    if isinstance(res, list):
        summaries = res
    elif isinstance(res, dict):
        if "error" in res:
            logger.warning(f"[PIERRE SYNC] Erro em get-bill-summary: {res}")
            return []

        data = res.get("data")
        if isinstance(data, list):
            summaries = data
        elif isinstance(data, dict):
            summaries = [data]
        # Formato legado onde o próprio dict é o summary
        elif "accountId" in res:
            summaries = [res]
        elif "billAmount" in res:
            summaries = [res]

    logger.info(f"[PIERRE SYNC] Summaries de fatura encontrados: {len(summaries)}")
    return summaries


def _extrair_parcelamentos(res) -> list:
    """
    Parser específico para get-installments.
    O endpoint retorna { data: { purchases: [...], stats: {...} } } ou similar.
    """
    if res is None:
        return []

    if isinstance(res, list):
        return res

    if isinstance(res, dict):
        if "error" in res:
            logger.warning(f"[PIERRE SYNC] Erro em get-installments: {res}")
            return []

        # Formato real: { purchases: [...] }
        purchases = res.get("purchases")
        if isinstance(purchases, list):
            return purchases

        # Formato: { data: { purchases: [...] } }
        data = res.get("data")
        if isinstance(data, dict):
            purchases = data.get("purchases")
            if isinstance(purchases, list):
                return purchases
        elif isinstance(data, list):
            return data

    logger.warning(f"[PIERRE SYNC] Não foi possível extrair parcelamentos. Tipo: {type(res)}")
    return []


# ---------------------------------------------------------------------------
# Carga inicial
# ---------------------------------------------------------------------------

async def sincronizar_carga_inicial(usuario: Usuario, db: Session) -> dict:
    logger.info("🚀 [PIERRE SYNC] Iniciando carga inicial Open Finance")

    if not usuario.pierre_api_key:
        return {"error": "Sem chave API configurada"}

    client = PierreClient(usuario.pierre_api_key)

    # Força atualização dos dados nos bancos antes de buscar
    logger.info("[PIERRE SYNC] Solicitando atualização nos bancos...")
    client.manual_update()
    await asyncio.sleep(3)  # Aguarda propagação

    # ------------------------------------------------------------------
    # ETAPA 1: Upsert de Contas
    # ------------------------------------------------------------------
    logger.info("[PIERRE SYNC] Buscando contas...")
    res_accounts = client.get_accounts()
    accounts_raw = _extrair_lista_de_resposta(res_accounts)
    logger.info(f"[PIERRE SYNC] {len(accounts_raw)} conta(s) encontrada(s)")

    accounts_map: dict[str, int] = {}  # external_id → conta.id local
    contas_count = 0

    for acc in accounts_raw:
        ext_id = str(acc.get("id") or acc.get("accountId") or "")
        if not ext_id:
            continue

        p_type = acc.get("type", "BANK")
        tipo_local = {
            "CREDIT": "Cartão de Crédito",
            "INVESTMENT": "Investimento",
            "LOAN": "Empréstimo",
        }.get(p_type, "Conta Corrente")

        conta = (
            db.query(Conta)
            .filter(Conta.external_id == ext_id, Conta.id_usuario == usuario.id)
            .first()
        )
        if not conta:
            conta = Conta(id_usuario=usuario.id, external_id=ext_id)
            db.add(conta)
            contas_count += 1

        conta.nome = acc.get("name") or acc.get("displayName") or "Conta Open Finance"
        conta.tipo = tipo_local

        # Dados de cartão de crédito
        cc = acc.get("creditCard") or {}
        if cc:
            if cc.get("limit") is not None:
                conta.limite_cartao = _safe_decimal(cc["limit"])
            if cc.get("closingDay") is not None:
                conta.dia_fechamento = int(cc["closingDay"])
            if cc.get("dueDay") is not None:
                conta.dia_vencimento = int(cc["dueDay"])

        db.flush()
        accounts_map[ext_id] = conta.id

    logger.info(f"[PIERRE SYNC] Contas processadas: {contas_count} novas, {len(accounts_map)} total")

    # ------------------------------------------------------------------
    # ETAPA 2: Transações (últimos 90 dias)
    # ------------------------------------------------------------------
    date_90 = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%d')
    logger.info(f"[PIERRE SYNC] Buscando transações desde {date_90}...")

    res_txs = client.get_transactions(startDate=date_90, limit=1000, format="raw")
    txs_raw = _extrair_lista_de_resposta(res_txs)
    logger.info(f"[PIERRE SYNC] {len(txs_raw)} transação(ões) brutas recebidas")

    # Pré-carrega caches de categoria/subcategoria
    cat_cache: dict[str, int] = {c.nome: c.id for c in db.query(Categoria).all()}
    subcat_cache: dict[tuple, int] = {
        (s.id_categoria, s.nome): s.id for s in db.query(Subcategoria).all()
    }

    txs_count = 0
    txs_skip = 0

    for tx in txs_raw:
        ext_id = str(tx.get("id") or tx.get("transactionId") or "")
        if not ext_id:
            txs_skip += 1
            continue

        # Evita duplicatas
        if db.query(Lancamento).filter(Lancamento.external_id == ext_id).first():
            txs_skip += 1
            continue

        valor_bruto = _safe_decimal(tx.get("amount") or tx.get("value") or 0)
        acc_type = tx.get("accountType") or tx.get("type") or "BANK"
        descricao = (
            tx.get("description")
            or tx.get("name")
            or tx.get("memo")
            or "Transação"
        ).strip()

        # Inferir tipo com a lógica robusta
        tipo = _inferir_tipo(descricao, valor_bruto, acc_type)

        # Categorizar
        cat_id, subcat_id = categorizar_transacao(
            descricao, tipo, db, cat_cache, subcat_cache
        )

        # Data da transação
        data_tx = (
            _parse_iso_date(tx.get("date"))
            or _parse_iso_date(tx.get("createdAt"))
            or _parse_iso_date(tx.get("transactionDate"))
            or datetime.now(timezone.utc)
        )

        # Conta associada
        acc_id_tx = str(tx.get("accountId") or "")
        conta_id = accounts_map.get(acc_id_tx)

        db.add(Lancamento(
            id_usuario=usuario.id,
            id_conta=conta_id,
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
        txs_count += 1

        # Flush a cada 100 para não acumular memória
        if txs_count % 100 == 0:
            db.flush()
            logger.info(f"[PIERRE SYNC] {txs_count} transações processadas...")

    logger.info(f"[PIERRE SYNC] Transações: {txs_count} importadas, {txs_skip} ignoradas")

    # ------------------------------------------------------------------
    # ETAPA 3: Fatura Atual (bill-summary)
    # ------------------------------------------------------------------
    logger.info("[PIERRE SYNC] Buscando sumário de faturas...")
    res_summary = client.get_bill_summary()
    logger.error(f"🔍 [DEBUG FATURA] Resposta bruta: {str(res_summary)[:500]}")
    summaries = _extrair_sumarios_fatura(res_summary)

    faturas_count = 0
    for summary in summaries:
        acc_id = str(summary.get("accountId") or summary.get("account_id") or "")
        conta_id = accounts_map.get(acc_id)

        if not conta_id:
            logger.warning(f"[PIERRE SYNC] Fatura sem conta mapeada. accountId={acc_id}")
            continue

        # Cria ID único por conta + mês para upsert seguro
        agora = datetime.now()
        fake_ext_id = f"fatura_aberta_{acc_id}_{agora.year}_{agora.month:02d}"

        fatura = db.query(FaturaCartao).filter(FaturaCartao.external_id == fake_ext_id).first()
        if not fatura:
            fatura = FaturaCartao(
                id_usuario=usuario.id,
                id_conta=conta_id,
                external_id=fake_ext_id,
            )
            db.add(fatura)
            faturas_count += 1

        # Tenta vários campos possíveis para o valor
        valor_fatura = (
            summary.get("billAmount")
            or summary.get("amount")
            or summary.get("currentBillAmount")
            or summary.get("totalAmount")
            or 0
        )
        fatura.valor_total = _safe_decimal(valor_fatura)
        fatura.status = "em_aberto"

        # Data de vencimento
        data_venc_raw = (
            summary.get("dueDate")
            or summary.get("due_date")
            or summary.get("closeDate")
        )
        if data_venc_raw:
            dt = _parse_iso_date(str(data_venc_raw))
            if dt:
                fatura.data_vencimento = dt.date()

        logger.info(
            f"[PIERRE SYNC] Fatura {fake_ext_id}: R$ {fatura.valor_total} "
            f"| venc: {fatura.data_vencimento}"
        )

    logger.info(f"[PIERRE SYNC] Faturas: {faturas_count} salvas")

    # ------------------------------------------------------------------
    # ETAPA 4: Faturas Passadas (bills)
    # ------------------------------------------------------------------
    logger.info("[PIERRE SYNC] Buscando faturas passadas...")
    res_bills = client.get_bills()
    bills_raw = _extrair_lista_de_resposta(res_bills)

    faturas_passadas_count = 0
    for bill in bills_raw:
        ext_id = str(bill.get("id") or bill.get("billId") or "")
        if not ext_id:
            continue

        acc_id = str(bill.get("accountId") or "")
        conta_id = accounts_map.get(acc_id)
        if not conta_id:
            continue

        fatura = db.query(FaturaCartao).filter(FaturaCartao.external_id == ext_id).first()
        if not fatura:
            fatura = FaturaCartao(
                id_usuario=usuario.id,
                id_conta=conta_id,
                external_id=ext_id,
            )
            db.add(fatura)
            faturas_passadas_count += 1

        fatura.valor_total = _safe_decimal(
            bill.get("amount") or bill.get("totalAmount") or bill.get("value") or 0
        )
        fatura.status = bill.get("status") or "fechada"

        due_raw = bill.get("dueDate") or bill.get("due_date")
        if due_raw:
            dt = _parse_iso_date(str(due_raw))
            if dt:
                fatura.data_vencimento = dt.date()

    logger.info(f"[PIERRE SYNC] Faturas passadas: {faturas_passadas_count} salvas")

    # ------------------------------------------------------------------
    # ETAPA 5: Parcelamentos
    # ------------------------------------------------------------------
    logger.info("[PIERRE SYNC] Buscando parcelamentos...")
    res_inst = client.get_installments(start_date=date_90)
    logger.error(f"🔍 [DEBUG PARCELAS] Resposta bruta: {str(res_inst)[:500]}")
    inst_list = _extrair_parcelamentos(res_inst)
    logger.info(f"[PIERRE SYNC] {len(inst_list)} parcelamento(s) encontrado(s)")

    parcelas_count = 0
    for inst in inst_list:
        # Tenta vários campos de ID que o schema pode usar
        ext_id = str(
            inst.get("id")
            or inst.get("purchaseId")
            or inst.get("installmentId")
            or ""
        )
        if not ext_id or ext_id.lower() in ("none", "null"):
            continue

        parcela = db.query(ParcelamentoItem).filter(
            ParcelamentoItem.external_id == ext_id,
            ParcelamentoItem.id_usuario == usuario.id,
        ).first()
        if not parcela:
            parcela = ParcelamentoItem(id_usuario=usuario.id, external_id=ext_id)
            db.add(parcela)
            parcelas_count += 1

        acc_id = str(inst.get("accountId") or "")
        parcela.id_conta = accounts_map.get(acc_id)
        parcela.descricao = (
            inst.get("description")
            or inst.get("name")
            or inst.get("merchantName")
            or "Parcelamento"
        )

        v_total = _safe_decimal(inst.get("totalAmount") or inst.get("total") or 0)
        total_parc = max(1, int(inst.get("totalInstallments") or inst.get("installments") or 1))
        parcela.valor_total = v_total
        parcela.total_parcelas = total_parc
        parcela.valor_parcela = _safe_decimal(
            inst.get("installmentAmount")
            or inst.get("installmentValue")
            or (float(v_total) / total_parc if v_total else 0)
        )
        parcela.parcela_atual = int(
            inst.get("installmentNumber")
            or inst.get("installmentsPaid")
            or inst.get("currentInstallment")
            or 1
        )

        data_raw = (
            inst.get("purchaseDate")
            or inst.get("date")
            or inst.get("createdAt")
        )
        if data_raw:
            dt = _parse_iso_date(str(data_raw))
            if dt:
                parcela.data_compra = dt.date()

        logger.debug(
            f"[PIERRE SYNC] Parcela {ext_id}: {parcela.descricao} "
            f"| {parcela.parcela_atual}/{parcela.total_parcelas} "
            f"| R$ {parcela.valor_parcela}"
        )

    logger.info(f"[PIERRE SYNC] Parcelamentos: {parcelas_count} novos")

    # ------------------------------------------------------------------
    # Finalização
    # ------------------------------------------------------------------
    usuario.pierre_initial_sync_done = True
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        f"✅ [PIERRE SYNC] Carga concluída: "
        f"{contas_count} contas | {txs_count} transações | "
        f"{faturas_count + faturas_passadas_count} faturas | {parcelas_count} parcelas"
    )

    return {
        "contas": contas_count,
        "lancamentos": txs_count,
        "faturas": faturas_count + faturas_passadas_count,
        "parcelamentos": parcelas_count,
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

    res_txs = client.get_transactions(startDate=date_48h, limit=200, format="raw")
    txs_raw = _extrair_lista_de_resposta(res_txs)

    # Carrega contas para o mapeamento
    contas = db.query(Conta).filter(Conta.id_usuario == usuario.id).all()
    accounts_map = {str(c.external_id): c.id for c in contas if c.external_id}

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
        acc_type = tx.get("accountType") or "BANK"
        descricao = (tx.get("description") or tx.get("name") or "Transação").strip()

        tipo = _inferir_tipo(descricao, valor_bruto, acc_type)
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

    if novos:
        db.commit()
        logger.info(f"[PIERRE SYNC] Incremental: {novos} novas transações importadas")

    # Atualiza timestamp de última sync
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()

    return novos