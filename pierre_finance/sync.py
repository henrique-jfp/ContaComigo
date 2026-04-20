"""
Sincronização Open Finance — Pierre Finance
============================================
Motor de carga e atualização incremental de dados bancários.

Correções aplicadas v3:
- Prioridade de Merchant para cartões de crédito
- Captura de accountId aninhado
- Importação de faturas passadas (get_bills)
- Parser de parcelas corrigido para schema real
"""

import logging
import re
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from .client import PierreClient
from .enrichment import enriquecer_lancamentos_pendentes, enriquecer_um_lancamento
from finance_utils import normalize_financial_type
from models import (
    Usuario, Conta, Lancamento, SaldoConta,
    FaturaCartao, ParcelamentoItem, Categoria, Subcategoria,
    Agendamento, OrcamentoCategoria
)

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

_SINAIS_RECEITA_FORTE = {
    "salario", "salário", "pagamento salario", "pagamento salário",
    "pix recebido", "ted recebida", "ted recebido", "doc recebido",
    "transferencia recebida", "deposito recebido", "transf.recebida",
    "reembolso", "estorno", "devolucao", "devolução",
    "rendimento", "rendimentos", "juros recebidos", "pro-labore",
    "dividendo", "dividendos", "jcp", "venda", "resgate",
}

_SINAIS_DESPESA_FORTE = {
    "debito automatico", "débito automático",
    "debito em conta", "débito em conta",
    "pagamento fatura", "pagto fatura", "pgt fatura",
    "compra credito", "compra debito", "pix enviado",
    "transferencia enviada", "transf.enviada", "iof", "tarifa",
    "pag boleto", "pagamento boleto", "pgto boleto", "pagamento titulo",
    "pagto titulo", "pgto titulo", "liquidação boleto", "liquidacao boleto",
}

def _is_self_transfer(usuario_nome: str | None, contraparte_nome: str | None) -> bool:
    """Verifica se a contraparte parece ser o próprio usuário (mesma titularidade)."""
    if not usuario_nome or not contraparte_nome:
        return False
    
    u_parts = set(re.findall(r"\w+", usuario_nome.lower()))
    c_parts = set(re.findall(r"\w+", contraparte_nome.lower()))
    
    # Se o primeiro nome e pelo menos um sobrenome baterem (ou parte dele), é provável que seja self-transfer
    common = u_parts.intersection(c_parts)
    # Filtra conectores comuns
    common = {p for p in common if len(p) > 2}
    
    return len(common) >= 2 or (len(u_parts) == 1 and len(common) >= 1)

def _inferir_tipo(
    descricao: str,
    valor_bruto: Decimal,
    account_type: str,
    transaction_type: str | None = None,
    nome_contraparte: str | None = None,
    usuario_nome: str | None = None
) -> str:
    desc_norm = (descricao or "").lower()

    # 1. Checa auto-transferência (DESATIVADO: Usuário prefere ver como Receita/Despesa no Livro Único)
    # if _is_self_transfer(usuario_nome, nome_contraparte):
    #    return "Transferência"

    # 2. Checa sinais fortes de despesa (importante para boletos com sinal invertido)
    for sinal in _SINAIS_DESPESA_FORTE:
        if sinal in desc_norm:
            return "Despesa"

    # 3. Checa sinais fortes de receita
    for sinal in _SINAIS_RECEITA_FORTE:
        if sinal in desc_norm:
            return "Receita"

    tipo_tx_norm = normalize_financial_type(transaction_type, default="")
    if tipo_tx_norm in {"Receita", "Despesa", "Transferência"}:
        return tipo_tx_norm

    if account_type == "CREDIT":
        if valor_bruto < 0:
            return "Receita"
        return "Despesa"

    if valor_bruto < 0:
        return "Despesa"

    return "Receita"


def _extrair_nome_da_descricao(descricao: str) -> str | None:
    """Tenta extrair o nome da empresa/pessoa de descrições sujas do Open Finance."""
    if not descricao:
        return None
        
    desc = descricao.strip()
    
    patterns = [
        r"(?:Pix enviado|Pix recebido)\s*-\s*(.+)",
        r"TRANSFERENCIA PIX\s*-\s*[A-Z]{3}\s*(.+)",
        r"PAGTO ELETRON\s*COBRANCA\s*-\s*(.+?)\s*-",
        r"COMPRA NO CARTAO\s*-\s*(.+?)\s*(-|\d)",
        r"^(.+?)\s*(?:RIO DE JANEIR|SAO PAULO|BRA$|BRA\s)",
    ]
    
    for pat in patterns:
        match = re.search(pat, desc, re.IGNORECASE)
        if match:
            res = match.group(1).strip()
            res = re.split(r'\s+\d{2}/\d{2}', res)[0]
            res = re.split(r'\s+-', res)[0]
            return res.strip()
            
    return None


