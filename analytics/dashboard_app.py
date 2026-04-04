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
import uuid
import asyncio
import re
from urllib.parse import parse_qsl
from functools import wraps
from sqlalchemy import and_
from flask import Flask, render_template, jsonify, request, g
from datetime import datetime, timedelta, date

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache simples em memória (para substituir Redis em ambiente local)
_cache = {}
CACHE_TTL = 300  # 5 minutos
_miniapp_sessions = {}
MINIAPP_SESSION_TTL = 60 * 60

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
from models import Usuario, Lancamento, Agendamento, Objetivo
from gerente_financeiro.prompts import PROMPT_ALFREDO
from gerente_financeiro.services import preparar_contexto_financeiro_completo
import google.generativeai as genai

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
    secret_key = hashlib.sha256(config.TELEGRAM_TOKEN.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(received_hash, calculated_hash):
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


def _create_miniapp_session(user_id: int) -> dict:
    session_id = str(uuid.uuid4())
    _miniapp_sessions[session_id] = {
        "user_id": user_id,
        "expires_at": datetime.utcnow() + timedelta(seconds=MINIAPP_SESSION_TTL),
    }
    return {
        "session_id": session_id,
        "expires_in": MINIAPP_SESSION_TTL,
    }


def _get_session(session_id: str) -> dict | None:
    if not session_id:
        return None
    session = _miniapp_sessions.get(session_id)
    if not session:
        return None
    if session["expires_at"] < datetime.utcnow():
        _miniapp_sessions.pop(session_id, None)
        return None
    return session


def _require_session() -> dict | None:
    session_id = request.headers.get("X-Session-Id")
    return _get_session(session_id)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


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


def _format_lancamentos_for_chat(lancamentos: list) -> str:
    if not lancamentos:
        return "Nao encontrei lancamentos com esses criterios."
    lines = ["<b>Seus lancamentos</b>"]
    for lanc in lancamentos:
        data = lanc.data_transacao.strftime('%d/%m/%Y')
        valor = float(lanc.valor)
        prefix = '-' if lanc.tipo == 'Saída' else '+'
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


@app.route('/webapp')
def miniapp_shell():
    """Shell do miniapp Telegram"""
    return render_template('miniapp.html')


@app.route('/api/telegram/auth', methods=['POST'])
def telegram_auth():
    """Valida initData do Telegram Web App e cria uma sessao"""
    payload = request.get_json(silent=True) or {}
    init_data = payload.get("init_data") or ""
    user = _validate_telegram_init_data(init_data)
    if not user:
        return jsonify({"ok": False, "error": "invalid_init_data"}), 401

    session_data = _create_miniapp_session(user.get("id"))
    return jsonify({
        "ok": True,
        "user": {
            "id": user.get("id"),
            "first_name": user.get("first_name"),
            "username": user.get("username"),
        },
        **session_data,
    })


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
            base_query = base_query.filter(Lancamento.tipo == tipo)
        if start_date:
            base_query = base_query.filter(Lancamento.data_transacao >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            base_query = base_query.filter(Lancamento.data_transacao <= datetime.combine(end_date, datetime.max.time()))

        total = base_query.count()
        lancamentos = (
            base_query.order_by(Lancamento.data_transacao.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        itens = [
            {
                "id": lanc.id,
                "descricao": lanc.descricao,
                "valor": float(lanc.valor),
                "tipo": lanc.tipo,
                "data": lanc.data_transacao.isoformat(),
                "forma_pagamento": lanc.forma_pagamento,
            }
            for lanc in lancamentos
        ]

        return jsonify({"ok": True, "items": itens, "total": total, "offset": offset})
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
            return jsonify({"ok": True})

        payload = request.get_json(silent=True) or {}
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
            setattr(lancamento, key, value)

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
        return jsonify({"ok": True})
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
        prompt_final = PROMPT_ALFREDO.format(
            user_name=usuario.nome_completo.split(' ')[0] if usuario.nome_completo else "voce",
            pergunta_usuario=prompt,
            contexto_financeiro_completo=contexto_financeiro,
            contexto_conversa="",
            perfil_ia=f"\n\n# 🧠 PERFIL COMPORTAMENTAL IA\n{usuario.perfil_ia}" if usuario.perfil_ia else ""
        )

        model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        response = model.generate_content(prompt_final)
        resposta = _sanitize_response(response.text or "")

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

        return jsonify({
            "ok": True,
            "answer": resposta
        })
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