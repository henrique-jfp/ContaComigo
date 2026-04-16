#!/usr/bin/env python3
"""
Dashboard Web para Analytics do ContaComigo Bot
Interface web limpa para visualizar métricas e estatísticas
"""

import os
import sys
import logging
import json
import hmac
import hashlib
import base64
import asyncio
import re
import requests
from urllib.parse import parse_qsl
from functools import wraps
from sqlalchemy import and_, func, desc, or_, extract, case
from flask import Flask, render_template, jsonify, request, g, make_response
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta, date, timezone, time

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache simples em memória (para substituir Redis em ambiente local)
_cache = {}
CACHE_TTL = 300  # 5 minutos
_miniapp_sessions = {}
_miniapp_chat_context = {}
MINIAPP_SESSION_TTL = 30 * 24 * 60 * 60  # 30 dias de duração da sessão
MINIAPP_AI_INSIGHT_ENABLED = os.getenv("MINIAPP_AI_INSIGHT_ENABLED", "0").lower() in ("1", "true", "yes", "on")

def cache_key(*args):
    """Gera chave de cache baseada nos argumentos"""
    return "|".join(str(arg) for arg in args)

def cached(ttl=CACHE_TTL):
    """Decorator para cache de funções"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = cache_key(func.__name__, *args, *sorted(kwargs.items()))
            now = datetime.now().timestamp()
            
            # Verificar se há cache válido
            if key in _cache:
                cached_data, cached_time = _cache[key]
                if now - cached_time < ttl:
                    logger.debug(f"Cache hit: {func.__name__}")
                    return cached_data
            
            # Executar função e cachear resultado
            result = func(*args, **kwargs)
            _cache[key] = (result, now)
            logger.debug(f"Cache miss: {func.__name__}")
            return result
        return wrapper
    return decorator

# Configurar paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
template_dir = os.path.join(parent_dir, 'templates')
static_dir = os.path.join(parent_dir, 'static')
sys.path.insert(0, parent_dir)
import config
from database.database import get_db, buscar_lancamentos_usuario
from models import Usuario, Lancamento, Agendamento, Objetivo, MetaConfirmacao, Categoria, Subcategoria, XpEvent, UserMission, UserAchievement, OrcamentoCategoria, Conta, SaldoConta, FaturaCartao, ParcelamentoItem, Investment, CarteiraFII, HistoricoAlertaFII, PatrimonySnapshot, RegraCategorizacao
from pierre_finance.categorizador import limpar_descricao
from gerente_financeiro.prompts import PROMPT_ALFREDO_APRIMORADO as PROMPT_ALFREDO
from gerente_financeiro.services import preparar_contexto_financeiro_completo
from gerente_financeiro.services import salvar_transacoes_generica
from gerente_financeiro.services import limpar_cache_usuario
from gerente_financeiro.gamification_service import get_level_progress_payload, award_xp
from gerente_financeiro.gamification_missions_service import get_user_active_missions
from gerente_financeiro.fatura_draft_store import (
    get_fatura_draft,
    pop_fatura_draft,
    pop_pending_editor_token,
)
from pierre_finance.client import PierreClient
from finance_utils import is_expense_type
import google.generativeai as genai
from types import SimpleNamespace

# Criar app Flask
app = Flask(__name__, 
           template_folder=template_dir,
           static_folder=static_dir)

# Configurar analytics
analytics_available = False
is_render = bool(os.getenv('DATABASE_URL'))

if is_render:
    try:
        from analytics.bot_analytics_postgresql import get_analytics
        analytics = get_analytics()
        # Verificação simples se engine existe
        if getattr(analytics, 'engine', None):
            analytics_available = True
            logger.info("✅ Analytics PostgreSQL conectado (engine ok)")
        else:
            logger.warning("⚠️ Analytics PostgreSQL instanciado mas engine ausente")
    except ImportError as e:
        logger.warning(f"Analytics indisponível: {e}")
else:
    logger.info("Modo local - usando dados mock")

# --- CONFIGURAÇÃO E UTILITÁRIOS ---

@cached(ttl=60)  # Cache por 1 minuto
def get_fallback_data():
    """Retorna dados padrão para fallback (com cache)"""
    return {
        'total_users': 15,
        'total_commands': 127,
        'avg_response_time': 245.8,
        'error_count': 3,
        'status': 'fallback',
        'timestamp': datetime.now().isoformat()
    }

def execute_with_retry(func, max_retries=3):
    """Executa função com retry automático"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            logger.error(f"Tentativa {attempt + 1} falhou: {e}")
            if attempt == max_retries - 1:
                raise
    return None