def _extrair_dados_contraparte(tx: dict) -> tuple[str | None, str | None]:
    """Extrai CNPJ/CPF e Nome da contraparte do payload da transação."""
    payment_data = tx.get("payment_data") or {}
    acc_type = tx.get("accountType", "")
    
    # Prioridade para Merchant em Cartão de Crédito
    if acc_type == "CREDIT":
        merchant = tx.get("merchant") or {}
        doc = merchant.get("documentNumber") or merchant.get("document")
        name = merchant.get("name")
        if name and name.lower() != "null":
            if doc:
                doc = "".join(filter(str.isdigit, str(doc)))
                if len(doc) not in [11, 14]: doc = None
            return doc, name

    # Fallback para receiver/payer (Pix/TED)
    receiver = payment_data.get("receiver") or {}
    doc = receiver.get("document")
    name = receiver.get("name")
    
    if not name or name.lower() == "null":
        payer = payment_data.get("payer") or {}
        if not doc: doc = payer.get("document")
        if not name: name = payer.get("name")

    if not name or name.lower() == "null":
        name = _extrair_nome_da_descricao(tx.get("description") or "")

    if doc:
        doc = "".join(filter(str.isdigit, str(doc)))
        if len(doc) not in [11, 14]: doc = None
            
    return doc, name


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
        p_subtype = acc.get("accountSubtype") or acc.get("subtype")
        
        if p_type == "CREDIT":
            conta.tipo = "Cartão de Crédito"
        elif p_type == "INVESTMENT":
            conta.tipo = "Investimento"
        elif p_type == "LOAN":
            conta.tipo = "Empréstimo"
        elif p_subtype == "SAVINGS_ACCOUNT":
            conta.tipo = "Conta Poupança"
        elif p_subtype == "CHECKING_ACCOUNT":
            conta.tipo = "Conta Corrente"
        elif p_subtype == "PAYMENT_ACCOUNT":
            conta.tipo = "Carteira Digital"
        else:
            conta.tipo = "Conta Corrente"

        # Campos específicos para Cartão de Crédito
        cc = acc.get("creditCard") or acc.get("creditData") or {}
        if cc:
            # Pierre usa 'creditLimit' ou 'limit'
            conta.limite_cartao = _safe_decimal(cc.get("creditLimit") or cc.get("limit"))
            # Fechamento e Vencimento
            conta.dia_fechamento = int(cc.get("closingDay") or 0) or conta.dia_fechamento
            conta.dia_vencimento = int(cc.get("dueDay") or cc.get("due_day") or 0) or conta.dia_vencimento

        db.flush()
        accounts_map[ext_id] = conta.id

        # Saldo Diário
        saldo_val = _safe_decimal(acc.get("balance"))
        # Para cartões, o Pierre manda saldo disponível em 'availableCreditLimit'
        saldo_disp = _safe_decimal(
            acc.get("availableBalance") or 
            cc.get("availableCreditLimit") or 
            acc.get("balance")
        )

        hoje = datetime.now(timezone.utc).date()
        saldo_existente = db.query(SaldoConta).filter(
            SaldoConta.id_conta == conta.id,
            func.date(SaldoConta.capturado_em) == hoje
        ).first()

        if saldo_existente:
            saldo_existente.saldo = saldo_val
            saldo_existente.saldo_disponivel = saldo_disp
            saldo_existente.capturado_em = datetime.now(timezone.utc)
        else:
            db.add(SaldoConta(
                id_usuario=usuario.id,
                id_conta=conta.id,
                saldo=saldo_val,
                saldo_disponivel=saldo_disp,
                capturado_em=datetime.now(timezone.utc)
            ))

    return accounts_map


def _upsert_bill_summaries(usuario: Usuario, db: Session, client: PierreClient, accounts_map: dict[str, int]) -> int:
    updated = 0
    try:
        # 1. Fatura Aberta/Atual
        res_current = client.get_bill_summary()
        current_bills = _extrair_sumarios_fatura(res_current)
        
        # 2. Faturas Fechadas/Passadas
        res_past = client.get_bills()
        past_bills = _extrair_sumarios_fatura(res_past)
        
        all_bills = current_bills + past_bills

        for s in all_bills:
            acc_id = str(s.get("accountId") or s.get("account_id") or "")
            conta_id = accounts_map.get(acc_id)
            if not conta_id:
                continue

            dv_raw = s.get("dueDate") or s.get("due_date")
            dv = _parse_iso_date(dv_raw)
            ref_date = dv or datetime.now(timezone.utc)
            
            fake_ext_id = f"bill_{acc_id}_{ref_date.year}_{ref_date.month:02d}"

            fatura = db.query(FaturaCartao).filter(
                FaturaCartao.external_id == fake_ext_id,
                FaturaCartao.id_usuario == usuario.id,
            ).first()
            if not fatura:
                fatura = FaturaCartao(id_usuario=usuario.id, id_conta=conta_id, external_id=fake_ext_id)
                db.add(fatura)

            fatura.valor_total = _safe_decimal(s.get("billAmount") or s.get("amount") or s.get("totalAmount") or 0)
            fatura.data_vencimento = ref_date.date()
            
            status_raw = str(s.get("status") or "").upper()
            hoje = datetime.now(timezone.utc).date()
            
            # Lógica de status aprimorada:
            # 1. Se o Pierre diz que tá pago/fechado, tá pago.
            if any(k in status_raw for k in ["PAID", "PAGO", "FECHADA", "CLOSED"]):
                fatura.status = "paga"
            # 2. Se o Pierre diz que tá em atraso, tá atrasada.
            elif any(k in status_raw for k in ["OVERDUE", "ATRASO"]):
                fatura.status = "atrasada"
            # 3. Se a fatura é antiga (> 15 dias do vencimento) e não tem status explícito de aberta, marca como paga (limpeza)
            elif fatura.data_vencimento < (hoje - timedelta(days=15)):
                fatura.status = "paga"
            # 4. Caso contrário, permanece em aberto
            else:
                fatura.status = "em_aberto"
                
            fatura.mes_referencia = ref_date.replace(day=1).date()

            df = _parse_iso_date(s.get("closeDate") or s.get("closing_date"))
            if df:
                fatura.data_fechamento = df.date()
            updated += 1
        return updated
    except Exception as e:
        logger.error(f"Erro em _upsert_bill_summaries: {e}")
        return 0


def _upsert_installments(usuario: Usuario, db: Session, client: PierreClient, accounts_map: dict[str, int]) -> int:
    try:
        res_inst = client.get_installments()
        # Schema Pierre: { "purchases": [ { "id", "description", "installments": [...] } ] }
        purchases = _extrair_parcelamentos(res_inst)
        logger.info(f"Sincronizando {len(purchases)} parcelamentos para usuário {usuario.id}")
        updated = 0

        for p in purchases:
            # Tenta ID explícito, senão gera um determinístico baseado em dados da compra
            p_id = str(p.get("id") or p.get("purchaseId") or "")
            p_desc = (p.get("description") or p.get("name") or "Compra Parcelada").strip()
            p_date = p.get("purchaseDate") or p.get("date") or ""
            p_acc_name = p.get("accountName") or ""
            
            if not p_id:
                # Gera um ID baseado na descrição, data e conta para ser estável
                import hashlib
                raw_id = f"{p_desc}_{p_date}_{p_acc_name}_{p.get('totalAmount')}"
                p_id = "gen_" + hashlib.md5(raw_id.encode()).hexdigest()[:12]

            p_acc_id = str(p.get("accountId") or p.get("account_id") or "")
            conta_id = accounts_map.get(p_acc_id)
            
            # Se não achou pelo ID, tenta pelo nome da conta como fallback
            if not conta_id and p_acc_name:
                c_fallback = db.query(Conta).filter(Conta.id_usuario == usuario.id, func.lower(Conta.nome) == p_acc_name.lower()).first()
                if c_fallback: conta_id = c_fallback.id
            installments = p.get("installments") or []
            if not installments:
                # Se não tem lista interna, tenta tratar o objeto raiz como uma parcela (legado)
                installments = [p]

            for inst in installments:
                # ID Único da Parcela: PurchaseID + Número da Parcela + Hash da descrição da parcela
                idx = inst.get("installmentNumber") or inst.get("currentInstallment") or 1
                inst_desc = (inst.get("description") or "").strip()
                
                import hashlib
                inst_hash = hashlib.md5(inst_desc.encode()).hexdigest()[:6]
                ext_id = f"inst_{p_id}_{idx}_{inst_hash}" if p_id else None
                
                if not ext_id: continue

                parcela = db.query(ParcelamentoItem).filter(
                    ParcelamentoItem.external_id == ext_id,
                    ParcelamentoItem.id_usuario == usuario.id,
                ).first()
                
                if not parcela:
                    parcela = ParcelamentoItem(id_usuario=usuario.id, external_id=ext_id)
                    db.add(parcela)

                parcela.id_conta = conta_id
                parcela.descricao = p_desc
                parcela.parcela_atual = int(idx)
                parcela.total_parcelas = int(p.get("totalInstallments") or p.get("installments") or idx)
                parcela.valor_total = _safe_decimal(p.get("totalAmount") or p.get("total") or 0)
                parcela.valor_parcela = _safe_decimal(inst.get("amount") or inst.get("installmentAmount") or 0)

                dp = _parse_iso_date(inst.get("dueDate") or inst.get("date"))
                if dp: parcela.data_proxima_parcela = dp.date()
                
                dc = _parse_iso_date(p.get("date") or p.get("purchaseDate"))
                if dc: parcela.data_compra = dc.date()
                
                updated += 1
        return updated
    except Exception as e:
        logger.error(f"Erro em _upsert_installments: {e}")
        return 0