def _validate_telegram_init_data(init_data: str) -> dict | None:
    if not init_data or not config.TELEGRAM_TOKEN:
        return None

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))

    # Telegram WebApp (Mini App) validation per official docs:
    # secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    webapp_secret_key = hmac.new(
        b"WebAppData",
        config.TELEGRAM_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
    webapp_hash = hmac.new(
        webapp_secret_key,
        data_check.encode(),
        hashlib.sha256,
    ).hexdigest()

    # Legacy fallback kept for compatibility with older flows.
    legacy_secret_key = hashlib.sha256(config.TELEGRAM_TOKEN.encode()).digest()
    legacy_hash = hmac.new(
        legacy_secret_key,
        data_check.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not (
        hmac.compare_digest(received_hash, webapp_hash)
        or hmac.compare_digest(received_hash, legacy_hash)
    ):
        return None

    try:
        auth_date = int(parsed.get("auth_date", "0"))
        if auth_date and (datetime.utcnow() - datetime.utcfromtimestamp(auth_date)).total_seconds() > 24 * 3600:
            return None
    except Exception:
        return None

    user_data = parsed.get("user")
    if not user_data:
        return None

    try:
        return json.loads(user_data)
    except json.JSONDecodeError:
        return None


def _resolve_categoria_ids(payload: dict) -> tuple[int | None, int | None]:
    id_categoria = payload.get("id_categoria")
    id_subcategoria = payload.get("id_subcategoria")

    try:
        id_categoria = int(id_categoria) if id_categoria not in (None, "") else None
    except (TypeError, ValueError):
        id_categoria = None
    try:
        id_subcategoria = int(id_subcategoria) if id_subcategoria not in (None, "") else None
    except (TypeError, ValueError):
        id_subcategoria = None

    if id_categoria is not None:
        return id_categoria, id_subcategoria

    categoria_nome = (payload.get("categoria_sugerida") or payload.get("categoria") or "").strip()
    subcategoria_nome = (payload.get("subcategoria_sugerida") or payload.get("subcategoria") or "").strip()
    if not categoria_nome:
        return None, None

    db = next(get_db())
    try:
        categoria_obj = db.query(Categoria).filter(func.lower(Categoria.nome) == categoria_nome.lower()).first()
        if not categoria_obj:
            return None, None

        id_categoria = categoria_obj.id
        if subcategoria_nome:
            sub_obj = db.query(Subcategoria).filter(
                Subcategoria.id_categoria == id_categoria,
                func.lower(Subcategoria.nome) == subcategoria_nome.lower(),
            ).first()
            if sub_obj:
                id_subcategoria = sub_obj.id
        return id_categoria, id_subcategoria
    finally:
        db.close()


def _create_miniapp_session(user_id: int) -> dict:
    expires_at = datetime.utcnow() + timedelta(seconds=MINIAPP_SESSION_TTL)
    expires_ts = int(expires_at.timestamp())

    # Stateless signed token avoids random 401s in multi-instance deployments.
    payload = f"{int(user_id)}|{expires_ts}"
    signature = hmac.new(_miniapp_session_secret(), payload.encode(), hashlib.sha256).hexdigest()
    token_bytes = f"{payload}|{signature}".encode()
    session_id = base64.urlsafe_b64encode(token_bytes).decode().rstrip("=")

    # Keep in-memory entry for backward compatibility with legacy sessions.
    _miniapp_sessions[session_id] = {
        "user_id": user_id,
        "expires_at": expires_at,
    }
    return {
        "session_id": session_id,
        "expires_in": MINIAPP_SESSION_TTL,
    }


def _miniapp_session_secret() -> bytes:
    raw = (
        os.getenv("MINIAPP_SESSION_SECRET")
        or config.TELEGRAM_TOKEN
        or os.getenv("SECRET_KEY")
        or "contacomigo-miniapp"
    )
    return hashlib.sha256(str(raw).encode()).digest()


def _get_session(session_id: str) -> dict | None:
    if not session_id:
        return None

    # Legacy in-memory session support.
    session = _miniapp_sessions.get(session_id)
    if session:
        if session["expires_at"] < datetime.utcnow():
            _miniapp_sessions.pop(session_id, None)
        else:
            return session

    # Stateless signed token support.
    try:
        padded = session_id + "=" * (-len(session_id) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        user_id_str, expires_ts_str, received_sig = raw.rsplit("|", 2)
    except Exception:
        return None

    payload = f"{user_id_str}|{expires_ts_str}"
    expected_sig = hmac.new(_miniapp_session_secret(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_sig, expected_sig):
        return None

    try:
        user_id = int(user_id_str)
        expires_ts = int(expires_ts_str)
    except (TypeError, ValueError):
        return None

    expires_at = datetime.utcfromtimestamp(expires_ts)
    if expires_at < datetime.utcnow():
        return None

    return {
        "user_id": user_id,
        "expires_at": expires_at,
    }


def _require_session() -> dict | None:
    session_id = request.headers.get("X-Session-Id") or request.args.get("session_id")
    session = _get_session(session_id)
    if session:
        session["session_id"] = session_id
    return session


def _miniapp_context_key(session: dict | None) -> str:
    if not session:
        return ""
    return str(session.get("session_id") or session.get("user_id") or "")


def _get_miniapp_contexto_conversa(session: dict | None) -> str:
    key = _miniapp_context_key(session)
    if not key:
        return ""
    history = _miniapp_chat_context.get(key, [])
    if not history:
        return ""
    lines = []
    for row in history[-5:]:
        lines.append(f"Usuario: {row.get('prompt', '')}")
        lines.append(f"Alfredo: {row.get('answer', '')}")
    return "\n".join(lines)


def _append_miniapp_contexto_conversa(session: dict | None, prompt: str, answer: str) -> None:
    key = _miniapp_context_key(session)
    if not key:
        return
    rows = _miniapp_chat_context.get(key, [])
    rows.append(
        {
            "prompt": (prompt or "").strip()[:400],
            "answer": (answer or "").strip()[:800],
            "created_at": datetime.utcnow(),
        }
    )
    if len(rows) > 10:
        rows = rows[-10:]
    _miniapp_chat_context[key] = rows


def _invalidate_financial_cache(telegram_id: int | None) -> None:
    if not telegram_id:
        return
    try:
        limpar_cache_usuario(int(telegram_id))
        # Limpar cache local do dashboard_app (ex: modo_deus)
        global _cache
        keys_to_del = [k for k in _cache.keys() if str(telegram_id) in str(k)]
        for k in keys_to_del:
            _cache.pop(k, None)
    except Exception:
        logger.debug("Falha ao invalidar cache financeiro do usuario %s", telegram_id, exc_info=True)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _normalize_forma_pagamento(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    mapa = {
        "pix": "Pix",
        "credito": "Crédito",
        "crédito": "Crédito",
        "debito": "Débito",
        "débito": "Débito",
        "boleto": "Boleto",
        "dinheiro": "Dinheiro",
        "nao informado": "Nao_informado",
        "não informado": "Nao_informado",
        "nao_informado": "Nao_informado",
        "n/a": "Nao_informado",
        "": "Nao_informado",
    }
    return mapa.get(raw, "Nao_informado")


def _month_bounds(reference: date | None = None) -> tuple[date, date]:
    ref = reference or datetime.utcnow().date()
    start = date(ref.year, ref.month, 1)
    if ref.month == 12:
        end = date(ref.year, 12, 31)
    else:
        end = date(ref.year, ref.month + 1, 1) - timedelta(days=1)
    return start, end


def _daily_cashflow(lancamentos: list[Lancamento], start: date, end: date) -> list[dict]:
    days = (end - start).days + 1
    labels = [(start + timedelta(days=i)).strftime("%d/%m") for i in range(days)]
    series = {label: {"Entrada": 0.0, "Saída": 0.0} for label in labels}

    for lanc in lancamentos:
        data = lanc.data_transacao.date() if isinstance(lanc.data_transacao, datetime) else lanc.data_transacao
        if not data or data < start or data > end:
            continue
        label = data.strftime("%d/%m")
        tipo = "Entrada" if str(lanc.tipo).lower().startswith(("entr", "recei")) else "Saída"
        series[label][tipo] += abs(float(lanc.valor or 0))

    return [
        {"label": label, "entrada": round(series[label]["Entrada"], 2), "saida": round(series[label]["Saída"], 2)}
        for label in labels
    ]


def _category_distribution(lancamentos: list[Lancamento]) -> list[dict]:
    totals: dict[str, float] = {}
    total_geral_gastos = 0.0
    
    for lanc in lancamentos:
        # Considera apenas gastos/saídas
        if str(lanc.tipo).lower().startswith(("entr", "recei")):
            continue
            
        valor = abs(float(lanc.valor or 0))
        total_geral_gastos += valor
        
        categoria = "Sem categoria"
        if getattr(lanc, "categoria", None) and lanc.categoria.nome:
            categoria = lanc.categoria.nome
            # Opcional: remover subcategoria do label do gráfico pizza para não poluir
            # if getattr(lanc, "subcategoria", None) and lanc.subcategoria.nome:
            #    categoria = f"{categoria} / {lanc.subcategoria.nome}"
        
        totals[categoria] = totals.get(categoria, 0.0) + valor

    if not totals:
        return []

    # Ordena por valor e pega as top 5
    ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    top = ordered[:5]
    
    total_mapeado = sum(value for _, value in top)
    restante = total_geral_gastos - total_mapeado
    
    if restante > 0.01:
        top.append(("Outros", restante))

    palette = ["#7b1e2d", "#b85d6e", "#16a34a", "#f59e0b", "#2563eb", "#8b5cf6"]
    return [
        {"label": label, "value": round(value, 2), "color": palette[i % len(palette)]}
        for i, (label, value) in enumerate(top)
    ]


def _build_miniapp_insight(usuario: Usuario, balance: float, receita: float, despesa: float, categories: list[dict], cashflow: list[dict]) -> str:
    if receita <= 0 and despesa <= 0:
        return "Comece registrando seus primeiros lançamentos. O Alfredo vai te mostrar os padrões assim que o fluxo começar."

    predominant = categories[0]["label"] if categories else None
    category_value = categories[0]["value"] if categories else 0
    ratio = (despesa / receita * 100) if receita > 0 else 0
    first = cashflow[0]["label"] if cashflow else ""
    last = cashflow[-1]["label"] if cashflow else ""

    prompt = (
        "Você é Alfredo, gerente financeiro. Gere 1 ou 2 frases curtas, objetivas e acolhedoras em português do Brasil, "
        "para um card de insights do miniapp. Não use listas. Não use markdown. "
        f"Saldo do mês: R$ {balance:.2f}. Receita: R$ {receita:.2f}. Despesa: R$ {despesa:.2f}. "
        f"Gasto principal: {predominant or 'N/A'} com R$ {category_value:.2f}. "
        f"Despesas representam {ratio:.1f}% da receita. "
        f"Primeiro dia do período: {first}. Último dia: {last}. "
        "Se houver economia, destaque isso. Se houver alerta, seja direto."
    )

    if MINIAPP_AI_INSIGHT_ENABLED:
        resposta = None
        if config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\"").strip())
                model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
                response = model.generate_content(prompt)
                resposta = _sanitize_response(response.text or "")
            except Exception as exc:
                logger.warning("Gemini falhou no insight do MiniApp: %s", exc, exc_info=True)

        if not resposta:
            resposta = _run_async(_generate_with_groq(prompt)) if config.GROQ_API_KEY else None
            if resposta:
                resposta = _sanitize_response(resposta)

        if resposta:
            return resposta

    if balance >= 0:
        return f"Você fechou o mês no azul com R$ {abs(balance):.2f}. O Alfredo está de olho para manter esse ritmo."
    return f"Cuidado: suas despesas já passaram as receitas em R$ {abs(balance):.2f}. Vale apertar os vilões do mês."


def _serialize_miniapp_lancamento(lanc: Lancamento) -> dict:
    origem_raw = str(lanc.origem or "").strip().lower()
    if origem_raw.startswith("audio"):
        origem_label = "Por voz"
    elif origem_raw.startswith("ocr"):
        origem_label = "OCR"
    elif origem_raw.startswith("fatura") or origem_raw.startswith("extrato"):
        origem_label = "Fatura"
    elif origem_raw in {"manual", "miniapp", "texto", "alfredo"}:
        origem_label = "Manual"
    else:
        origem_label = "Manual"

    return {
        "id": lanc.id,
        "descricao": lanc.descricao,
        "valor": abs(float(lanc.valor or 0)),
        "tipo": lanc.tipo,
        "data": lanc.data_transacao.isoformat() if lanc.data_transacao else None,
        "forma_pagamento": lanc.forma_pagamento,
        "origem": lanc.origem,
        "origem_label": origem_label,
        "id_categoria": lanc.id_categoria,
        "id_subcategoria": lanc.id_subcategoria,
        "categoria_nome": lanc.categoria.nome if lanc.categoria else None,
        "subcategoria_nome": lanc.subcategoria.nome if lanc.subcategoria else None,
    }


def _level_badge(level: int) -> str:
    level_num = int(level or 1)
    badges = {
        1: "📒 Caderneta Zerada",
        2: "📝 Anotador de Plantão",
        3: "🧮 Controlador de Gastos",
        4: "📊 Orçamentário Jr.",
        5: "🕵️ Caçador de Sobras",
        6: "🗂️ Arquivista do Real",
        7: "🔎 Analista de Bolso",
        8: "🎯 Planejador Ativo",
        9: "🌊 Mestre do Fluxo",
        10: "🛡️ Guardião do Patrimônio",
        11: "💼 CFO Pessoal",
        12: "🏗️ Arquiteto Financeiro",
        13: "🔮 Visionário de Mercado",
        14: "🧿 Oráculo do Budget",
        15: "🤖 Alfredo Humano",
        16: "🚀 Além do Budget",
    }
    if level_num > 16:
        return f"♾️ Além do Budget +{level_num - 16}"
    return badges.get(level_num, "📒 Caderneta Zerada")


_badge_svg_cache: dict[int, str] | None = None


def _load_badge_svgs() -> dict[int, str]:
    global _badge_svg_cache
    if _badge_svg_cache is not None:
        return _badge_svg_cache

    _badge_svg_cache = {}
    badge_file = os.path.join(parent_dir, 'xp_system', 'contacomigo_badges_16_niveis.html')
    if not os.path.exists(badge_file):
        return _badge_svg_cache

    try:
        with open(badge_file, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = re.compile(
            r'<div class="badge-wrap">\s*(<svg[\s\S]*?</svg>)[\s\S]*?<div class="badge-num">\s*N[íi]vel\s*([0-9]+)\+?\s*</div>',
            re.IGNORECASE,
        )
        for svg_markup, level_str in pattern.findall(content):
            _badge_svg_cache[int(level_str)] = svg_markup.strip()
    except Exception:
        logger.exception('Falha ao carregar SVGs de badge')

    return _badge_svg_cache


def _level_badge_svg(level: int) -> str | None:
    level_num = int(level or 1)
    badges = _load_badge_svgs()
    if not badges:
        return None
    if level_num > 16:
        level_num = 16
    return badges.get(level_num)


def _canonical_level_from_xp(total_xp: int) -> int:
    xp = int(total_xp or 0)
    milestones = [
        (1, 0),
        (2, 200),
        (3, 500),
        (4, 1000),
        (5, 2000),
        (6, 3500),
        (7, 5500),
        (8, 8000),
        (9, 12000),
        (10, 18000),
        (11, 25000),
        (12, 35000),
        (13, 50000),
        (14, 70000),
        (15, 95000),
        (16, 130000),
    ]
    level = 1
    for lvl, threshold in milestones:
        if xp >= threshold:
            level = lvl
    while level >= 16 and xp >= 130000 + (level - 16) * 35000:
        level += 1
    return level


def _friendly_feature_name(action: str | None) -> str:
    key = str(action or "").strip().upper()
    mapping = {
        "PRIMEIRA_INTERACAO_DIA": "Primeira interação do dia",
        "INTERACAO_BOT": "Uso do bot no chat",
        "CONVERSA_GERAL_BOT": "Uso do bot no chat",
        "MONTH_TURN_BLUE": "Mês fechado no azul",
        "LANCAMENTO_CRIADO": "Lançamentos realizados",
        "LANCAMENTO_MANUAL": "Lançamento via texto",
        "LANCAMENTO_CRIADO_TEXTO": "Lançamento via texto",
        "LANCAMENTO_AUDIO": "Lançamento via voz",
        "LANCAMENTO_CRIADO_VOZ": "Lançamento via voz",
        "LANCAMENTO_FOTO": "Lançamento via foto/OCR",
        "LANCAMENTO_CRIADO_OCR": "Lançamento via foto/OCR",
        "PDF_PROCESSADO": "Importação de fatura PDF",
        "LANCAMENTO_CRIADO_PDF": "Importação de fatura PDF",
        "TRANSACAO_EDITADA": "Edição de transação",
        "LANCAMENTO_EDITADO": "Edição de transação",
        "CONFIRMACAO_IA": "Confirmação de sugestão da IA",
        "META_CRIADA_FINANCEIRA": "Criação de meta financeira",
        "META_CRIADA": "Metas criadas",
        "META_CHECKIN_MENSAL": "Check-in de meta",
        "META_CHECKIN": "Check-in de metas",
        "META_CONCLUIDA_100": "Meta 100% atingida",
        "META_ATINGIDA": "Metas atingidas",
        "META_CONCLUIDA_ANTES_PRAZO": "Meta atingida antes do prazo",
        "META_ATINGIDA_ANTES_PRAZO": "Meta batida antes do prazo",
        "AGENDAMENTO_NOVO": "Criação de agendamento",
        "AGENDAMENTO_CRIADO": "Agendamentos criados",
        "DASHBOARD_VISUALIZADO": "Abertura do MiniApp",
        "INVESTIMENTO_ADICIONADO_MANUAL": "Adição de investimento",
        "OCR_PROCESSADO": "Leituras por OCR",
        "AUDIO_PROCESSADO": "Lançamentos por voz",
        "PERGUNTA_ALFREDO_IA": "Pergunta ao Alfredo",
        "PERGUNTA_ALFREDO": "Perguntas ao Alfredo",
        "RELATORIO_GERADO": "Relatórios gerados",
        "CONVITE_ACEITO": "Convites aceitos",
        "CONQUISTA_DESBLOQUEADA": "Conquistas desbloqueadas",
        "WRAPPED_ACESSADO": "Consulta de Wrapped",
        "WRAPPED_ANUAL": "Wrapped anual gerado",
    }
    if key in mapping:
        return mapping[key]

    cleaned = key.replace("_", " ").strip().lower()
    if not cleaned:
        return "Atividade no app"
    return cleaned.capitalize()


def _alfredo_profile_note(progress_pct: int, week_interactions: int, top_feature: str | None) -> str:
    if progress_pct >= 85:
        return "Você está no sprint final para subir de nível. Mais algumas ações estratégicas e você vira o jogo."
    if week_interactions >= 25:
        return "Ritmo excelente nesta semana. Continue repetindo sua feature forte para consolidar vantagem no ranking."
    if top_feature:
        return f"Seu ponto forte está em {top_feature}. Transforme isso em consistência diária e o level sobe rápido."
    return "Comece pelas features-chave (lançamentos, metas e IA) para acelerar sua progressão sem farm gratuito."


def _get_month_bounds(reference: date | None = None) -> tuple[datetime, datetime]:
    ref = reference or datetime.utcnow().date()
    start = datetime(ref.year, ref.month, 1)
    if ref.month == 12:
        end = datetime(ref.year, 12, 31, 23, 59, 59)
    else:
        end = datetime(ref.year, ref.month + 1, 1) - timedelta(seconds=1)
    return start, end


def _award_xp_from_miniapp(db, telegram_id: int, action: str) -> None:
    # Contexto mínimo para reaproveitar a regra central de XP sem quebrar no Flask.
    noop_bot = SimpleNamespace(send_message=lambda **kwargs: None, delete_message=lambda **kwargs: None)
    fake_context = SimpleNamespace(bot=noop_bot)
    try:
        _run_async(award_xp(db, telegram_id, action, fake_context))
    except Exception:
        # XP jamais deve quebrar o fluxo principal da API.
        logger.debug("Falha nao critica ao conceder XP no MiniApp", exc_info=True)


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    return asyncio.run(coro)


def _sanitize_response(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r'^```(html|json)?\n', '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'```$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'<!DOCTYPE[^>]*>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<html[^>]*>|</html>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<head[^>]*>.*?</head>', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'<body[^>]*>|</body>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def _groq_generate_content(prompt: str) -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    payload = {
        "model": config.GROQ_MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Você é Alfredo, gerente financeiro do ContaComigo. Responda em português do Brasil, com foco em finanças pessoais, de forma objetiva e simpática."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 1200,
    }
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


async def _generate_with_groq(prompt: str) -> str | None:
    if not config.GROQ_API_KEY:
        return None
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _groq_generate_content, prompt)
    except Exception as exc:
        logger.error("Falha ao processar chat do MiniApp com Groq: %s", exc, exc_info=True)
        return None


def _format_lancamentos_for_chat(lancamentos: list) -> str:
    if not lancamentos:
        return "Nao encontrei lancamentos com esses criterios."
    lines = ["<b>Seus lancamentos</b>"]
    for lanc in lancamentos:
        data = lanc.data_transacao.strftime('%d/%m/%Y')
        valor = float(lanc.valor)
        prefix = '-' if is_expense_type(lanc.tipo) else '+'
        lines.append(
            f"• {lanc.descricao} ({data}) <code>{prefix}R$ {abs(valor):.2f}</code>"
        )
    return "\n".join(lines)

# Middleware para timing de requisições
@app.before_request
def before_request():
    g.start_time = datetime.now()

@app.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        duration = (datetime.now() - g.start_time).total_seconds() * 1000
        response.headers['X-Response-Time'] = f"{duration:.2f}ms"
    return response

# --- ROTAS PRINCIPAIS ---

@app.route('/')
def dashboard():
    """Página principal do dashboard"""
    try:
        return render_template('dashboard_analytics_clean.html')
    except Exception as e:
        return f"""
        <h1>ERRO NO DASHBOARD</h1>
        <p>Erro: {str(e)}</p>
        <p>Template: {os.path.exists(os.path.join(template_dir, 'dashboard_analytics_clean.html'))}</p>
        """


@app.route('/webapp', strict_slashes=False)
def miniapp_shell():
    """Shell do miniapp Telegram"""
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "ContaComigoBot")
    response = make_response(render_template('miniapp.html', bot_username=bot_username, kpis={}))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/telegram/auth', methods=['POST'])
def telegram_auth():
    """Valida initData do Telegram Web App e cria uma sessao"""
    payload = request.get_json(silent=True) or {}
    init_data = payload.get("init_data") or ""
    user = _validate_telegram_init_data(init_data)
    if not user:
        return jsonify({"ok": False, "error": "invalid_init_data"}), 401

    db = next(get_db())
    has_pierre = False
    try:
        usuario_db = db.query(Usuario).filter(Usuario.telegram_id == user.get("id")).first()
        if usuario_db and usuario_db.pierre_api_key:
            has_pierre = True
    finally:
        db.close()

    session_data = _create_miniapp_session(user.get("id"))
    return jsonify({
        "ok": True,
        "user": {
            "id": user.get("id"),
            "first_name": user.get("first_name"),
            "username": user.get("username"),
            "has_pierre_access": has_pierre
        },
        **session_data,
    })


@app.route('/api/miniapp/pierre/health')
def pierre_health():
    """Busca o score de saúde financeira real via Pierre API."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario or not usuario.pierre_api_key:
            return jsonify({"ok": False, "error": "pierre_not_configured"}), 403

        client = PierreClient(usuario.pierre_api_key)
        # Assumindo que o PierreClient tem um método get_financial_health()
        health_data = client.get_financial_health() 
        
        if isinstance(health_data, dict) and health_data.get("success"):
            return jsonify({"ok": True, "data": health_data.get("data")})
        else:
            logger.error(f"Erro ao buscar saúde financeira Pierre para usuário {usuario.id}: {health_data}")
            return jsonify({"ok": False, "error": health_data.get("error", "Erro desconhecido ao buscar saúde financeira")}), 500
    except Exception as e:
        logger.error(f"Erro interno ao buscar saúde financeira Pierre para usuário {usuario.id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "internal_server_error"}), 500
    finally:
        db.close()

@app.route('/api/miniapp/pierre/projection')
def pierre_projection():
    """Calcula o total de compromissos financeiros projetados para o próximo mês via Pierre API."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario or not usuario.pierre_api_key:
            return jsonify({"ok": False, "error": "pierre_not_configured"}), 403

        client = PierreClient(usuario.pierre_api_key)
        
        # Obtém o primeiro dia do próximo mês
        hoje = datetime.now(timezone.utc)
        primeiro_dia_mes_atual = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        proximo_mes_inicio = primeiro_dia_mes_atual + timedelta(days=31) # Simplesmente avança 31 dias para pegar o início do próximo mês
        proximo_mes_inicio = proximo_mes_inicio.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Obtém parcelas a partir de amanhã até o fim do próximo mês
        # A lógica exata pode precisar de ajuste dependendo de como 'get_installments' lida com intervalos
        data_inicial_filtro = (hoje + timedelta(days=1)).strftime('%Y-%m-%d')
        data_final_filtro = (proximo_mes_inicio + timedelta(days=31)).replace(day=1) - timedelta(days=1) # Fim do próximo mês
        data_final_filtro_str = data_final_filtro.strftime('%Y-%m-%d')

        # Assume que get_installments retorna parcelas com 'dueDate' e 'amount'
        installments_data = client.get_installments(startDate=data_inicial_filtro, endDate=data_final_filtro_str)
        
        total_next_month_commitments = 0
        if isinstance(installments_data, dict) and installments_data.get("success"):
            for item in installments_data.get("purchases", []): # Assumindo que 'purchases' contém as parcelas
                due_date_str = item.get("dueDate")
                amount = float(item.get("amount", 0))

                if due_date_str:
                    try:
                        # Tenta parsear a data de vencimento
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                        # Verifica se a data de vencimento está dentro do próximo mês
                        if proximo_mes_inicio <= due_date < (proximo_mes_inicio + timedelta(days=31)).replace(day=1):
                            total_next_month_commitments += amount
                    except ValueError:
                        logger.warning(f"Data de vencimento inválida recebida do Pierre: {due_date_str}")
            
            return jsonify({"ok": True, "data": {"total_commitments_next_month": round(total_next_month_commitments, 2)}})
        else:
            logger.error(f"Erro ao buscar parcelamentos Pierre para usuário {usuario.id}: {installments_data}")
            return jsonify({"ok": False, "error": installments_data.get("error", "Erro desconhecido ao buscar parcelamentos")}), 500
    except Exception as e:
        logger.error(f"Erro interno ao calcular projeção Pierre para usuário {usuario.id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "internal_server_error"}), 500
    finally:
        db.close()

@app.route('/api/miniapp/pierre/connected-banks')
def pierre_connected_banks():
    """Lista bancos/instituições financeiras conectadas via Pierre."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario or not usuario.pierre_api_key:
            return jsonify({"ok": False, "error": "pierre_not_configured"}), 403

        client = PierreClient(usuario.pierre_api_key)
        accounts = client.get_accounts()
        logger.info(f"[Pierre] get_accounts() response: {accounts}")
        institutions = []
        if isinstance(accounts, list):
            for acc in accounts:
                if isinstance(acc, dict) and acc.get("id") and acc.get("name"):
                    institutions.append({
                        "id": acc.get("id"),
                        "name": acc.get("name", "Instituição Desconhecida"),
                        "type": acc.get("type", "BANK")
                    })
        elif isinstance(accounts, dict) and accounts.get("data") and isinstance(accounts["data"], list):
            for acc in accounts["data"]:
                if isinstance(acc, dict) and acc.get("id") and acc.get("name"):
                    institutions.append({
                        "id": acc.get("id"),
                        "name": acc.get("name", "Instituição Desconhecida"),
                        "type": acc.get("type", "BANK")
                    })
        else:
            logger.error(f"[Pierre] Formato de resposta inesperado ao buscar contas: {accounts}")
            return jsonify({"ok": False, "error": "unexpected_response_format", "raw": accounts}), 500

        return jsonify({"ok": True, "data": institutions})
    except Exception as e:
        logger.error(f"Erro ao buscar contas conectadas Pierre para usuário {usuario.id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "internal_server_error"}), 500
    finally:
        db.close()


@app.route('/api/miniapp/pierre/dashboard')
def miniapp_pierre_dashboard():
    """Endpoint agregado para o Modo Deus (Pierre Finance) lendo dados locais"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario or not usuario.pierre_api_key:
            return jsonify({"ok": False, "error": "pierre_not_configured"}), 403

        # 1. Buscar Contas e Saldos
        contas = db.query(Conta).filter(Conta.id_usuario == usuario.id).all()
        accounts_res = []
        total_balance = 0
        
        for c in contas:
            ultimo_saldo = db.query(SaldoConta).filter(SaldoConta.id_conta == c.id).order_by(SaldoConta.capturado_em.desc()).first()
            saldo_val = float(ultimo_saldo.saldo) if ultimo_saldo else 0
            
            display_info = None
            if c.tipo == "Cartão de Crédito":
                avail = float(ultimo_saldo.saldo_disponivel) if ultimo_saldo and ultimo_saldo.saldo_disponivel is not None else float(c.limite_cartao or 0)
                if avail:
                    display_info = f"Limite: R$ {avail:.2f}"
                else:
                    display_info = f"Fatura: R$ {saldo_val:.2f}"
            else:
                total_balance += saldo_val
                
            accounts_res.append({
                "id": c.external_id or str(c.id),
                "name": c.nome,
                "type": "CREDIT" if c.tipo == "Cartão de Crédito" else "BANK",
                "balance": saldo_val,
                "display_info": display_info
            })
            
        # 2. Buscar Categorias Caras (últimos 30 dias usando dados locais)
        trinta_dias_atras = datetime.now(timezone.utc) - timedelta(days=30)
        lancamentos_mes = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario.id,
            Lancamento.origem == 'open_finance',
            Lancamento.tipo.in_(['Saída', 'Despesa']),
            Lancamento.data_transacao >= trinta_dias_atras
        ).all()
        
        cleaned_categories = {}
        for l in lancamentos_mes:
            cat_name = l.categoria.nome if l.categoria else "Outros"
            cleaned_categories[cat_name] = cleaned_categories.get(cat_name, 0) + float(l.valor)
            
        cleaned_categories = dict(sorted(cleaned_categories.items(), key=lambda item: item[1], reverse=True)[:5])

        # 3. Buscar Parcelamentos (da tabela ParcelamentoItem)
        parcelas_db = db.query(ParcelamentoItem).filter(ParcelamentoItem.id_usuario == usuario.id).order_by(ParcelamentoItem.data_proxima_parcela.asc()).limit(15).all()
        installments_res = []
        for p in parcelas_db:
            installments_res.append({
                "id": p.external_id or str(p.id),
                "description": p.descricao,
                "amount": float(p.valor_parcela),
                "dueDate": p.data_proxima_parcela.isoformat() if p.data_proxima_parcela else None,
                "installmentNumber": p.parcela_atual,
                "totalInstallments": p.total_parcelas
            })

        # 4. Cálculo Dinâmico de Saúde
        total_expenses = sum(cleaned_categories.values())
        
        if total_balance < 100:
            health_score = 25
            health_label = "Crítico"
        elif total_balance < 1000:
            health_score = 50
            health_label = "Atenção"
        elif total_expenses > total_balance:
            health_score = 40
            health_label = "Risco"
        else:
            health_score = 90
            health_label = "Excelente"

        return jsonify({
            "ok": True,
            "data": {
                "balance": total_balance,
                "accounts": accounts_res,
                "categories": cleaned_categories,
                "installments": installments_res,
                "health": {"score": health_score, "label": health_label},
                "sync_time": usuario.last_pierre_sync_at.isoformat() if usuario.last_pierre_sync_at else datetime.now(timezone.utc).isoformat()
            }
        })
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard Pierre: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()


@app.route('/api/miniapp/pierre/sync', methods=['POST'])
def miniapp_pierre_sync():
    """Força a sincronização dos bancos via Pierre Finance"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario or not usuario.pierre_api_key:
            return jsonify({"ok": False, "error": "pierre_not_configured"}), 403

        from pierre_finance.ai_tools import executar_tool_pierre
        res = executar_tool_pierre("forcar_sincronizacao_bancaria", {}, usuario.pierre_api_key)
        return jsonify({"ok": True, "data": res})
    except Exception as e:
        logger.error(f"Erro ao sincronizar Pierre: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()


@app.route('/api/miniapp/pierre/parcelamentos')
def miniapp_pierre_parcelamentos():
    """Consulta parcelamentos locais sincronizados via Pierre Finance"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 403

        parcelas_db = db.query(ParcelamentoItem).filter(ParcelamentoItem.id_usuario == usuario.id).order_by(ParcelamentoItem.data_proxima_parcela.asc()).all()
        
        if not parcelas_db:
            return jsonify({"ok": True, "data": "Não encontrei compras parceladas registradas na base local."})
            
        text = "🗓️ <b>Radar de Parcelamentos:</b>\n\n"
        for p in parcelas_db[:15]:
            desc = p.descricao[:30]
            val = float(p.valor_parcela)
            date_str = p.data_proxima_parcela.strftime('%d/%m/%Y') if p.data_proxima_parcela else "S/D"
            inst_num = p.parcela_atual
            inst_tot = p.total_parcelas
            text += f"• {desc}\n  R$ {val:.2f} | Venc: {date_str} | Parc: {inst_num}/{inst_tot}\n\n"
            
        return jsonify({"ok": True, "data": text})
    except Exception as e:
        logger.error(f"Erro ao buscar parcelamentos locais: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()


@app.route('/api/miniapp/pierre/livro-caixa')
def miniapp_pierre_livro_caixa():
    """Gera dados para o livro caixa lendo transações locais e envia via Bot"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 403

        lancamentos = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario.id,
            Lancamento.origem == 'open_finance'
        ).order_by(Lancamento.data_transacao.desc()).limit(300).all()
        
        # Gerar PDF e enviar via Bot
        try:
            pdf_bytes = _generate_local_book_pdf(lancamentos)
            _send_telegram_document(
                usuario.telegram_id, 
                pdf_bytes, 
                f"Livro_Caixa_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf",
                "📄 Aqui está o seu <b>Livro Caixa Analítico</b> (Dados Locais Sincronizados)."
            )
            return jsonify({"ok": True})
        except Exception as pdf_err:
            logger.error(f"Erro ao gerar/enviar PDF Local: {pdf_err}")
            return jsonify({"ok": False, "error": "pdf_generation_failed"}), 500
            
    except Exception as e:
        logger.error(f"Erro ao gerar livro caixa local: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()

def _send_telegram_document(chat_id, document_bytes, filename, caption=""):
    """Envia um documento via API direta do Telegram."""
    if not config.TELEGRAM_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendDocument"
    files = {'document': (filename, document_bytes, 'application/pdf')}
    data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
    try:
        res = requests.post(url, data=data, files=files, timeout=30)
        return res.status_code == 200
    except Exception as e:
        logger.error(f"Erro ao enviar documento Telegram: {e}")
        return False

def _generate_local_book_pdf(lancamentos):
    """Gera um PDF simplificado com o Livro Caixa usando dados locais."""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    
    elements.append(Paragraph("Livro Caixa Analítico (ContaComigo)", styles['Title']))
    elements.append(Spacer(1, 12))
    
    if not lancamentos:
        elements.append(Paragraph("Nenhuma transação encontrada no histórico.", styles['Normal']))
    else:
        table_data = [["Data", "Descrição", "Valor", "Categoria"]]
        for l in lancamentos:
            cat_name = l.categoria.nome if l.categoria else "Outros"
            val_str = f"R$ {float(l.valor):.2f}"
            if is_expense_type(l.tipo):
                val_str = f"-{val_str}"
            table_data.append([
                l.data_transacao.strftime('%d/%m/%Y'),
                l.descricao[:40],
                val_str,
                cat_name
            ])
        
        t = Table(table_data, colWidths=[80, 200, 80, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


@app.route('/api/miniapp/history')
def miniapp_history():
    """Lista os ultimos lancamentos para o miniapp"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    limit = min(int(request.args.get("limit", 20)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    query = (request.args.get("query") or "").strip()
    tipo = (request.args.get("tipo") or "").strip()
    order = (request.args.get("order") or "date_desc").strip().lower()
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        base_query = db.query(Lancamento).filter(Lancamento.id_usuario == usuario.id)
        if query:
            base_query = base_query.filter(Lancamento.descricao.ilike(f"%{query}%"))
        if tipo:
            tipo_norm = tipo.strip().lower()
            if tipo_norm in {"entrada", "receita"}:
                base_query = base_query.filter(func.lower(Lancamento.tipo).in_(["entrada", "receita"]))
            elif tipo_norm in {"saída", "saida", "despesa"}:
                base_query = base_query.filter(func.lower(Lancamento.tipo).in_(["saída", "saida", "despesa"]))
            else:
                base_query = base_query.filter(Lancamento.tipo == tipo)
        if start_date:
            base_query = base_query.filter(Lancamento.data_transacao >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            base_query = base_query.filter(Lancamento.data_transacao <= datetime.combine(end_date, datetime.max.time()))

        # O frontend nao usa o total atualmente; remover count evita query pesada em bases grandes.
        total = None
        base_query = base_query.options(
            joinedload(Lancamento.categoria),
            joinedload(Lancamento.subcategoria),
        )

        # Ordem padrao: data da transação decrescente (mais recente primeiro)
        if order == "date_asc":
            base_query = base_query.order_by(Lancamento.data_transacao.asc(), Lancamento.id.asc())
        else:
            # Padrão agora é date_desc
            base_query = base_query.order_by(Lancamento.data_transacao.desc(), Lancamento.id.desc())

        lancamentos = base_query.offset(offset).limit(limit).all()

        itens = [_serialize_miniapp_lancamento(lanc) for lanc in lancamentos]

        return jsonify({"ok": True, "items": itens, "total": total, "offset": offset})
    finally:
        db.close()


@app.route('/api/miniapp/modo_deus')
def miniapp_modo_deus():
    """Aba Modo Deus - Painel CFO Pessoal consolidado."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    user_id_telegram = session["user_id"]
    
    # Cache manual de 60 segundos para maior precisão em tempo real
    cache_key_val = f"modo_deus_{user_id_telegram}"
    now_ts = datetime.now().timestamp()
    if cache_key_val in _cache:
        cached_val, ts = _cache[cache_key_val]
        if now_ts - ts < 60:
            return jsonify(cached_val)

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id_telegram).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404
        
        user_id = usuario.id
        today = datetime.now(timezone.utc).date()
        start_month = today.replace(day=1)
        next_month = (start_month + timedelta(days=32)).replace(day=1)
        end_month = next_month - timedelta(days=1)
        
        result = {}
        
        # --- SEÇÃO 1: VISÃO GERAL (Cálculo Dinâmico e Tempo Real) ---
        try:
            # 1. Busca todas as contas do usuário
            contas = db.query(Conta).filter(Conta.id_usuario == user_id).all()
            total_patrimonio_contas = 0.0
            saldo_disponivel = 0.0
            divida_cartoes = 0.0
            
            min_date_aware = datetime(1970, 1, 1, tzinfo=timezone.utc)

            for c in contas:
                ultimo_snapshot = db.query(SaldoConta).filter(
                    SaldoConta.id_conta == c.id
                ).order_by(SaldoConta.capturado_em.desc()).first()
                
                base_balance = float(ultimo_snapshot.saldo or 0) if ultimo_snapshot else 0.0
                since_date = ultimo_snapshot.capturado_em if ultimo_snapshot else min_date_aware
                
                var_receitas = db.query(func.sum(Lancamento.valor)).filter(
                    Lancamento.id_conta == c.id,
                    Lancamento.tipo.in_(['Entrada', 'Receita']),
                    Lancamento.data_transacao > since_date
                ).scalar() or 0
                
                var_despesas = db.query(func.sum(Lancamento.valor)).filter(
                    Lancamento.id_conta == c.id,
                    Lancamento.tipo.in_(['Saída', 'Despesa']),
                    Lancamento.data_transacao > since_date
                ).scalar() or 0
                
                current_acc_balance = base_balance + float(var_receitas) - float(var_despesas)
                
                if c.tipo == "Cartão de Crédito":
                    divida_cartoes += abs(current_acc_balance)
                    total_patrimonio_contas -= abs(current_acc_balance)
                else:
                    total_patrimonio_contas += current_acc_balance
                    if c.tipo in ["Conta Corrente", "Carteira Digital", "Conta Poupança"]:
                        saldo_disponivel += max(0, current_acc_balance)

            # Investimentos e FIIs (Apenas Ativos)
            investments_total = db.query(func.sum(Investment.valor_atual)).filter(
                Investment.id_usuario == user_id, Investment.ativo == True
            ).scalar() or 0
            
            fiis_total = db.query(func.sum(CarteiraFII.quantidade_cotas * CarteiraFII.preco_medio)).filter(
                CarteiraFII.id_usuario == user_id, CarteiraFII.ativo == True
            ).scalar() or 0
            
            patrimonio_liquido = float(total_patrimonio_contas) + float(investments_total) + float(fiis_total)
            
            # Fluxo de Caixa Mensal
            entradas_mes = db.query(func.sum(Lancamento.valor)).filter(
                Lancamento.id_usuario == user_id,
                Lancamento.tipo.in_(['Entrada', 'Receita']),
                Lancamento.data_transacao >= datetime.combine(start_month, time.min),
                Lancamento.data_transacao <= datetime.combine(end_month, time.max)
            ).scalar() or 0
            
            # --- LÓGICA DE DUPLICIDADE (Filtro Inteligente) ---
            # Pegamos os nomes dos cartões sincronizados (Open Finance)
            contas_cartao_sync = [c.nome.lower() for c in contas if c.tipo == "Cartão de Crédito" and c.external_id]
            
            # Buscamos todos os lançamentos de saída do mês para processamento granular
            lancamentos_saida_mes = db.query(Lancamento).options(
                joinedload(Lancamento.categoria),
                joinedload(Lancamento.subcategoria)
            ).filter(
                Lancamento.id_usuario == user_id,
                Lancamento.tipo.in_(['Saída', 'Despesa']),
                Lancamento.data_transacao >= datetime.combine(start_month, time.min),
                Lancamento.data_transacao <= datetime.combine(end_month, time.max)
            ).all()

            saidas_mes_real = 0.0
            for lanc in lancamentos_saida_mes:
                cat_nome = (lanc.categoria.nome if lanc.categoria else "").lower()
                sub_nome = (lanc.subcategoria.nome if lanc.subcategoria else "").lower()
                desc_lower = (lanc.descricao or "").lower()
                contra_lower = (lanc.nome_contraparte or "").lower()

                # 1. Regra de Ouro: Pagamento de fatura de cartão SINCRONIZADO não é despesa nova
                if "fatura" in sub_nome or cat_nome == "cartão de crédito":
                    # Se houver match com algum cartão sync, ignoramos na soma de despesas
                    if any(nome_card in desc_lower or nome_card in contra_lower for nome_card in contas_cartao_sync):
                        continue
                
                # 2. Transferência Interna: Também ignoramos se for explicitamente marcada
                if sub_nome == "transferência interna":
                    continue
                
                saidas_mes_real += abs(float(lanc.valor))
            
            saidas_mes = saidas_mes_real
            resultado_mes = float(entradas_mes) - abs(float(saidas_mes))
            
            # Limite Diário Seguro (Baseado na sobra projetada se o saldo for positivo)
            dias_restantes = (end_month - today).days + 1
            if dias_restantes > 0:
                # Se já gastou mais do que ganhou, o limite é zero ou mínimo
                limite_diario = max(0, (saldo_disponivel + resultado_mes) / dias_restantes) if (saldo_disponivel + resultado_mes) > 0 else 0
            else:
                limite_diario = 0
            
            result['visao_geral'] = {
                "patrimonio_liquido": patrimonio_liquido,
                "saldo_disponivel": saldo_disponivel,
                "resultado_mes": resultado_mes,
                "entradas_mes": float(entradas_mes),
                "saidas_mes": abs(float(saidas_mes)),
                "dias_restantes_mes": dias_restantes,
                "limite_diario_seguro": limite_diario,
                "divida_cartoes": divida_cartoes,
                "variacao_patrimonio_pct": 0.0  # TODO: Implementar cálculo real
            }
        except Exception as e:
            logger.error(f"Erro Modo Deus (visao_geral): {e}")
            result['visao_geral'] = {}

        # --- SEÇÃO 2: TOP CATEGORIAS ---
        try:
            # Usamos a soma calculada acima para manter a consistência
            total_gastos_real = saidas_mes 

            # Para o gráfico, agrupamos e aplicamos o mesmo filtro inteligente
            cat_totals = {}
            for lanc in lancamentos_saida_mes:
                cat_nome_display = (lanc.categoria.nome if lanc.categoria else "Outros")
                cat_nome_lower = cat_nome_display.lower()
                sub_nome = (lanc.subcategoria.nome if lanc.subcategoria else "").lower()
                desc_lower = (lanc.descricao or "").lower()
                contra_lower = (lanc.nome_contraparte or "").lower()

                # Aplicar filtro de duplicidade (Faturas Sync e Transf Interna)
                if "fatura" in sub_nome or cat_nome_lower == "cartão de crédito":
                    if any(nome_card in desc_lower or nome_card in contra_lower for nome_card in contas_cartao_sync):
                        continue
                if sub_nome == "transferência interna":
                    continue
                
                cat_totals[cat_nome_display] = cat_totals.get(cat_nome_display, 0.0) + abs(float(lanc.valor))

            top_cats_data = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:6]
            
            top_categorias_list = []
            colors = ["#D85A30","#378ADD","#7F77DD","#888780","#1D9E75","#BA7517"]
            total_mapeado = 0
            for i, (cat_name, total_cat) in enumerate(top_cats_data):
                v_cat = abs(float(total_cat))
                if v_cat < 0.01: continue
                total_mapeado += v_cat
                
                # Buscar subcategorias para este gráfico também com filtro
                sub_totals = {}
                for lanc in lancamentos_saida_mes:
                    if lanc.categoria and lanc.categoria.nome == cat_name:
                        sub_n = (lanc.subcategoria.nome if lanc.subcategoria else "Geral")
                        sub_n_lower = sub_n.lower()
                        d_l = (lanc.descricao or "").lower()
                        c_l = (lanc.nome_contraparte or "").lower()
                        
                        # Filtro nas subs também
                        if "fatura" in sub_n_lower or cat_name.lower() == "cartão de crédito":
                            if any(nc in d_l or nc in c_l for nc in contas_cartao_sync):
                                continue
                        if sub_n_lower == "transferência interna":
                            continue
                            
                        sub_totals[sub_n] = sub_totals.get(sub_n, 0.0) + abs(float(lanc.valor))
                
                top_sub_list = []
                for sn, sv in sorted(sub_totals.items(), key=lambda x: x[1], reverse=True):
                    top_sub_list.append({"nome": sn, "total": sv})

                top_categorias_list.append({
                    "nome": cat_name,
                    "total": v_cat,
                    "percentual_do_total_gastos": (v_cat / total_gastos_real * 100) if total_gastos_real > 0 else 0,
                    "cor_hex": colors[i % len(colors)],
                    "subcategorias": top_sub_list
                })
            
            restante = total_gastos_real - total_mapeado
            if restante > 0.01:
                top_categorias_list.append({
                    "nome": "Outros",
                    "total": restante,
                    "percentual_do_total_gastos": (restante / total_gastos_real * 100) if total_gastos_real > 0 else 0,
                    "cor_hex": "#94a3b8",
                    "subcategorias": [{"nome": "Diversos", "total": restante}]
                })
            result['top_categorias'] = top_categorias_list
        except Exception as e:
            logger.error(f"Erro Modo Deus (top_categorias): {e}")
            result['top_categorias'] = []

        # --- SEÇÃO 3: ASSINATURAS ---
        try:
            servicos_assinatura = [
                'netflix', 'spotify', 'amazon', 'disney', 'hbo', 'globoplay', 'youtube',
                'deezer', 'apple', 'crunchyroll', 'paramount', 'claro', 'vivo', 'tim',
                'oi', 'net', 'sky', 'starlink', 'gympass', 'totalpass', 'wellhub',
                'chatgpt', 'openai', 'google one', 'icloud', 'dropbox', 'microsoft 365',
                'adobe', 'prime video', 'amazon prime', 'youtube premium', 'academia', 'smartfit', 'bluefit'
            ]
            termos_recorrentes = ['assinatura', 'subscription', 'plano mensal', 'mensalidade', 'recorrente']
            termos_excluir = ['juros', 'multa', 'encargo', 'iof', 'rotativo', 'pix enviado', 'pix recebido', 'bar ', 'lanchonete', 'restaurante', 'uber', '99app', '99food', 'ifood', 'rappi', 'ecovias', 'ponte', 'seguro cartão', 'seguro cartao']
            
            regex_servicos = '|'.join(servicos_assinatura)
            regex_recorrentes = '|'.join(termos_recorrentes)
            regex_excluir = '|'.join(termos_excluir)
            
            start_assinaturas = datetime.combine(today - timedelta(days=90), time.min)
            cat_ass_ids = [r[0] for r in db.query(Categoria.id).filter(or_(func.lower(Categoria.nome).like('%assinatura%'), func.lower(Categoria.nome).like('%serviços e assinaturas%'))).all()]
            
            lanc_ass = db.query(Lancamento).filter(
                Lancamento.id_usuario == user_id, Lancamento.tipo.in_(['Saída', 'Despesa']),
                Lancamento.data_transacao >= start_assinaturas,
                or_(Lancamento.id_categoria.in_(cat_ass_ids), func.lower(Lancamento.descricao).op('~')(regex_servicos), func.lower(Lancamento.descricao).op('~')(regex_recorrentes)),
                func.lower(Lancamento.descricao).op('!~')(regex_excluir)
            ).all()

            agend_ass = db.query(Agendamento).filter(Agendamento.id_usuario == user_id, Agendamento.ativo == True, Agendamento.frequencia == 'mensal', func.lower(Agendamento.descricao).op('!~')(regex_excluir)).all()            
            
            from pierre_finance.categorizador import limpar_descricao
            lista_ass = []
            seen = set()
            for l in lanc_ass:
                nome_base = limpar_descricao(l.descricao or "").split()[0].lower()
                if nome_base and nome_base not in seen:
                    lista_ass.append({"descricao": l.descricao, "valor": abs(float(l.valor)), "proxima_data": None})
                    seen.add(nome_base)
            for a in agend_ass:
                nome_base = limpar_descricao(a.descricao or "").split()[0].lower()
                if nome_base and nome_base not in seen:
                    lista_ass.append({"descricao": a.descricao, "valor": float(a.valor), "proxima_data": a.proxima_data_execucao.isoformat() if a.proxima_data_execucao else None})
                    seen.add(nome_base)
            
            lista_ass.sort(key=lambda x: x['valor'], reverse=True)
            result['assinaturas'] = {"lista": lista_ass, "total_mensal": sum(x['valor'] for x in lista_ass)}
        except Exception as e:
            logger.error(f"Erro Modo Deus (assinaturas): {e}")
            result['assinaturas'] = {"lista": [], "total_mensal": 0}

        # --- SEÇÃO 4: PARCELAMENTOS ---
        try:
            parcelas = db.query(ParcelamentoItem).filter(
                ParcelamentoItem.id_usuario == user_id,
                or_(ParcelamentoItem.data_proxima_parcela.is_(None), ParcelamentoItem.data_proxima_parcela >= (today - timedelta(days=5)))
            ).order_by(ParcelamentoItem.data_proxima_parcela.asc()).limit(10).all()
            
            lista_p = [{"descricao": p.descricao, "valor_parcela": float(p.valor_parcela), "parcela_atual": p.parcela_atual, "total_parcelas": p.total_parcelas, "data_proxima_parcela": p.data_proxima_parcela.isoformat() if p.data_proxima_parcela else None, "percentual_concluido": (p.parcela_atual / p.total_parcelas * 100) if p.total_parcelas > 0 else 0} for p in parcelas]
            result['parcelamentos'] = {"lista": lista_p, "total_mensal_parcelas": sum(float(p.valor_parcela) for p in parcelas)}
        except Exception as e:
            logger.error(f"Erro Modo Deus (parcelamentos): {e}")
            result['parcelamentos'] = {"lista": [], "total_mensal_parcelas": 0}

        # --- SEÇÃO 5: CARTÕES ---
        try:
            v_limit_cards = today + timedelta(days=45)
            faturas = db.query(FaturaCartao).join(Conta).filter(
                FaturaCartao.id_usuario == user_id,
                or_(FaturaCartao.status.in_(['em_aberto', 'aberta', 'aberto', 'PENDING']), and_(FaturaCartao.data_vencimento >= (today - timedelta(days=2)), FaturaCartao.data_vencimento <= v_limit_cards))
            ).order_by(FaturaCartao.data_vencimento.asc()).all()
            
            colors_c = ["#534AB7","#378ADD","#1D9E75","#D85A30"]
            lista_c = []
            seen_accounts = set()
            for i, f in enumerate(faturas):
                if f.id_conta in seen_accounts: continue
                seen_accounts.add(f.id_conta)
                limite = float(f.conta.limite_cartao or 0)
                lista_c.append({
                    "nome_conta": f.conta.nome, "valor_total": float(f.valor_total),
                    "data_vencimento": f.data_vencimento.isoformat() if f.data_vencimento else None,
                    "status": f.status, "limite_cartao": limite, "cor_hex": colors_c[i % len(colors_c)],
                    "dias_para_vencer": (f.data_vencimento - today).days if f.data_vencimento else None
                })
            result['cartoes'] = lista_c
        except Exception as e:
            logger.error(f"Erro Modo Deus (cartoes): {e}")
            result['cartoes'] = []

        # --- SEÇÃO 6: METAS ---
        try:
            metas = db.query(Objetivo).filter(Objetivo.id_usuario == user_id, Objetivo.valor_atual < Objetivo.valor_meta).all()
            result['metas'] = [{
                "descricao": m.descricao, "valor_meta": float(m.valor_meta), "valor_atual": float(m.valor_atual or 0),
                "percentual": (float(m.valor_atual or 0) / float(m.valor_meta) * 100) if m.valor_meta > 0 else 0
            } for m in metas]
        except Exception as e:
            result['metas'] = []

        # --- SEÇÃO 7: ORÇAMENTOS ---
        try:
            orcs = db.query(OrcamentoCategoria).filter(OrcamentoCategoria.id_usuario == user_id).all()
            lista_o = []
            for o in orcs:
                gasto = db.query(func.sum(Lancamento.valor)).filter(Lancamento.id_usuario == user_id, Lancamento.id_categoria == o.id_categoria, Lancamento.tipo.in_(['Saída', 'Despesa']), Lancamento.data_transacao >= datetime.combine(start_month, time.min)).scalar() or 0
                gasto = abs(float(gasto))
                perc = (gasto / float(o.valor_limite) * 100) if o.valor_limite > 0 else 0
                lista_o.append({"categoria": o.categoria.nome if o.categoria else "Outros", "percentual_usado": perc, "status": "estourado" if perc > 100 else ("atencao" if perc > 75 else "ok")})
            result['orcamentos'] = lista_o
        except Exception as e:
            result['orcamentos'] = []

        # --- SEÇÃO 8: FIIS ---
        try:
            fiis = db.query(CarteiraFII).filter(CarteiraFII.id_usuario == user_id, CarteiraFII.ativo == True).all()
            lista_f = [{"ticker": f.ticker, "quantidade_cotas": float(f.quantidade_cotas), "valor_posicao": float(f.quantidade_cotas * f.preco_medio), "preco_medio": float(f.preco_medio)} for f in fiis]
            renda = db.query(HistoricoAlertaFII.valor_referencia).filter(HistoricoAlertaFII.id_usuario == user_id, HistoricoAlertaFII.tipo_alerta == 'rendimento_pago', HistoricoAlertaFII.enviado_em >= datetime.now(timezone.utc) - timedelta(days=30)).all()
            result['fiis'] = {"lista": lista_f, "renda_mensal_estimada": sum(float(r[0]) for r in renda) if renda else 0}
        except Exception as e:
            result['fiis'] = {"lista": [], "renda_mensal_estimada": 0}

        # --- SEÇÃO 9: ALERTAS E SCORE (Rigoroso) ---
        try:
            alertas = []
            score = 100
            
            vg = result.get('visao_geral', {})
            if vg.get('resultado_mes', 0) < 0:
                score -= 30
                alertas.append({"tipo": "critico", "titulo": "Mês no Vermelho", "detalhe": f"Déficit de R$ {abs(vg['resultado_mes']):.2f}", "data": datetime.now().isoformat()})
            
            if vg.get('saldo_disponivel', 0) < 0:
                score -= 50
                alertas.append({"tipo": "critico", "titulo": "Conta Negativa", "detalhe": "Saldo disponível abaixo de zero.", "data": datetime.now().isoformat()})

            juros_atual = abs(float(db.query(func.sum(Lancamento.valor)).filter(Lancamento.id_usuario == user_id, Lancamento.tipo.in_(['Saída', 'Despesa']), func.lower(Lancamento.descricao).op('~')('juros|multa|encargo|iof'), Lancamento.data_transacao >= datetime.combine(start_month, time.min)).scalar() or 0))
            if juros_atual > 0: 
                score -= 20
                alertas.append({"tipo": "critico", "titulo": "🚨 Gastos com Juros", "detalhe": f"Você pagou R$ {juros_atual:.2f} em juros este mês.", "data": datetime.now().isoformat()})
            
            for o in result.get('orcamentos', []):
                if o['status'] == 'estourado':
                    score -= 10
                    alertas.append({"tipo": "critico", "titulo": f"Limite de {o['categoria']} estourado", "detalhe": f"Gasto {o['percentual_usado']:.0f}% do limite."})
            
            if vg.get('patrimonio_liquido', 0) < 0:
                score -= 40
            
            score = max(0, score)
            label_score = "Excelente"
            if score < 40: label_score = "Crítico"
            elif score < 70: label_score = "Atenção"
            
            result['health'] = {"score": score, "label": label_score}
            result['alertas'] = alertas[:6]
        except Exception as e:
            logger.error(f"Erro Modo Deus (alertas/score): {e}")
            result['health'] = {"score": 50, "label": "Erro ao calcular"}

        # --- SEÇÃO 10: VENCIMENTOS ---
        try:
            v_limit = today + timedelta(days=30)
            lista_v = [{"descricao": a.descricao, "valor": float(a.valor), "data": a.proxima_data_execucao.isoformat(), "cor_hex": "#378ADD"} for a in db.query(Agendamento).filter(Agendamento.id_usuario == user_id, Agendamento.ativo == True, Agendamento.proxima_data_execucao <= v_limit).all()]
            lista_v += [{"descricao": f"Fatura {f.conta.nome}", "valor": float(f.valor_total), "data": f.data_vencimento.isoformat(), "cor_hex": "#534AB7"} for f in db.query(FaturaCartao).filter(FaturaCartao.id_usuario == user_id, FaturaCartao.data_vencimento >= today, FaturaCartao.data_vencimento <= v_limit, FaturaCartao.status != 'paga').all()]
            result['proximos_vencimentos'] = sorted(lista_v, key=lambda x: x['data'])[:8]
        except Exception as e:
            result['proximos_vencimentos'] = []

        # --- SEÇÃO 11: INSIGHTS RÁPIDOS ---
        try:
            ins = []
            vg = result.get('visao_geral', {})
            if vg.get('resultado_mes', 0) < 0: ins.append(f"O mês está fechando no vermelho em R$ {abs(vg['resultado_mes']):.2f}")
            if result.get('top_categorias') and result['top_categorias'][0]['percentual_do_total_gastos'] > 40: ins.append(f"{result['top_categorias'][0]['nome']} consome {result['top_categorias'][0]['percentual_do_total_gastos']:.0f}% dos gastos.")
            result['insights_rapidos'] = ins[:3]
        except Exception as e:
            result['insights_rapidos'] = []

        _cache[cache_key_val] = (result, now_ts)
        return jsonify(result)
    finally:
        db.close()


@app.route('/api/miniapp/overview')
def miniapp_overview():
    """Retorna o resumo da home do miniapp."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        start_date, end_date = _month_bounds()
        base_query = (
            db.query(Lancamento)
            .options(joinedload(Lancamento.categoria), joinedload(Lancamento.subcategoria))
            .filter(Lancamento.id_usuario == usuario.id)
        )
        lancamentos_mes = (
            base_query
            .filter(Lancamento.data_transacao >= datetime.combine(start_date, datetime.min.time()))
            .filter(Lancamento.data_transacao <= datetime.combine(end_date, datetime.max.time()))
            .order_by(Lancamento.data_transacao.asc())
            .all()
        )

        receita = sum(abs(float(lanc.valor or 0)) for lanc in lancamentos_mes if str(lanc.tipo).lower().startswith(("entr", "recei")))
        despesa = sum(abs(float(lanc.valor or 0)) for lanc in lancamentos_mes if str(lanc.tipo).lower().startswith(("desp", "saida")))
        
        # Saldo do mês (Resultado Líquido)
        balance = receita - despesa

        cashflow = _daily_cashflow(lancamentos_mes, start_date, end_date)
        categories = _category_distribution(lancamentos_mes)
        insight = _build_miniapp_insight(usuario, balance, receita, despesa, categories, cashflow)

        recent_items = (
            base_query
            .order_by(Lancamento.data_transacao.desc(), Lancamento.id.desc())
            .limit(6)
            .all()
        )

        # Series reais para os 6 gráficos estratégicos.
        today = datetime.utcnow().date()

        # Últimos 6 meses para fluxo de caixa.
        month_refs_6 = []
        for i in range(5, -1, -1):
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_refs_6.append((year, month))

        start_6 = date(month_refs_6[0][0], month_refs_6[0][1], 1)
        lanc_6m = (
            db.query(Lancamento)
            .options(joinedload(Lancamento.categoria), joinedload(Lancamento.subcategoria))
            .filter(Lancamento.id_usuario == usuario.id)
            .filter(Lancamento.data_transacao >= datetime.combine(start_6, datetime.min.time()))
            .all()
        )

        monthly_map: dict[tuple[int, int], dict[str, float]] = {
            key: {"entrada": 0.0, "saida": 0.0, "net": 0.0}
            for key in month_refs_6
        }
        for lanc in lanc_6m:
            if not lanc.data_transacao:
                continue
            key = (lanc.data_transacao.year, lanc.data_transacao.month)
            if key not in monthly_map:
                continue
            valor = abs(float(lanc.valor or 0))
            is_entrada = str(lanc.tipo).lower().startswith(("entr", "recei"))
            if is_entrada:
                monthly_map[key]["entrada"] += valor
                monthly_map[key]["net"] += valor
            else:
                saida = valor
                monthly_map[key]["saida"] += saida
                monthly_map[key]["net"] -= saida

        monthly_cashflow = []
        for year, month in month_refs_6:
            d = date(year, month, 1)
            label = d.strftime("%b").lower()
            monthly_cashflow.append({
                "label": label,
                "entrada": round(monthly_map[(year, month)]["entrada"], 2),
                "saida": round(monthly_map[(year, month)]["saida"], 2),
            })

        # Evolução patrimonial (últimos 8 meses) com base no saldo acumulado real.
        month_refs_8 = []
        for i in range(7, -1, -1):
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_refs_8.append((year, month))
        start_8 = date(month_refs_8[0][0], month_refs_8[0][1], 1)

        prior_lanc = (
            db.query(Lancamento)
            .filter(Lancamento.id_usuario == usuario.id)
            .filter(Lancamento.data_transacao < datetime.combine(start_8, datetime.min.time()))
            .all()
        )
        prior_balance = 0.0
        for lanc in prior_lanc:
            valor = abs(float(lanc.valor or 0))
            prior_balance += valor if str(lanc.tipo).lower().startswith(("entr", "recei")) else -valor

        patrimony_map: dict[tuple[int, int], float] = {key: 0.0 for key in month_refs_8}
        lanc_8m = (
            db.query(Lancamento)
            .filter(Lancamento.id_usuario == usuario.id)
            .filter(Lancamento.data_transacao >= datetime.combine(start_8, datetime.min.time()))
            .all()
        )
        for lanc in lanc_8m:
            if not lanc.data_transacao:
                continue
            key = (lanc.data_transacao.year, lanc.data_transacao.month)
            if key not in patrimony_map:
                continue
            valor = abs(float(lanc.valor or 0))
            patrimony_map[key] += valor if str(lanc.tipo).lower().startswith(("entr", "recei")) else -valor

        running_balance = prior_balance
        patrimony_series = []
        for year, month in month_refs_8:
            running_balance += patrimony_map[(year, month)]
            d = date(year, month, 1)
            patrimony_series.append({
                "label": d.strftime("%b").lower(),
                "value": round(running_balance, 2),
            })

        # Orçamento vs realizado por categoria (realizado no mês vs média dos 3 meses anteriores como teto realista).
        orcamentos_reais = db.query(OrcamentoCategoria).filter(OrcamentoCategoria.id_usuario == usuario.id).all()
        orcamentos_map = {o.categoria.nome: float(o.valor_limite) for o in orcamentos_reais if o.categoria}
        
        current_expenses: dict[str, float] = {}
        for lanc in lancamentos_mes:
            if str(lanc.tipo).lower().startswith(("entr", "recei")):
                continue
            categoria = lanc.categoria.nome if lanc.categoria and lanc.categoria.nome else "Sem categoria"
            current_expenses[categoria] = current_expenses.get(categoria, 0.0) + abs(float(lanc.valor or 0))

        sorted_current = sorted(current_expenses.items(), key=lambda x: x[1], reverse=True)[:5]
        budget_items = []
        if sorted_current:
            hist_start = date(start_date.year, start_date.month, 1) - timedelta(days=90)
            hist_lanc = (
                db.query(Lancamento)
                .options(joinedload(Lancamento.categoria))
                .filter(Lancamento.id_usuario == usuario.id)
                .filter(Lancamento.data_transacao >= datetime.combine(hist_start, datetime.min.time()))
                .filter(Lancamento.data_transacao < datetime.combine(start_date, datetime.min.time()))
                .all()
            )

            hist_by_cat: dict[str, float] = {}
            for lanc in hist_lanc:
                if str(lanc.tipo).lower().startswith(("entr", "recei")):
                    continue
                categoria = lanc.categoria.nome if lanc.categoria and lanc.categoria.nome else "Sem categoria"
                hist_by_cat[categoria] = hist_by_cat.get(categoria, 0.0) + abs(float(lanc.valor or 0))

            for categoria, realizado in sorted_current:
                # Usa o limite real definido pelo usuário, ou a média de fallback
                if categoria in orcamentos_map:
                    limite = orcamentos_map[categoria]
                else:
                    media_3m = hist_by_cat.get(categoria, 0.0) / 3.0 if hist_by_cat.get(categoria, 0.0) > 0 else realizado
                    limite = max(realizado, media_3m * 1.1)
                
                budget_items.append({
                    "label": categoria,
                    "orcamento": round(limite, 2),
                    "realizado": round(realizado, 2),
                })

        # Projeção simples com base no saldo e média de resultado mensal recente.
        avg_net = sum(monthly_map[key]["net"] for key in month_refs_6) / max(len(month_refs_6), 1)
        projection_series = []
        if patrimony_series:
            current_base = float(patrimony_series[-1]["value"])
            month_refs_10 = []
            for i in range(5, -1, -1):
                year = today.year
                month = today.month - i
                while month <= 0:
                    month += 12
                    year -= 1
                month_refs_10.append((year, month, "historico"))
            for i in range(1, 5):
                year = today.year
                month = today.month + i
                while month > 12:
                    month -= 12
                    year += 1
                month_refs_10.append((year, month, "futuro"))

            hist_map = {(item["label"], idx): item["value"] for idx, item in enumerate(patrimony_series[-6:])}
            # Históricos: usa série patrimonial real mais recente.
            hist_values = [item["value"] for item in patrimony_series[-6:]]
            while len(hist_values) < 6:
                hist_values.insert(0, current_base)

            for idx, (year, month, tipo_ref) in enumerate(month_refs_10):
                label = date(year, month, 1).strftime("%b").lower()
                if tipo_ref == "historico":
                    value = hist_values[idx]
                    projection_series.append({"label": label, "historico": round(value, 2), "futuro": None})
                else:
                    passo = idx - 5
                    future_value = current_base + (avg_net * passo)
                    projection_series.append({"label": label, "historico": None, "futuro": round(future_value, 2)})

        # --- SEÇÃO RADAR FINANCEIRO (CARTÕES E PARCELAS) ---
        # Filtro inteligente: faturas que vencem hoje/futuro OU faturas do mês atual (independente de estarem abertas ou não)
        current_month_start = today.replace(day=1)
        faturas_db = db.query(FaturaCartao).join(Conta).filter(
            FaturaCartao.id_usuario == usuario.id,
            or_(
                FaturaCartao.data_vencimento >= today,
                FaturaCartao.mes_referencia >= current_month_start
            )
        ).order_by(FaturaCartao.data_vencimento.asc()).all()
        
        cards_summary = []
        seen_accounts = set()
        for f in faturas_db:
            if f.id_conta in seen_accounts: continue
            seen_accounts.add(f.id_conta)
            cards_summary.append({
                "nome": f.conta.nome,
                "fatura": float(f.valor_total),
                "limite": float(f.conta.limite_cartao or 0),
                "vence": f.data_vencimento.isoformat() if f.data_vencimento else None
            })

        parcelas_db = db.query(ParcelamentoItem).filter(
            ParcelamentoItem.id_usuario == usuario.id,
            or_(ParcelamentoItem.data_proxima_parcela.is_(None), ParcelamentoItem.data_proxima_parcela >= (today - timedelta(days=2)))
        ).order_by(ParcelamentoItem.data_proxima_parcela.asc()).limit(3).all()
        
        installments_summary = []
        for p in parcelas_db:
            installments_summary.append({
                "desc": p.descricao,
                "valor": float(p.valor_parcela),
                "parcela": f"{p.parcela_atual}/{p.total_parcelas}",
                "vence": p.data_proxima_parcela.isoformat() if p.data_proxima_parcela else None
            })

        # Top vilões reais dos últimos 90 dias.
        villains_start = today - timedelta(days=90)
        villains_lanc = (
            db.query(Lancamento)
            .filter(Lancamento.id_usuario == usuario.id)
            .filter(Lancamento.data_transacao >= datetime.combine(villains_start, datetime.min.time()))
            .all()
        )
        villains_totals = {}
        for lanc in villains_lanc:
            try:
                if not lanc.tipo or str(lanc.tipo).lower().startswith(("entr", "recei")):
                    continue
                nome = (lanc.descricao or "Sem nome").strip() or "Sem nome"
                valor_lanc = abs(float(lanc.valor or 0))
                villains_totals[nome] = villains_totals.get(nome, 0.0) + valor_lanc
            except (TypeError, ValueError):
                continue

        top_villains = [
            {"label": nome, "value": round(valor, 2)}
            for nome, valor in sorted(villains_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        progress_base = float(receita + despesa)
        progress_pct = round((despesa / progress_base) * 100) if progress_base > 0 else 0
        xp = int(usuario.xp or 0)
        level = int(usuario.level or 1)
        streak = int(usuario.streak_dias or 0)
        
        try:
            level_progress = get_level_progress_payload(usuario)
        except Exception as e:
            logger.warning(f"Erro ao obter level_progress: {e}")
            level_progress = {"level": level, "xp": xp, "title": "Usuário"}

        # Importa função de label do plano
        user_plan = str(usuario.plan or "free").lower()
        try:
            from gerente_financeiro.monetization import _plan_label
            user_plan_label = _plan_label(user_plan)
        except Exception:
            user_plan_label = "Plano Free"

        # Garantir que insight nunca seja None para o JSON
        final_insight = insight or "O Alfredo está analisando seus dados..."

        return jsonify({
            "ok": True,
            "summary": {
                "balance": round(float(balance), 2),
                "receita": round(float(receita), 2),
                "despesa": round(float(despesa), 2),
                "progress_pct": max(0, min(int(progress_pct), 100)),
                "level": level,
                "xp": xp,
                "streak": streak,
                "level_title": level_progress.get("title", "Mestre das Finanças"),
                "level_progress": level_progress,
                "insight": final_insight,
                "badge": _level_badge(level),
                "badge_svg": _level_badge_svg(level),
                "cashflow": cashflow or [],
                "cashflow_monthly": monthly_cashflow or [],
                "categories": categories or [],
                "patrimony_series": patrimony_series or [],
                "budget_vs_realizado": budget_items or [],
                "projection_series": projection_series or [],
                "top_villains": top_villains,
                "recent": [_serialize_miniapp_lancamento(lanc) for lanc in (recent_items or [])],
                "plan": user_plan,
                "plan_label": user_plan_label,
                "cards": cards_summary or [],
                "installments": installments_summary or [],
            }
        })
    finally:
        db.close()


@app.route('/api/miniapp/lancamentos', methods=['POST'])
def miniapp_lancamento_create():
    """Cria um lançamento pelo miniapp."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    descricao = (payload.get("descricao") or "").strip()
    if not descricao:
        return jsonify({"ok": False, "error": "missing_descricao"}), 400

    try:
        valor = float(str(payload.get("valor", 0)).replace(",", "."))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_valor"}), 400
    if valor <= 0:
        return jsonify({"ok": False, "error": "invalid_valor"}), 400

    tipo = "Entrada" if str(payload.get("tipo", "Saída")).strip().lower() == "entrada" else "Saída"
    forma_pagamento = _normalize_forma_pagamento(payload.get("forma_pagamento"))

    parsed_date = _parse_date(payload.get("data_transacao") or payload.get("data"))
    data_transacao = datetime.combine(parsed_date, datetime.min.time()) if parsed_date else datetime.now()

    id_categoria, id_subcategoria = _resolve_categoria_ids(payload)

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        lancamento = Lancamento(
            id_usuario=usuario.id,
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            data_transacao=data_transacao,
            forma_pagamento=forma_pagamento,
            id_categoria=id_categoria,
            id_subcategoria=id_subcategoria,
                origem="miniapp",
        )
        db.add(lancamento)
        db.commit()
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True, "id": lancamento.id})
    finally:
        db.close()


@app.route('/api/miniapp/lancamentos/<int:lancamento_id>', methods=['PATCH', 'DELETE'])
def miniapp_lancamento_update(lancamento_id: int):
    """Atualiza ou remove lancamento pelo miniapp"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        lancamento = (
            db.query(Lancamento)
            .filter(Lancamento.id == lancamento_id, Lancamento.id_usuario == usuario.id)
            .first()
        )
        if not lancamento:
            return jsonify({"ok": False, "error": "not_found"}), 404

        if request.method == 'DELETE':
            db.delete(lancamento)
            db.commit()
            _invalidate_financial_cache(session["user_id"])
            return jsonify({"ok": True})

        payload = request.get_json(silent=True) or {}
        learn_rule = payload.get("learn_rule", False)
        
        allowed_fields = {
            "descricao",
            "valor",
            "tipo",
            "forma_pagamento",
            "id_categoria",
            "id_subcategoria",
            "data_transacao",
        }
        for key, value in payload.items():
            if key not in allowed_fields:
                continue
            if key == "data_transacao":
                parsed_date = _parse_date(value)
                if parsed_date:
                    lancamento.data_transacao = datetime.combine(parsed_date, datetime.min.time())
                continue
            if key == "forma_pagamento":
                lancamento.forma_pagamento = _normalize_forma_pagamento(value)
                continue
            
            # Converte IDs vazios ou strings para int/None
            if key in ("id_categoria", "id_subcategoria"):
                try:
                    value = int(value) if value not in (None, "") else None
                except (TypeError, ValueError):
                    value = None
            
            setattr(lancamento, key, value)

        # Lógica de Aprendizado (Regras Personalizadas)
        if learn_rule and lancamento.id_categoria:
            nome_limpo = limpar_descricao(lancamento.descricao or "")
            if nome_limpo:
                regra = db.query(RegraCategorizacao).filter(
                    RegraCategorizacao.id_usuario == usuario.id,
                    RegraCategorizacao.descricao_substring == nome_limpo
                ).first()
                if not regra:
                    regra = RegraCategorizacao(
                        id_usuario=usuario.id,
                        descricao_substring=nome_limpo
                    )
                    db.add(regra)
                
                regra.id_categoria = lancamento.id_categoria
                regra.id_subcategoria = lancamento.id_subcategoria
                logger.info(f"Regra de aprendizado salva para user {usuario.id}: {nome_limpo} -> {lancamento.id_categoria}")

        db.commit()
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route('/api/miniapp/configuracoes', methods=['GET', 'PUT'])
def miniapp_configuracoes():
    """Lê e atualiza dados de onboarding e notificações do MiniApp."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        if request.method == 'GET':
            return jsonify({
                "ok": True,
                "usuario": {
                    "nome_completo": usuario.nome_completo,
                    "perfil_investidor": usuario.perfil_investidor,
                    "horario_notificacao": usuario.horario_notificacao.strftime('%H:%M') if usuario.horario_notificacao else "09:00",
                    "alerta_gastos_ativo": bool(usuario.alerta_gastos_ativo),
                    # Novas flags de notificações
                    "notif_lembretes": bool(getattr(usuario, 'notif_lembretes', True)),
                    "notif_alertas_risco": bool(getattr(usuario, 'notif_alertas_risco', True)),
                    "notif_insights": bool(getattr(usuario, 'notif_insights', True)),
                    "notif_gamificacao": bool(getattr(usuario, 'notif_gamificacao', True)),
                },
            })

        payload = request.get_json(silent=True) or {}
        if "perfil_investidor" in payload:
            usuario.perfil_investidor = (payload.get("perfil_investidor") or "").strip() or None
        if "horario_notificacao" in payload:
            horario_raw = str(payload.get("horario_notificacao") or "").strip()
            if horario_raw:
                try:
                    usuario.horario_notificacao = datetime.strptime(horario_raw, "%H:%M").time()
                except ValueError:
                    return jsonify({"ok": False, "error": "invalid_time"}), 400
        if "alerta_gastos_ativo" in payload:
            usuario.alerta_gastos_ativo = bool(payload.get("alerta_gastos_ativo"))

        # Atualiza novas flags
        if "notif_lembretes" in payload:
            usuario.notif_lembretes = bool(payload.get("notif_lembretes"))
        if "notif_alertas_risco" in payload:
            usuario.notif_alertas_risco = bool(payload.get("notif_alertas_risco"))
        if "notif_insights" in payload:
            usuario.notif_insights = bool(payload.get("notif_insights"))
        if "notif_gamificacao" in payload:
            usuario.notif_gamificacao = bool(payload.get("notif_gamificacao"))

        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()

@app.route('/api/miniapp/agendamentos', methods=['GET', 'POST'])
def miniapp_agendamentos():
    """Lista ou cria agendamentos"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        if request.method == 'GET':
            items = (
                db.query(Agendamento)
                .filter(Agendamento.id_usuario == usuario.id)
                .order_by(Agendamento.proxima_data_execucao.asc())
                .all()
            )
            payload = [
                {
                    "id": item.id,
                    "descricao": item.descricao,
                    "valor": float(item.valor),
                    "tipo": item.tipo,
                    "frequencia": item.frequencia,
                    "proxima_data_execucao": item.proxima_data_execucao.isoformat(),
                    "ativo": item.ativo,
                }
                for item in items
            ]
            return jsonify({"ok": True, "items": payload})

        data = request.get_json(silent=True) or {}
        data_primeiro = _parse_date(data.get("data_primeiro_evento"))
        if not data_primeiro:
            return jsonify({"ok": False, "error": "invalid_date"}), 400

        agendamento = Agendamento(
            id_usuario=usuario.id,
            descricao=data.get("descricao", ""),
            valor=float(data.get("valor", 0)),
            tipo=data.get("tipo", "Saída"),
            id_categoria=data.get("id_categoria"),
            id_subcategoria=data.get("id_subcategoria"),
            data_primeiro_evento=data_primeiro,
            frequencia=data.get("frequencia", "mensal"),
            total_parcelas=data.get("total_parcelas"),
            parcela_atual=data.get("parcela_atual", 0),
            proxima_data_execucao=data_primeiro,
            ativo=True,
        )
        db.add(agendamento)
        db.commit()
        db.refresh(agendamento)
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True, "id": agendamento.id})
    finally:
        db.close()


@app.route('/api/miniapp/agendamentos/<int:agendamento_id>', methods=['PATCH', 'DELETE'])
def miniapp_agendamentos_update(agendamento_id: int):
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        agendamento = (
            db.query(Agendamento)
            .filter(Agendamento.id == agendamento_id, Agendamento.id_usuario == usuario.id)
            .first()
        )
        if not agendamento:
            return jsonify({"ok": False, "error": "not_found"}), 404

        if request.method == 'DELETE':
            db.delete(agendamento)
            db.commit()
            _invalidate_financial_cache(session["user_id"])
            return jsonify({"ok": True})

        data = request.get_json(silent=True) or {}
        for key in ["descricao", "valor", "tipo", "frequencia", "ativo"]:
            if key in data:
                setattr(agendamento, key, data[key])
        if "proxima_data_execucao" in data:
            parsed = _parse_date(data.get("proxima_data_execucao"))
            if parsed:
                agendamento.proxima_data_execucao = parsed
        db.commit()
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True})
    finally:
        db.close()

@app.route('/api/miniapp/orcamentos', methods=['GET', 'POST'])
def miniapp_orcamentos():
    """Lista ou cria limites de orçamento para categorias."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        if request.method == 'GET':
            orcamentos = db.query(OrcamentoCategoria).options(joinedload(OrcamentoCategoria.categoria)).filter(OrcamentoCategoria.id_usuario == usuario.id).all()
            today = datetime.now()
            items = []
            for o in orcamentos:
                periodo = o.periodo or 'monthly'
                if periodo == 'daily':
                    start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
                elif periodo == 'weekly':
                    # Começo da semana (segunda-feira)
                    start_date = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
                else: # monthly
                    start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                gasto = db.query(func.sum(Lancamento.valor)).filter(
                    Lancamento.id_usuario == usuario.id,
                    Lancamento.id_categoria == o.id_categoria,
                    Lancamento.tipo.in_(['Saída', 'Despesa']),
                    Lancamento.data_transacao >= start_date
                ).scalar() or 0
                items.append({
                    "id": o.id,
                    "id_categoria": o.id_categoria,
                    "categoria_nome": o.categoria.nome if o.categoria else "Desconhecida",
                    "valor_limite": float(o.valor_limite),
                    "valor_gasto": float(gasto),
                    "periodo": periodo
                })
            categorias = db.query(Categoria).order_by(Categoria.nome).all()
            cats = [{"id": c.id, "nome": c.nome} for c in categorias]
            return jsonify({"ok": True, "items": items, "categorias": cats})

        data = request.get_json(silent=True) or {}
        id_cat = int(data.get("id_categoria", 0))
        valor = float(str(data.get("valor_limite", 0)).replace(",", "."))
        periodo = data.get("periodo", "monthly")

        if valor <= 0:
            db.query(OrcamentoCategoria).filter(OrcamentoCategoria.id_usuario == usuario.id, OrcamentoCategoria.id_categoria == id_cat).delete()
        else:
            orc = db.query(OrcamentoCategoria).filter(OrcamentoCategoria.id_usuario == usuario.id, OrcamentoCategoria.id_categoria == id_cat).first()
            if orc: 
                orc.valor_limite = valor
                orc.periodo = periodo
            else: 
                db.add(OrcamentoCategoria(id_usuario=usuario.id, id_categoria=id_cat, valor_limite=valor, periodo=periodo))
        db.commit()
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True})
    finally:
        db.close()

@app.route('/api/miniapp/metas', methods=['GET', 'POST'])
def miniapp_metas():
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        if request.method == 'GET':
            now = datetime.utcnow()
            confirmacoes_mes = (
                db.query(MetaConfirmacao)
                .filter(
                    MetaConfirmacao.id_usuario == usuario.id,
                    MetaConfirmacao.ano == now.year,
                    MetaConfirmacao.mes == now.month,
                )
                .all()
            )
            confirmacoes_por_meta = {c.id_objetivo: c for c in confirmacoes_mes}

            metas = (
                db.query(Objetivo)
                .filter(Objetivo.id_usuario == usuario.id)
                .order_by(Objetivo.data_meta.asc())
                .all()
            )
            payload = [
                {
                    "id": meta.id,
                    "descricao": meta.descricao,
                    "valor_meta": float(meta.valor_meta),
                    "valor_atual": float(meta.valor_atual or 0),
                    "data_meta": meta.data_meta.isoformat() if meta.data_meta else None,
                    "confirmado_mes_atual": bool(confirmacoes_por_meta.get(meta.id)),
                    "valor_confirmado_mes": float(confirmacoes_por_meta[meta.id].valor_confirmado) if meta.id in confirmacoes_por_meta else None,
                    "confirmado_em": confirmacoes_por_meta[meta.id].criado_em.isoformat() if meta.id in confirmacoes_por_meta and confirmacoes_por_meta[meta.id].criado_em else None,
                }
                for meta in metas
            ]
            return jsonify({"ok": True, "items": payload})

        data = request.get_json(silent=True) or {}
        data_meta = _parse_date(data.get("data_meta"))
        if not data_meta:
            return jsonify({"ok": False, "error": "invalid_date"}), 400

        meta = Objetivo(
            id_usuario=usuario.id,
            descricao=data.get("descricao", ""),
            valor_meta=float(data.get("valor_meta", 0)),
            valor_atual=float(data.get("valor_atual", 0)),
            data_meta=data_meta,
        )
        db.add(meta)
        db.commit()
        db.refresh(meta)
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True, "id": meta.id})
    finally:
        db.close()


@app.route('/api/miniapp/metas/<int:meta_id>', methods=['PATCH', 'DELETE'])
def miniapp_metas_update(meta_id: int):
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        meta = (
            db.query(Objetivo)
            .filter(Objetivo.id == meta_id, Objetivo.id_usuario == usuario.id)
            .first()
        )
        if not meta:
            return jsonify({"ok": False, "error": "not_found"}), 404

        if request.method == 'DELETE':
            db.delete(meta)
            db.commit()
            _invalidate_financial_cache(session["user_id"])
            return jsonify({"ok": True})

        data = request.get_json(silent=True) or {}
        for key in ["descricao", "valor_meta", "valor_atual"]:
            if key in data:
                setattr(meta, key, data[key])
        if "data_meta" in data:
            parsed = _parse_date(data.get("data_meta"))
            if parsed:
                meta.data_meta = parsed
        db.commit()
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route('/api/miniapp/metas/<int:meta_id>/confirmar', methods=['POST'])
def miniapp_meta_confirmar_mes(meta_id: int):
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        meta = (
            db.query(Objetivo)
            .filter(Objetivo.id == meta_id, Objetivo.id_usuario == usuario.id)
            .first()
        )
        if not meta:
            return jsonify({"ok": False, "error": "not_found"}), 404

        payload = request.get_json(silent=True) or {}
        try:
            valor_confirmado = float(str(payload.get("valor_confirmado", meta.valor_meta)).replace(",", "."))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_valor_confirmado"}), 400

        agora = datetime.utcnow()
        confirmacao = (
            db.query(MetaConfirmacao)
            .filter(
                MetaConfirmacao.id_usuario == usuario.id,
                MetaConfirmacao.id_objetivo == meta.id,
                MetaConfirmacao.ano == agora.year,
                MetaConfirmacao.mes == agora.month,
            )
            .first()
        )

        if not confirmacao:
            confirmacao = MetaConfirmacao(
                id_usuario=usuario.id,
                id_objetivo=meta.id,
                ano=agora.year,
                mes=agora.month,
                valor_confirmado=valor_confirmado,
            )
            db.add(confirmacao)
        else:
            confirmacao.valor_confirmado = valor_confirmado

        valor_meta_alvo = float(meta.valor_meta or 0)
        valor_atual_antes = float(meta.valor_atual or 0)

        if valor_confirmado > valor_atual_antes:
            meta.valor_atual = valor_confirmado

        # Concede XP por check-in mensal da meta.
        _award_xp_from_miniapp(db, session["user_id"], "META_CHECKIN")

        # Bonus grande ao atingir a meta pela primeira vez.
        atingiu_agora = valor_meta_alvo > 0 and valor_atual_antes < valor_meta_alvo and float(meta.valor_atual or 0) >= valor_meta_alvo
        if atingiu_agora:
            _award_xp_from_miniapp(db, session["user_id"], "META_ATINGIDA")

        db.commit()
        _invalidate_financial_cache(session["user_id"])
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route('/api/miniapp/game-profile')
def miniapp_game_profile():
    """Perfil gamer do usuário com progressão, interações, top features E MISSÕES."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        now = datetime.utcnow()
        week_start = now - timedelta(days=7)

        total_interactions = (
            db.query(func.count(XpEvent.id))
            .filter(XpEvent.id_usuario == usuario.id)
            .scalar()
        ) or 0

        week_interactions = (
            db.query(func.count(XpEvent.id))
            .filter(XpEvent.id_usuario == usuario.id)
            .filter(XpEvent.created_at >= week_start)
            .scalar()
        ) or 0

        top_features_rows = (
            db.query(XpEvent.action, func.count(XpEvent.id).label('total'))
            .filter(XpEvent.id_usuario == usuario.id)
            .group_by(XpEvent.action)
            .order_by(desc('total'))
            .limit(6)
            .all()
        )
        top_features = [
            {
                "feature": _friendly_feature_name(row.action),
                "raw_feature": row.action,
                "interactions": int(row.total or 0),
            }
            for row in top_features_rows
        ]

        month_start, month_end = _get_month_bounds()
        monthly_scores = (
            db.query(
                XpEvent.id_usuario,
                func.sum(XpEvent.xp_gained).label('monthly_xp'),
            )
            .filter(XpEvent.created_at >= month_start)
            .filter(XpEvent.created_at <= month_end)
            .group_by(XpEvent.id_usuario)
            .order_by(desc('monthly_xp'))
            .all()
        )
        monthly_rank = None
        for idx, row in enumerate(monthly_scores, start=1):
            if int(row.id_usuario) == int(usuario.id):
                monthly_rank = idx
                break

        user_missions = get_user_active_missions(db, usuario.id)

        level_progress = get_level_progress_payload(usuario)
        top_feature_name = top_features[0]["feature"] if top_features else None

        canonical_level = int(level_progress.get("level") or 1)
        if int(usuario.level or 1) != canonical_level:
            usuario.level = canonical_level
            db.commit()

        return jsonify({
            "ok": True,
            "profile": {
                "name": usuario.nome_completo or "Jogador",
                "telegram_id": int(usuario.telegram_id),
                "level": canonical_level,
                "title": level_progress.get("title") or "Caderneta Zerada",
                "badge": _level_badge(canonical_level),
                "badge_svg": _level_badge_svg(canonical_level),
                "streak": int(usuario.streak_dias or 0),
                "xp": level_progress,
                "monthly_rank": monthly_rank,
                "interactions_total": int(total_interactions),
                "interactions_week": int(week_interactions),
                "top_features": top_features,
                "missions": user_missions,
                "alfredo_note": _alfredo_profile_note(int(level_progress.get("progress_pct", 0)), int(week_interactions), top_feature_name),
            },
        })
    finally:
        db.close()


@app.route('/api/miniapp/mission-claim', methods=['POST'])
def miniapp_mission_claim():
    """Resgata a recompensa de uma missão concluída."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    mission_id = int(payload.get('mission_id') or 0)
    if not mission_id:
        return jsonify({"ok": False, "error": "invalid_mission_id"}), 400

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        user_mission = (
            db.query(UserMission)
            .filter(UserMission.id == mission_id)
            .filter(UserMission.id_usuario == usuario.id)
            .first()
        )
        if not user_mission:
            return jsonify({"ok": False, "error": "mission_not_found"}), 404
        if user_mission.status == 'claimed':
            return jsonify({"ok": False, "error": "mission_already_claimed"}), 400
        if user_mission.status != 'completed':
            return jsonify({"ok": False, "error": "mission_not_completed"}), 400

        mission_reward = int(user_mission.mission.xp_reward or 0)
        usuario.xp = int(usuario.xp or 0) + mission_reward
        from gerente_financeiro.gamification_missions_service import _calculate_level_from_xp
        usuario.level = int(_calculate_level_from_xp(int(usuario.xp or 0)))

        user_mission.status = 'claimed'
        user_mission.claimed_at = datetime.utcnow()
        db.commit()
        _invalidate_financial_cache(session["user_id"])

        return jsonify({
            "ok": True,
            "xp_gained": mission_reward,
            "new_xp": int(usuario.xp or 0),
            "new_level": int(usuario.level or 1),
        })
    except Exception as exc:
        db.rollback()
        logger.exception("Erro ao resgatar missão: %s", exc)
        return jsonify({"ok": False, "error": "mission_claim_failed"}), 500
    finally:
        db.close()


@app.route('/api/miniapp/missions')
def miniapp_missions():
    """Retorna missões ativas e seu progresso atual."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        missions = get_user_active_missions(db, usuario.id)
        return jsonify({"ok": True, "missions": missions})
    finally:
        db.close()


@app.route('/api/miniapp/achievements')
def miniapp_achievements():
    """Retorna conquistas desbloqueadas e bônus permanentes do usuário."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        rows = db.query(UserAchievement).filter(UserAchievement.id_usuario == usuario.id).order_by(UserAchievement.unlocked_at.desc()).all()
        achievements = []
        total_multiplier = 0.0
        for row in rows:
            total_multiplier += float(row.permanent_multiplier or 0.0)
            achievements.append({
                "achievement_key": row.achievement_key,
                "name": row.achievement_name,
                "description": row.achievement_description,
                "xp_reward": int(row.xp_reward or 0),
                "permanent_multiplier": float(row.permanent_multiplier or 0.0),
                "unlocked_at": row.unlocked_at.isoformat() if row.unlocked_at else None,
            })

        return jsonify({"ok": True, "achievements": achievements, "total_permanent_multiplier": total_multiplier})
    finally:
        db.close()


@app.route('/api/miniapp/ranking-monthly')
def miniapp_ranking_monthly():
    """Ranking mensal em tempo real por XP ganho no mês corrente."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    db = next(get_db())
    try:
        month_start, month_end = _get_month_bounds()
        rows = (
            db.query(
                Usuario.nome_completo,
                Usuario.telegram_id,
                Usuario.xp,
                func.sum(XpEvent.xp_gained).label('monthly_xp'),
                func.count(XpEvent.id).label('interactions'),
            )
            .join(XpEvent, XpEvent.id_usuario == Usuario.id)
            .filter(XpEvent.created_at >= month_start)
            .filter(XpEvent.created_at <= month_end)
            .group_by(Usuario.id)
            .order_by(desc('monthly_xp'), desc('interactions'))
            .all()
        )

        ranking = []
        for idx, row in enumerate(rows, start=1):
            nome = (row.nome_completo or "Jogador").strip() or "Jogador"
            ranking.append({
                "position": idx,
                "name": nome,
                "level": _canonical_level_from_xp(int(row.xp or 0)),
                "monthly_xp": int(row.monthly_xp or 0),
                "interactions": int(row.interactions or 0),
                "is_current_user": int(row.telegram_id or 0) == int(session["user_id"]),
            })

        return jsonify({
            "ok": True,
            "month": month_start.strftime('%m/%Y'),
            "ranking": ranking,
            "updated_at": datetime.utcnow().isoformat(),
        })
    finally:
        db.close()


@app.route('/api/miniapp/fatura-editor', methods=['GET'])
def miniapp_fatura_editor():
    """Retorna rascunho de lançamentos da fatura para edição no miniapp."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "missing_token"}), 400

    draft = get_fatura_draft(token, session["user_id"])
    if not draft:
        return jsonify({"ok": False, "error": "draft_not_found"}), 404

    payload = []
    for idx, item in enumerate(draft.get("transacoes", [])):
        data_tx = item.get("data_transacao")
        if isinstance(data_tx, datetime):
            data_iso = data_tx.date().isoformat()
        else:
            data_iso = str(data_tx)[:10]
        payload.append({
            "id": idx,
            "descricao": item.get("descricao", ""),
            "valor": float(item.get("valor", 0)),
            "data_transacao": data_iso,
        })

    return jsonify({
        "ok": True,
        "origem": draft.get("origem_label", "Fatura"),
        "conta": draft.get("conta_nome", "Cartao de Credito"),
        "transacoes": payload,
    })


@app.route('/api/miniapp/fatura-editor-pending', methods=['GET'])
def miniapp_fatura_editor_pending():
    """Consome token pendente de editor de fatura para abertura automática no miniapp."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    token = pop_pending_editor_token(session["user_id"])
    return jsonify({
        "ok": True,
        "has_pending": bool(token),
        "token": token or "",
    })


@app.route('/api/miniapp/fatura-editor-save', methods=['POST'])
def miniapp_fatura_editor_save():
    """Salva as edições dos lançamentos da fatura usando o mesmo pipeline de importação."""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    edited_rows = data.get("transacoes", [])

    if not token:
        return jsonify({"ok": False, "error": "missing_token"}), 400
    if not edited_rows:
        return jsonify({"ok": False, "error": "no_transactions"}), 400

    draft = get_fatura_draft(token, session["user_id"])
    if not draft:
        return jsonify({"ok": False, "error": "draft_not_found"}), 404

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        conta_id = int(draft.get("conta_id") or 0)
        if conta_id <= 0:
            return jsonify({"ok": False, "error": "invalid_account"}), 400

        transacoes = []
        for t in edited_rows:
            try:
                descricao = str(t.get("descricao", "")).strip()
                if not descricao:
                    continue
                valor_str = str(t.get("valor", "0")).strip()
                if "," in valor_str:
                    valor = float(valor_str.replace(".", "").replace(",", "."))
                else:
                    valor = float(valor_str)
                data_iso = str(t.get("data_transacao", "")).strip()
                data_tx = datetime.fromisoformat(data_iso)
                transacoes.append({
                    "descricao": descricao,
                    "valor": valor,
                    "data_transacao": data_tx,
                    "forma_pagamento": _normalize_forma_pagamento("Crédito"),
                    "origem": "fatura_pdf_editado",
                })
            except Exception:
                continue

        if not transacoes:
            return jsonify({"ok": False, "error": "invalid_rows"}), 400

        ok, msg, stats = _run_async(
            salvar_transacoes_generica(
                db,
                usuario,
                transacoes,
                conta_id,
                tipo_origem="fatura_pdf_editado",
            )
        )
        if not ok:
            db.rollback()
            return jsonify({"ok": False, "error": "save_failed", "message": msg}), 400

        # Só consome o rascunho após persistir com sucesso.
        pop_fatura_draft(token, session["user_id"])
        _invalidate_financial_cache(session["user_id"])

        return jsonify({
            "ok": True,
            "message": msg,
            "saved_count": int((stats or {}).get("importadas") or len(transacoes)),
        })
    except Exception:
        db.rollback()
        logger.exception("Erro ao salvar edições de fatura")
        return jsonify({"ok": False, "error": "save_failed"}), 500
    finally:
        db.close()


@app.route('/api/miniapp/gerente', methods=['POST'])
def miniapp_gerente():
    """Stub do chat do gerente para o miniapp"""
    session = _require_session()
    if not session:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "empty_prompt"}), 400

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == session["user_id"]).first()
        if not usuario:
            return jsonify({"ok": False, "error": "user_not_found"}), 404

        contexto_financeiro = _run_async(preparar_contexto_financeiro_completo(db, usuario))
        contexto_conversa = _get_miniapp_contexto_conversa(session)
        prompt_final = PROMPT_ALFREDO.format(
            user_name=usuario.nome_completo.split(' ')[0] if usuario.nome_completo else "voce",
            pergunta_usuario=prompt,
            contexto_financeiro_completo=contexto_financeiro,
            contexto_conversa=contexto_conversa,
            perfil_ia=f"\n\n# 🧠 PERFIL COMPORTAMENTAL IA\n{usuario.perfil_ia}" if usuario.perfil_ia else ""
        )

        resposta = ""
        try:
            model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
            response = model.generate_content(prompt_final)
            resposta = _sanitize_response(response.text or "")
        except Exception as gemini_error:
            logger.warning("Gemini falhou no chat do MiniApp: %s", gemini_error, exc_info=True)
            resposta_groq = _run_async(_generate_with_groq(prompt_final))
            if resposta_groq:
                resposta = _sanitize_response(resposta_groq)
            else:
                return jsonify({
                    "ok": False,
                    "error": "ai_unavailable",
                    "message": "Alfredo está temporariamente indisponível. Tente novamente em instantes.",
                }), 503

        json_match = re.search(r'(\{[\s\S]*?"funcao"[\s\S]*?\})', resposta)
        if json_match:
            try:
                dados_funcao = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                dados_funcao = None
            if isinstance(dados_funcao, dict) and dados_funcao.get("funcao") == "listar_lancamentos":
                parametros = dados_funcao.get("parametros", {})
                lancamentos = buscar_lancamentos_usuario(
                    telegram_user_id=session["user_id"],
                    **parametros
                )
                resposta = _format_lancamentos_for_chat(lancamentos)

        if not resposta:
            resposta = "Nao consegui gerar uma resposta agora. Tente novamente."

        _append_miniapp_contexto_conversa(session, prompt, resposta)

        return jsonify({
            "ok": True,
            "answer": resposta
        })
    except Exception as exc:
        logger.error("Erro inesperado no chat do MiniApp: %s", exc, exc_info=True)
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Falha ao conversar com Alfredo no momento.",
        }), 500
    finally:
        db.close()

@app.route('/api/status')
def api_status():
    """Status da API"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'analytics_enabled': analytics_available,
        'environment': 'render' if is_render else 'local'
    })

# --- APIs DE DADOS ---

@app.route('/api/realtime')
@cached(ttl=30)  # Cache de 30 segundos para dados em tempo real
def realtime_stats():
    """Métricas em tempo real com retry automático e cache"""
    if not analytics_available:
        return jsonify(get_fallback_data())
    
    def get_real_data():
        from analytics.bot_analytics_postgresql import get_session
        from sqlalchemy import text
        
        session = get_session()
        if not session:
            raise Exception("Sessão não criada")
        
        try:
            cutoff = datetime.now() - timedelta(hours=24)
            
            result = session.execute(text("""
                SELECT 
                    COUNT(DISTINCT cu.username) as users,
                    COUNT(cu.id) as commands,
                    AVG(COALESCE(cu.execution_time_ms, 0)) as avg_time,
                    (SELECT COUNT(*) FROM analytics_error_logs WHERE timestamp >= :cutoff) as errors
                FROM analytics_command_usage cu 
                WHERE cu.timestamp >= :cutoff
            """), {"cutoff": cutoff}).fetchone()
            
            if result:
                return {
                    'total_users': int(result.users or 0),
                    'total_commands': int(result.commands or 0),
                    'avg_response_time': round(float(result.avg_time or 0), 2),
                    'error_count': int(result.errors or 0),
                    'status': 'success',
                    'timestamp': datetime.now().isoformat(),
                    'cached': True
                }
            raise Exception("Sem resultados")
            
        finally:
            session.close()
    
    try:
        return jsonify(execute_with_retry(get_real_data))
    except Exception as e:
        logger.error(f"Falha ao obter dados reais: {e}")
        return jsonify(get_fallback_data())

@app.route('/api/users/active')
def active_users():
    """API para usuários ativos"""
    return jsonify({
        'active_users_24h': 8,
        'new_users_today': 2,
        'status': 'mock'
    })

@app.route('/api/commands')
def commands_stats():
    """API para comandos mais utilizados"""
    if analytics_available and is_render:
        try:
            from analytics.bot_analytics_postgresql import get_session
            from sqlalchemy import func, text
            
            session = get_session()
            if session:
                result = session.execute(text("""
                    SELECT command, COUNT(*) as count
                    FROM analytics_command_usage 
                    WHERE timestamp >= :cutoff
                    GROUP BY command 
                    ORDER BY count DESC 
                    LIMIT 10
                """), {"cutoff": datetime.now() - timedelta(days=7)}).fetchall()
                
                session.close()
                
                return jsonify({
                    'top_commands': [{'command': row.command, 'count': row.count} for row in result],
                    'status': 'success'
                })
        except Exception as e:
            logger.error(f"Erro ao obter comandos: {e}")
    
    # Mock data
    return jsonify({
        'top_commands': [
            {'command': '/start', 'count': 25},
            {'command': '/help', 'count': 18},
            {'command': '/extrato', 'count': 12},
            {'command': '/dashboard', 'count': 8}
        ],
        'status': 'mock'
    })

@app.route('/api/errors/recent')
def recent_errors():
    """API para erros recentes"""
    try:
        days = int(request.args.get('days', 3))
        
        if analytics_available and is_render:
            from analytics.bot_analytics_postgresql import get_session
            from sqlalchemy import text
            
            session = get_session()
            if session:
                errors = session.execute(text("""
                    SELECT error_type, error_message, timestamp, username, command
                    FROM analytics_error_logs 
                    WHERE timestamp >= :cutoff
                    ORDER BY timestamp DESC 
                    LIMIT 20
                """), {"cutoff": datetime.now() - timedelta(days=days)}).fetchall()
                
                session.close()
                
                return jsonify({
                    'errors': [{
                        'type': row.error_type,
                        'message': row.error_message[:100],
                        'timestamp': row.timestamp.isoformat(),
                        'user': row.username or 'N/A',
                        'command': row.command or 'N/A'
                    } for row in errors],
                    'status': 'success'
                })
        
        # Fallback
        return jsonify({
            'errors': [{
                'type': 'MockError',
                'message': 'Erro de exemplo para demonstração',
                'timestamp': datetime.now().isoformat(),
                'user': 'usuario_teste',
                'command': '/test'
            }],
            'status': 'mock'
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/performance/trends')
@cached(ttl=300)  # Cache de 5 minutos
def performance_trends():
    """API para tendências de performance"""
    try:
        # Simular dados de tendência por enquanto
        hours = []
        response_times = []
        
        for i in range(24):
            hour = (datetime.now() - timedelta(hours=i)).strftime('%H:00')
            hours.append(hour)
            # Simular variação realista de tempo de resposta
            response_times.append(200 + (i * 10) + (i % 3 * 50))
        
        return jsonify({
            'hours': list(reversed(hours)),
            'response_times': list(reversed(response_times)),
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/system/health')
def system_health():
    """API para saúde do sistema"""
    try:
        health_data = {
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': 'healthy' if analytics_available else 'unavailable',
                'cache': 'healthy',
                'api': 'healthy'
            },
            'metrics': {
                'uptime': '99.9%',
                'memory_usage': '45%',
                'cpu_usage': '12%',
                'cache_hit_rate': f"{len(_cache) * 10}%"  # Aproximação baseada no cache
            },
            'status': 'operational'
        }
        
        return jsonify(health_data)
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'})

# --- NOVOS ENDPOINTS DE MÉTRICAS AVANÇADAS ---

@app.route('/api/metrics/engagement')
@cached(ttl=900)  # Cache de 15 minutos
def user_engagement():
    """API para métricas de engajamento"""
    try:
        # Dados mock para demonstração
        engagement_data = {
            'daily_active_users': 15,
            'weekly_active_users': 45,
            'monthly_active_users': 120,
            'retention_rate_7d': 85.3,
            'retention_rate_30d': 62.1,
            'avg_session_duration': 4.2,
            'commands_per_user': 8.5,
            'engagement_score': 87.2
        }
        
        return jsonify({
            'engagement': engagement_data,
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro em metrics/engagement: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/metrics/performance')
@cached(ttl=600)  # Cache de 10 minutos
def command_performance():
    """API para performance de comandos"""
    try:
        performance_data = {
            'avg_response_time': 245.8,
            'success_rate': 98.7,
            'error_rate': 1.3,
            'throughput_per_minute': 12.5,
            'slowest_commands': [
                {'command': '/relatorio', 'avg_time_ms': 1250},
                {'command': '/dashboard', 'avg_time_ms': 890},
                {'command': '/extrato', 'avg_time_ms': 675}
            ],
            'fastest_commands': [
                {'command': '/start', 'avg_time_ms': 125},
                {'command': '/help', 'avg_time_ms': 89},
                {'command': '/status', 'avg_time_ms': 45}
            ]
        }
        
        return jsonify({
            'performance': performance_data,
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro em metrics/performance: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/metrics/kpis')
@cached(ttl=1800)  # Cache de 30 minutos
def business_kpis():
    """API para KPIs de negócio"""
    try:
        kpis_data = {
            'total_users': 150,
            'new_users_this_month': 35,
            'user_growth_rate': 30.5,
            'command_success_rate': 98.7,
            'avg_commands_per_day': 245,
            'user_satisfaction_score': 4.3,
            'system_uptime': 99.8,
            'revenue_metrics': {
                'monthly_value': 0,  # Free service
                'cost_per_user': 0.15,
                'efficiency_score': 92.1
            }
        }
        
        return jsonify({
            'kpis': kpis_data,
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro em metrics/kpis: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/trends/usage')
@cached(ttl=3600)  # Cache de 1 hora
def usage_trends():
    """API para tendências de uso"""
    try:
        # Gerar dados de tendência dos últimos 30 dias
        import random
        from datetime import timedelta
        
        trends_data = {
            'period': '30_days',
            'daily_stats': [],
            'growth_trend': 'positive',
            'peak_hours': [9, 12, 15, 18, 21],
            'top_growing_commands': [
                {'command': '/extrato', 'growth': 45.2},
                {'command': '/dashboard', 'growth': 32.1},
                {'command': '/relatorio', 'growth': 28.5}
            ]
        }
        
        # Simular 30 dias de dados
        for i in range(30):
            date = datetime.now() - timedelta(days=29-i)
            base_usage = 20 + (i * 0.5)  # Tendência crescente
            daily_variation = random.uniform(0.8, 1.2)
            
            trends_data['daily_stats'].append({
                'date': date.strftime('%Y-%m-%d'),
                'total_commands': int(base_usage * daily_variation),
                'active_users': int((base_usage * daily_variation) / 3),
                'error_rate': round(random.uniform(0.5, 2.5), 1)
            })
        
        return jsonify({
            'trends': trends_data,
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro em trends/usage: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/cache/stats')
def cache_stats():
    """API para estatísticas do cache"""
    try:
        total_keys = len(_cache)
        cache_info = {
            'total_keys': total_keys,
            'cache_ttl': CACHE_TTL,
            'memory_usage': f'{total_keys * 0.1:.1f}KB',
            'hit_rate': f'{min(95, total_keys * 2)}%'
        }
        
        return jsonify({
            'cache': cache_info,
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'})

# Endpoints adicionais que o frontend espera
@app.route('/api/commands/ranking')
def commands_ranking():
    """API para ranking de comandos mais usados"""
    try:
        days = request.args.get('days', 7, type=int)
        
        # Mock data para ranking de comandos
        ranking_data = [
            {'command': '/extrato', 'count': 45, 'percentage': 25.0},
            {'command': '/adicionar', 'count': 38, 'percentage': 21.1},
            {'command': '/relatorio', 'count': 32, 'percentage': 17.8},
            {'command': '/metas', 'count': 28, 'percentage': 15.6},
            {'command': '/start', 'count': 22, 'percentage': 12.2},
            {'command': '/help', 'count': 15, 'percentage': 8.3}
        ]
        
        return jsonify({
            'ranking': ranking_data,
            'period_days': days,
            'total_commands': sum(item['count'] for item in ranking_data),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Erro no ranking de comandos: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/errors/detailed')
def errors_detailed():
    """API para erros detalhados"""
    try:
        days = request.args.get('days', 7, type=int)
        
        # Mock data para erros detalhados
        errors_data = [
            {
                'id': 1,
                'timestamp': (datetime.now() - timedelta(hours=2)).isoformat(),
                'error_type': 'ValidationError',
                'message': 'Formato de valor inválido',
                'command': '/adicionar',
                'user_id': 'user_123',
                'severity': 'medium'
            },
            {
                'id': 2,
                'timestamp': (datetime.now() - timedelta(hours=5)).isoformat(),
                'error_type': 'NetworkError',
                'message': 'Timeout na conexão com banco',
                'command': '/extrato',
                'user_id': 'user_456',
                'severity': 'high'
            },
            {
                'id': 3,
                'timestamp': (datetime.now() - timedelta(days=1)).isoformat(),
                'error_type': 'AuthError',
                'message': 'Token expirado',
                'command': '/metas',
                'user_id': 'user_789',
                'severity': 'low'
            }
        ]
        
        return jsonify({
            'errors': errors_data,
            'period_days': days,
            'total_errors': len(errors_data),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint errors_detailed: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/performance/metrics')
def performance_metrics():
    """API para métricas de performance"""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        # Mock data para métricas de performance
        metrics_data = {
            'response_times': {
                'avg_ms': 145,
                'max_ms': 320,
                'min_ms': 45,
                'p95_ms': 280
            },
            'throughput': {
                'requests_per_hour': 42,
                'commands_per_hour': 38,
                'errors_per_hour': 2
            },
            'system_health': {
                'cpu_usage': 15.2,
                'memory_usage': 62.5,
                'uptime_hours': 48.3
            },
            'trends': [
                {'time': '00:00', 'response_time': 120, 'throughput': 35},
                {'time': '04:00', 'response_time': 110, 'throughput': 28},
                {'time': '08:00', 'response_time': 130, 'throughput': 45},
                {'time': '12:00', 'response_time': 150, 'throughput': 52},
                {'time': '16:00', 'response_time': 145, 'throughput': 48},
                {'time': '20:00', 'response_time': 135, 'throughput': 42}
            ]
        }
        
        return jsonify({
            'metrics': metrics_data,
            'period_hours': hours,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Erro nas métricas de performance: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/config/status')
def config_status():
    """API para status das configurações do sistema"""
    try:
        import config
        
        # Verificar status das variáveis críticas
        env_status = {
            'TELEGRAM_TOKEN': '✅ Configurado' if config.TELEGRAM_TOKEN else '❌ Não configurado',
            'GEMINI_API_KEY': '✅ Configurado' if config.GEMINI_API_KEY else '❌ Não configurado',  
            'PIX_KEY': '✅ Configurado' if config.PIX_KEY else '❌ Não configurado',
            'EMAIL_HOST_PASSWORD': '✅ Configurado' if config.EMAIL_HOST_PASSWORD else '❌ Não configurado',
            'DATABASE_URL': '✅ Configurado' if config.DATABASE_URL else '❌ Não configurado'
        }
        
        # Calcular % de configuração
        configured = sum(1 for status in env_status.values() if '✅' in status)
        total = len(env_status)
        config_percentage = round((configured / total) * 100)
        
        # Determinar status geral
        if config_percentage == 100:
            overall_status = 'complete'
            status_message = '🎉 Sistema 100% configurado'
        elif config_percentage >= 80:
            overall_status = 'mostly_complete'  
            status_message = '⚠️ Quase completo - algumas funcionalidades limitadas'
        elif config_percentage >= 40:
            overall_status = 'partial'
            status_message = '📊 Configuração parcial - modo demo ativo'
        else:
            overall_status = 'demo'
            status_message = '🏠 Modo demo - configure variáveis de ambiente'
        
        return jsonify({
            'environment_variables': env_status,
            'configuration_percentage': config_percentage,
            'overall_status': overall_status,
            'status_message': status_message,
            'is_production': bool(os.environ.get('RENDER_SERVICE_NAME')),
            'recommendations': [
                'Configure TELEGRAM_TOKEN para ativar o bot',
                'Configure GEMINI_API_KEY para IA funcionar', 
                'Configure PIX_KEY para pagamentos',
                'Configure EMAIL_* para notificações'
            ] if config_percentage < 100 else ['Sistema totalmente configurado! 🎉']
        })
        
    except Exception as e:
        logger.error(f"Erro no status de configuração: {e}")
        return jsonify({'error': str(e), 'status': 'error'})

@app.route('/api/analytics_debug')
def analytics_debug():
    """Endpoint de debug rápido: contagens brutas das tabelas de analytics (se disponíveis)."""
    info = {"status": "ok"}
    if not analytics_available:
        info["analytics_available"] = False
        return jsonify(info)
    try:
        from analytics.bot_analytics_postgresql import get_session
        from sqlalchemy import text
        session = get_session()
        if not session:
            info["error"] = "session_none"
            return jsonify(info)
        try:
            cmd = session.execute(text("SELECT COUNT(*) FROM analytics_command_usage"))
            info["command_usage_count"] = int(cmd.scalar() or 0)
        except Exception as e:
            info["command_usage_error"] = str(e)
        try:
            err = session.execute(text("SELECT COUNT(*) FROM analytics_error_logs"))
            info["error_logs_count"] = int(err.scalar() or 0)
        except Exception as e:
            info["error_logs_error"] = str(e)
        finally:
            session.close()
    except Exception as e:
        info["fatal"] = str(e)
    return jsonify(info)

@app.route('/api/miniapp/toggle-notificacoes', methods=['POST'])
def toggle_notificacoes():
    """
    Endpoint para o MiniApp ativar/desativar as notificações automáticas do usuário.
    Espera um JSON: {"telegram_id": 123456789, "ativo": true/false}
    """
    logger.info("⚡ Recebida requisição para alterar status das notificações automáticas.")
    dados = request.get_json(silent=True) or {}
    telegram_id = dados.get('telegram_id')
    ativo = dados.get('ativo')

    if telegram_id is None or ativo is None:
        return jsonify({"erro": "telegram_id e ativo são obrigatórios"}), 400

    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == telegram_id).first()
        if not usuario:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        usuario.alerta_gastos_ativo = bool(ativo)
        db.commit()

        status_msg = "ligadas" if ativo else "desligadas"
        return jsonify({
            "sucesso": True, 
            "mensagem": f"Notificações {status_msg} com sucesso!",
            "estado_atual": usuario.alerta_gastos_ativo
        })
    except Exception as e:
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

# --- WEBHOOK MERCADO PAGO ---
from flask import request
from gerente_financeiro.monetization import PLAN_PREMIUM_MONTHLY, PLAN_PREMIUM_ANNUAL, PLAN_PRICES
from gerente_financeiro.monetization import get_db, get_or_create_user, ensure_user_plan_state
import logging

@app.route('/webhook_mercadopago', methods=['POST'])
def webhook_mercadopago():
    data = request.json or {}
    topic = data.get('topic') or data.get('type')
    if topic not in ('payment', 'merchant_order'):  # só processa pagamentos
        return {"status": "ignored"}
    # Buscar info do pagamento
    payment = data.get('data', {}).get('id') or data.get('id')
    if not payment:
        return {"status": "no_payment_id"}
    # Buscar detalhes do pagamento via API Mercado Pago (opcional, pode confiar no webhook se preferir)
    # Aqui, assume que o external_reference é o user_id
    user_id = None
    try:
        user_id = int(data.get('data', {}).get('external_reference') or data.get('external_reference'))
    except Exception:
        pass
    if not user_id:
        return {"status": "no_user_id"}
    plano = None
    valor = float(data.get('data', {}).get('transaction_amount') or 0)
    if abs(valor - PLAN_PRICES[PLAN_PREMIUM_MONTHLY]) < 0.1:
        plano = PLAN_PREMIUM_MONTHLY
    elif abs(valor - PLAN_PRICES[PLAN_PREMIUM_ANNUAL]) < 0.1:
        plano = PLAN_PREMIUM_ANNUAL
    else:
        return {"status": "invalid_amount"}
    # Ativar plano premium
    db = next(get_db())
    user = get_or_create_user(db, user_id, None)
    ensure_user_plan_state(db, user, commit=True)
    user.plan = plano
    # premium_expires_at: 1 mês ou 1 ano
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    if plano == PLAN_PREMIUM_MONTHLY:
        user.premium_expires_at = now + timedelta(days=31)
    else:
        user.premium_expires_at = now + timedelta(days=366)
    db.add(user)
    db.commit()
    logging.info(f"✅ Usuário {user_id} ativado no plano {plano} via Mercado Pago!")
    return {"status": "ok", "user_id": user_id, "plan": plano}

if __name__ == '__main__':
    # Configurar servidor
    port = int(os.environ.get('PORT', 5000))
    debug_mode = not is_render
    
    logger.info(f"🌐 Dashboard iniciando em 0.0.0.0:{port}")
    logger.info(f"📁 Template dir: {template_dir}")
    logger.info(f"📁 Static dir: {static_dir}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=False
    )