def _sync_spending_limits(usuario: Usuario, db: Session, client: PierreClient):
    """Sincroniza os limites de gastos do Pierre com OrcamentoCategoria."""
    try:
        res = client.list_spending_limits()
        limits = _extrair_lista_de_resposta(res)
        
        for lim in limits:
            ext_id = str(lim.get("id") or "")
            if not ext_id: continue
            
            cat_name = lim.get("category")
            if not cat_name: continue

            # Busca categoria local para associar
            cat_db = db.query(Categoria).filter(func.lower(Categoria.nome) == func.lower(cat_name)).first()
            if not cat_db:
                cat_db = Categoria(nome=cat_name)
                db.add(cat_db)
                db.flush()
            
            orc = db.query(OrcamentoCategoria).filter(
                OrcamentoCategoria.external_id == ext_id,
                OrcamentoCategoria.id_usuario == usuario.id
            ).first()
            
            if not orc:
                orc = OrcamentoCategoria(id_usuario=usuario.id, external_id=ext_id)
                db.add(orc)
            
            orc.id_categoria = cat_db.id
            orc.valor_limite = _safe_decimal(lim.get("limitAmount") or lim.get("amount"))
            orc.periodo = lim.get("period", "monthly")
            orc.recorrente = bool(lim.get("isRecurring", True))
            orc.ativo = bool(lim.get("isActive", True))
            
    except Exception as e:
        logger.error(f"Erro ao sincronizar limites Pierre: {e}")


def _sync_payment_reminders(usuario: Usuario, db: Session, client: PierreClient):
    """Sincroniza os lembretes de pagamento do Pierre com Agendamento."""
    try:
        res = client.list_payment_reminders()
        reminders = _extrair_lista_de_resposta(res)
        
        for rem in reminders:
            ext_id = str(rem.get("id") or "")
            if not ext_id: continue
            
            agend = db.query(Agendamento).filter(
                Agendamento.external_id == ext_id,
                Agendamento.id_usuario == usuario.id
            ).first()
            
            if not agend:
                agend = Agendamento(id_usuario=usuario.id, external_id=ext_id, origem_externa="pierre")
                db.add(agend)
            
            agend.descricao = rem.get("title") or "Lembrete Pierre"
            agend.valor = _safe_decimal(rem.get("amount") or 0)
            agend.tipo = "Despesa"
            
            dv_raw = rem.get("dueDate")
            dv = _parse_iso_date(dv_raw)
            if dv:
                agend.proxima_data_execucao = dv.date()
                if not agend.data_primeiro_evento:
                    agend.data_primeiro_evento = dv.date()
            
            agend.frequencia = rem.get("recurrencePattern") or "Único"
            agend.status = rem.get("status", "active")
            agend.ativo = (agend.status == "active")
            
    except Exception as e:
        logger.error(f"Erro ao sincronizar lembretes Pierre: {e}")


def _enrich_user_profile(usuario: Usuario, client: PierreClient):
    """Enriquece o perfil IA do usuário com dados do Pierre get-book."""
    try:
        book_res = client.get_book(include_categories=True)
        if isinstance(book_res, dict):
            summary = book_res.get("summary") or book_res.get("data", {}).get("summary")
            if summary:
                usuario.perfil_ia = str(summary)
    except Exception as e:
        logger.warning(f"Erro ao enriquecer perfil IA via get-book: {e}")


def _extrair_lista_de_resposta(res) -> list:
    if res is None: return []
    if isinstance(res, list): return res
    if isinstance(res, dict):
        for key in ["data", "purchases", "bills", "accounts", "transactions"]:
            data = res.get(key)
            if isinstance(data, list): return data
            if isinstance(data, dict): return [data]
        if any(k in res for k in ["accountId", "id", "transactionId"]):
            return [res]
    return []


def _extrair_sumarios_fatura(res) -> list:
    if not res: return []
    if isinstance(res, dict):
        data = res.get("data") or res.get("bills") or res.get("summaries")
        if isinstance(data, list): return data
        if isinstance(data, dict):
            items = data.get("items") or data.get("bills") or data.get("summaries")
            if isinstance(items, list): return items
            return [data]
        if any(k in res for k in ["billAmount", "dueDate", "accountId"]):
            return [res]
    if isinstance(res, list): return res
    return []


def _extrair_parcelamentos(res) -> list:
    if not res: return []
    if isinstance(res, dict):
        data = res.get("data") or res.get("purchases") or res.get("installments")
        if isinstance(data, list): return data
        if isinstance(data, dict):
            items = data.get("purchases") or data.get("installments") or data.get("items")
            if isinstance(items, list): return items
            if any(k in data for k in ["purchaseId", "totalInstallments", "installmentAmount"]):
                return [data]
        if any(k in res for k in ["purchaseId", "totalInstallments", "description"]):
            return [res]
    if isinstance(res, list): return res
    return []


async def sincronizar_carga_inicial(usuario: Usuario, db: Session) -> dict:
    logger.info(f"🚀 [PIERRE SYNC] Iniciando carga inicial para {usuario.telegram_id}")
    if not usuario.pierre_api_key: return {"error": "Sem chave API configurada"}

    client = PierreClient(usuario.pierre_api_key)
    accounts_map = _upsert_accounts_and_balances(usuario, db, client)

    date_90 = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%d')
    res_txs = client.get_transactions(startDate=date_90, limit=1000, format="raw")
    txs_raw = _extrair_lista_de_resposta(res_txs)

    from gerente_financeiro.reconciliation_service import ReconciliationService
    
    txs_count = 0
    for tx in txs_raw:
        ext_id = str(tx.get("id") or tx.get("transactionId") or "")
        if not ext_id:
            continue

        valor_bruto = _safe_decimal(tx.get("amount") or tx.get("value"))
        acc_type = tx.get("accountType") or (tx.get("account") or {}).get("type") or "BANK"
        tx_type = tx.get("type") or tx.get("transactionType")
        descricao = (tx.get("description") or tx.get("name") or "Transação").strip()

        # Filtro Banco Inter - Crédito Liberado (Pix no Crédito)
        acc_name = (tx.get("account") or {}).get("name") or ""
        if "inter" in acc_name.lower() and "crédito liberado" in descricao.lower():
            logger.info(f"Ignorando lançamento Inter 'Crédito liberado': {ext_id}")
            continue

        cnpj, nome_fantasia = _extrair_dados_contraparte(tx)
        tipo = _inferir_tipo(descricao, valor_bruto, acc_type, tx_type, nome_contraparte=nome_fantasia, usuario_nome=usuario.nome_completo)

        # Converte para valor com sinal (Receita positiva, Despesa negativa) para o ReconciliationService
        valor_final = abs(float(valor_bruto)) if tipo == "Receita" else -abs(float(valor_bruto))
        data_tx = _parse_iso_date(tx.get("date")) or datetime.now(timezone.utc)

        # --- Lógica de Deduplicação e Categorização Inteligente (Livro Único) ---
        desc_norm = descricao.lower()
        contra_norm = (nome_fantasia or "").lower()
        u_nome_norm = (usuario.nome_completo or "").lower()
        is_transfer_logic = False
        cat_manual = None
        subcat_manual = None
        
        # 1. Detecção de Investimentos (Aplicações e Resgates)
        # Serão tratados como Despesa/Receita naturalmente para não sumir do fluxo de caixa.
        termos_investimento = ["aplicacao", "aplicação", "investimento", "resgate", "cdb", "cdi", "tesouro", "poupanca", "poupança", "fundo de inv"]
        if any(k in desc_norm for k in termos_investimento) or any(k in contra_norm for k in termos_investimento):
            cat_manual, subcat_manual = "Investimentos", "Aporte" if valor_final < 0 else "Resgate"

        # 2. Detecção de Pagamento de Fatura (A ÚNICA coisa que vira Transferência se for rastreada)
        termos_fatura = [
            "pagamento on line", "pagamento fatura", "pagamento de fatura", 
            "pagamento efetuado", "pagamento recebido", "pagto eletron", 
            "pag boleto bancario", "pagamento de titulo", "pagamento boleto", 
            "liquidacao boleto", "fatura paga"
        ]
        
        if any(k in desc_norm for k in termos_fatura):
            # Busca se o destino do pagamento é uma conta/cartão conhecido no sistema
            contas_rastreadas = db.query(Conta).filter(
                Conta.id_usuario == usuario.id,
                or_(Conta.external_id != None, Conta.tipo == "Cartão de Crédito")
            ).all()
            
            nomes_rastreados = [c.nome.lower() for c in contas_rastreadas]
            item_bank_name = (tx.get("item_bank_name") or "").lower()
            is_rastreada = False

            for nome in nomes_rastreados:
                if not nome: continue
                # Match por nome na descrição ou pelo banco fornecido pela API
                if nome in desc_norm or (nome_fantasia and nome in nome_fantasia.lower()) or \
                   (item_bank_name and (nome in item_bank_name or item_bank_name in nome or "inter" in item_bank_name and "inter" in nome)):
                    is_rastreada = True
                    break
            
            if is_rastreada:
                is_transfer_logic = True
                cat_manual, subcat_manual = "Cartão de Crédito", "Pagamento de Fatura"
                # Tenta marcar fatura como paga se for banco nacional
                if acc_type in ("BANK", "PAYMENT_ACCOUNT"):
                    try:
                        f_vencida = db.query(FaturaCartao).filter(
                            FaturaCartao.id_usuario == usuario.id,
                            FaturaCartao.status != "paga"
                        ).order_by(func.abs(FaturaCartao.data_vencimento - data_tx.date())).first()
                        if f_vencida:
                            f_vencida.status = "paga"
                            logger.info(f"Fatura {f_vencida.id} marcada como PAGA.")
                    except Exception: pass
            else:
                # Se não rastreou o cartão, vira despesa para o usuário não 'ganhar' dinheiro fantasma
                tipo = "Despesa"
                tipo = "Despesa"

        # REQUISITO CRÍTICO: Crédito em Cartão (Pagamento de Fatura)
        # Qualquer valor positivo entrando no cartão é um pagamento e NÃO pode ser Receita.
        if acc_type == "CREDIT" and valor_final > 0:
            is_transfer_logic = True
            cat_manual, subcat_manual = "Cartão de Crédito", "Pagamento de Fatura"

        # Finaliza o tipo se caiu em alguma regra de transferência
        if is_transfer_logic:
            tipo = "Transferência"

        # Registro via Serviço de Reconciliação (Com ID de Conta Correto)
        acc_id_ext = str(tx.get("accountId") or (tx.get("account") or {}).get("id") or "")
        conta_id_dest = accounts_map.get(acc_id_ext)

        lanc, criado = ReconciliationService.register_transaction(
            db=db,
            user_id=usuario.id,
            valor=valor_final,
            data=data_tx,
            descricao=descricao,
            origem="open_finance",
            external_id=ext_id,
            tipo=tipo,
            id_conta=conta_id_dest
        )

        # Só forçamos a categoria/tipo se for um lançamento NOVO
        if criado:
            if cat_manual and subcat_manual:
                from pierre_finance.categorizador import persistir_ids_categoria
                cid, sid = persistir_ids_categoria(db, cat_manual, subcat_manual)
                lanc.id_categoria = cid
                lanc.id_subcategoria = sid
            
            # Enriquecimento adicional
            lanc.cnpj_contraparte = cnpj
            lanc.nome_contraparte = nome_fantasia
            lanc.forma_pagamento = _normalizar_forma_pagamento(descricao, acc_type)
            # Tenta categorizar na hora
            await enriquecer_um_lancamento(db, lanc)
            txs_count += 1
        else:
            # Se já existia, mas não tinha external_id, o register_transaction já cuidou do commit.
            # EVITAMOS mudar o tipo (tipo=tipo) para não ocultar do dashboard o que o usuário já tinha.
            pass

    _upsert_bill_summaries(usuario, db, client, accounts_map)
    _upsert_installments(usuario, db, client, accounts_map)
    _enrich_user_profile(usuario, client)

    usuario.pierre_initial_sync_done = True
    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()

    try: await enriquecer_lancamentos_pendentes(db)
    except Exception as e: logger.error(f"Erro no enriquecimento: {e}")

    return {"status": "success", "lancamentos": txs_count, "contas": len(accounts_map)}


async def sincronizar_incremental(usuario: Usuario, db: Session) -> int:
    if not usuario.pierre_api_key: return 0
    if not usuario.pierre_initial_sync_done:
        res = await sincronizar_carga_inicial(usuario, db)
        return res.get("lancamentos", 0) if isinstance(res, dict) else 0

    client = PierreClient(usuario.pierre_api_key)
    date_168h = (datetime.now(timezone.utc) - timedelta(hours=168)).strftime('%Y-%m-%d')

    accounts_map = _upsert_accounts_and_balances(usuario, db, client)
    res_txs = client.get_transactions(startDate=date_168h, limit=200, format="raw")
    txs_raw = _extrair_lista_de_resposta(res_txs)

    from gerente_financeiro.reconciliation_service import ReconciliationService
    
    novos = 0
    for tx in txs_raw:
        ext_id = str(tx.get("id") or tx.get("transactionId") or "")
        if not ext_id:
            continue

        valor_bruto = _safe_decimal(tx.get("amount") or tx.get("value") or 0)
        acc_type = tx.get("accountType") or (tx.get("account") or {}).get("type") or "BANK"
        tx_type = tx.get("type") or tx.get("transactionType")
        descricao = (tx.get("description") or tx.get("name") or "Transação").strip()

        # Filtro Banco Inter - Crédito Liberado (Pix no Crédito)
        acc_name = (tx.get("account") or {}).get("name") or ""
        if "inter" in acc_name.lower() and "crédito liberado" in descricao.lower():
            logger.info(f"Ignorando lançamento Inter 'Crédito liberado': {ext_id}")
            continue

        cnpj, nome_fantasia = _extrair_dados_contraparte(tx)
        tipo = _inferir_tipo(descricao, valor_bruto, acc_type, tx_type, nome_contraparte=nome_fantasia, usuario_nome=usuario.nome_completo)

        # Converte para valor com sinal (Receita positiva, Despesa negativa)
        valor_final = abs(float(valor_bruto)) if tipo == "Receita" else -abs(float(valor_bruto))
        data_tx = _parse_iso_date(tx.get("date")) or _parse_iso_date(tx.get("createdAt")) or datetime.now(timezone.utc)

        # --- Lógica de Deduplicação e Categorização Inteligente (Livro Único) ---
        desc_norm = descricao.lower()
        contra_norm = (nome_fantasia or "").lower()
        u_nome_norm = (usuario.nome_completo or "").lower()
        is_transfer_logic = False
        cat_manual = None
        subcat_manual = None
        
        # 1. Detecção de Investimentos (Aplicações e Resgates)
        # Serão tratados como Despesa/Receita naturalmente para não sumir do fluxo de caixa.
        termos_investimento = ["aplicacao", "aplicação", "investimento", "resgate", "cdb", "cdi", "tesouro", "poupanca", "poupança", "fundo de inv"]
        if any(k in desc_norm for k in termos_investimento) or any(k in contra_norm for k in termos_investimento):
            cat_manual, subcat_manual = "Investimentos", "Aporte" if valor_final < 0 else "Resgate"

        # 2. Detecção de Pagamento de Fatura (A ÚNICA coisa que vira Transferência se for rastreada)
        termos_fatura = [
            "pagamento on line", "pagamento fatura", "pagamento de fatura", 
            "pagamento efetuado", "pagamento recebido", "pagto eletron", 
            "pag boleto bancario", "pagamento de titulo", "pagamento boleto", 
            "liquidacao boleto", "fatura paga"
        ]
        
        if any(k in desc_norm for k in termos_fatura):
            # Busca se o destino do pagamento é uma conta/cartão conhecido no sistema
            contas_rastreadas = db.query(Conta).filter(
                Conta.id_usuario == usuario.id,
                or_(Conta.external_id != None, Conta.tipo == "Cartão de Crédito")
            ).all()
            
            nomes_rastreados = [c.nome.lower() for c in contas_rastreadas]
            item_bank_name = (tx.get("item_bank_name") or "").lower()
            is_rastreada = False

            for nome in nomes_rastreados:
                if not nome: continue
                # Match por nome na descrição ou pelo banco fornecido pela API
                if nome in desc_norm or (nome_fantasia and nome in nome_fantasia.lower()) or \
                   (item_bank_name and (nome in item_bank_name or item_bank_name in nome or "inter" in item_bank_name and "inter" in nome)):
                    is_rastreada = True
                    break
            
            if is_rastreada:
                is_transfer_logic = True
                cat_manual, subcat_manual = "Cartão de Crédito", "Pagamento de Fatura"
                # Tenta marcar fatura como paga se for banco nacional
                if acc_type in ("BANK", "PAYMENT_ACCOUNT"):
                    try:
                        f_vencida = db.query(FaturaCartao).filter(
                            FaturaCartao.id_usuario == usuario.id,
                            FaturaCartao.status != "paga"
                        ).order_by(func.abs(FaturaCartao.data_vencimento - data_tx.date())).first()
                        if f_vencida:
                            f_vencida.status = "paga"
                            logger.info(f"Fatura {f_vencida.id} marcada como PAGA.")
                    except Exception: pass
            else:
                # Se não rastreou o cartão, vira despesa para o usuário não 'ganhar' dinheiro fantasma
                tipo = "Despesa"
                tipo = "Despesa"

        # REQUISITO CRÍTICO: Crédito em Cartão (Pagamento de Fatura)
        # Qualquer valor positivo entrando no cartão é um pagamento e NÃO pode ser Receita.
        if acc_type == "CREDIT" and valor_final > 0:
            is_transfer_logic = True
            cat_manual, subcat_manual = "Cartão de Crédito", "Pagamento de Fatura"

        # Finaliza o tipo se caiu em alguma regra de transferência
        if is_transfer_logic:
            tipo = "Transferência"

        # Registro via Serviço de Reconciliação (Com ID de Conta Correto)
        acc_id_ext = str(tx.get("accountId") or (tx.get("account") or {}).get("id") or "")
        conta_id_dest = accounts_map.get(acc_id_ext)

        lanc, criado = ReconciliationService.register_transaction(
            db=db,
            user_id=usuario.id,
            valor=valor_final,
            data=data_tx,
            descricao=descricao,
            origem="open_finance",
            external_id=ext_id,
            tipo=tipo,
            id_conta=conta_id_dest
        )

        # Só forçamos a categoria/tipo se for um lançamento NOVO
        if criado:
            if cat_manual and subcat_manual:
                from pierre_finance.categorizador import persistir_ids_categoria
                cid, sid = persistir_ids_categoria(db, cat_manual, subcat_manual)
                lanc.id_categoria = cid
                lanc.id_subcategoria = sid

            lanc.cnpj_contraparte = cnpj
            lanc.nome_contraparte = nome_fantasia
            lanc.forma_pagamento = _normalizar_forma_pagamento(descricao, acc_type)
            await enriquecer_um_lancamento(db, lanc)
            novos += 1
        else:
            # Se já existia, evitamos mudar o tipo para não ocultar do dashboard.
            pass

    faturas_atualizadas = _upsert_bill_summaries(usuario, db, client, accounts_map)
    parcelamentos_atualizados = _upsert_installments(usuario, db, client, accounts_map)
    _enrich_user_profile(usuario, client)

    usuario.last_pierre_sync_at = datetime.now(timezone.utc)
    db.commit()

    try: await enriquecer_lancamentos_pendentes(db)
    except Exception as e: logger.error(f"Erro no enriquecimento: {e}")

    return novos
