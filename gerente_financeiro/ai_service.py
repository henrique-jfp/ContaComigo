import logging
import json
import asyncio
import re
import requests
import google.generativeai as genai
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)

# Lista global de ferramentas suportadas
_ALFREDO_TOOLS_NAMES = {
    "registrar_lancamento", "agendar_despesa", "agendar_receita", "criar_meta", 
    "criar_lembrete", "responder_duvida_financeira", "definir_limite_orcamento", "categorizar_lancamentos_pendentes",
    "consultar_saldos_bancarios_reais", "consultar_faturas_cartao_real", "consultar_livro_caixa_analitico"
}

def _groq_chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    api_key = str(config.GROQ_API_KEY).strip().strip("'\"").strip()
    
    payload = {
        "model": config.GROQ_MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    try:
        response.raise_for_status()
    except Exception as e:
        logger.error(f"[GROQ] Erro API: {response.text}")
        raise e
    return response.json()

async def _groq_chat_completion_async(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict:
    max_retries = 1
    for attempt in range(max_retries + 1):
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _groq_chat_completion, messages, tools, tool_choice)
        except Exception as e:
            if "429" in str(e) and attempt < max_retries:
                wait_time = (attempt + 1) * 2
                logger.warning(f"⚠️ Groq Rate Limit (429). Aguardando {wait_time}s antes da tentativa {attempt + 2}...")
                await asyncio.sleep(wait_time)
                continue
            raise

async def _gemini_chat_completion_async(messages: list[dict], tools: list[dict] | None = None) -> str | None:
    """Fallback para análise usando Gemini se o Groq/Cerebras falharem."""
    if not config.GEMINI_API_KEY:
        return None
    
    api_key = str(config.GEMINI_API_KEY).strip().strip("'\"").strip()
    
    max_retries = 1
    for attempt in range(max_retries + 1):
        try:
            model_name = config.GEMINI_MODEL_NAME or "gemini-1.5-flash"
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            prompt_parts = []
            
            # Se houver tools, injeta a definição no início do prompt para o Gemini saber o que chamar
            if tools:
                tools_desc = "\n".join([f"- {t['function']['name']}: {t['function']['description']}" for t in tools])
                prompt_parts.append(f"SYSTEM: Você tem acesso às seguintes FERRAMENTAS financeiras. Se precisar realizar uma ação (como criar meta, lembrete ou agendamento), você DEVE retornar um JSON no formato: {{\"function\": {{\"name\": \"nome_da_funcao\", \"arguments\": {{\"param1\": \"valor1\"}}}}}}. \n\nFERRAMENTAS DISPONÍVEIS:\n{tools_desc}")
            for m in messages:
                role_raw = m.get("role", "system")
                content = m.get("content") or ""
                
                if role_raw == "user":
                    role = "User"
                elif role_raw == "assistant":
                    role = "Assistant"
                    if not content and m.get("tool_calls"):
                        t_calls = m.get("tool_calls", [])
                        content = f"[Chamando ferramenta: {t_calls[0].get('function', {}).get('name')}]"
                elif role_raw == "tool":
                    role = "Tool Result"
                else:
                    role = "System"
                
                prompt_parts.append(f"{role}: {content}")
            
            full_prompt = "\n\n".join(prompt_parts)
            
            response = await model.generate_content_async(full_prompt)
            if response and response.text:
                return response.text
            return None
        except Exception as e:
            if "429" in str(e) and attempt < max_retries:
                logger.warning(f"⚠️ Gemini Rate Limit (429). Aguardando 2s para retry...")
                await asyncio.sleep(2)
                continue
            logger.error(f"Falha no fallback Gemini: {e}")
            return None

async def _cerebras_chat_completion_async(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict:
    if not config.CEREBRAS_API_KEY:
        raise RuntimeError("CEREBRAS_API_KEY nao configurada")

    api_key = str(config.CEREBRAS_API_KEY).strip().strip("'\"").strip()

    payload = {
        "model": config.CEREBRAS_MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
    def _call():
        response = requests.post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except Exception as e:
            logger.error(f"[CEREBRAS] Erro API: {response.text}")
            raise e
        return response.json()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call)

async def _openrouter_chat_completion_async(messages: list[dict]) -> str | None:
    """Acesso ao OpenRouter para modelos gratuitos e triagem."""
    if not config.OPENROUTER_API_KEY:
        return None

    api_key = str(config.OPENROUTER_API_KEY).strip().strip("'\"").strip()
    # Forçamos o uso de um modelo gratuito altamente disponível se o config estiver no padrão antigo
    model = config.OPENROUTER_MODEL_NAME or "meta-llama/llama-3.1-8b-instruct:free"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 500,
    }
    
    def _call():
        # URL sem espaços ou caracteres ocultos
        target_url = "https://openrouter.ai/api/v1/chat/completions".strip()
        response = requests.post(
            target_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://contacomigo.henriquedejesus.dev",
                "X-OpenRouter-Title": "ContaComigo Alfredo"
            },
            json=payload,
            timeout=25
        )
        if response.status_code != 200:
            logger.error(f"❌ [OpenRouter] Erro {response.status_code}: {response.text}")
        response.raise_for_status()
        return response.json()

    try:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, _call)
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"❌ [OpenRouter] Falha: {e}")
        return None

async def _openrouter_triagem_rapida_async(texto_usuario: str) -> str | None:
    """
    Atua como o 'Porteiro' do Alfredo usando modelos de elite gratuitos de 2026.
    Retorna JSON de ferramenta ou 'COMPLEXO'.
    """
    if not config.OPENROUTER_API_KEY:
        return None

    prompt_triagem = f"""Você é o classificador do Alfredo. Analise a frase do usuário.

OBJETIVO:
1. Se for um REGISTRO de gasto ou receita simples (ex: "almoço 35", "gasolina 100", "recebi 200"), extraia os dados e responda EXATAMENTE um JSON de ferramenta registrar_lancamento.
2. Se for uma pergunta, dúvida, pedido de análise ou algo que exija olhar o histórico, responda APENAS a palavra: COMPLEXO

REGRAS JSON:
- descricao: o que foi comprado (Capitalize)
- valor: numero (ex: 35.50)
- categoria: Alimentação, Transporte, Lazer, Saúde ou Outros.
- forma_pagamento: Pix, Crédito ou Nao_informado.

FRASE: "{texto_usuario}"
RESPOSTA:"""

    messages = [{"role": "user", "content": prompt_triagem}]
    
    # Lista de ELITE Free REAL de 2026 (Focada em VELOCIDADE para evitar timeout)
    modelos_elite_2026 = [
        "liquid/lfm-2.5-1.2b-instruct:free", # Ultra-rápido, ideal para triagem
        "nvidia/nemotron-3-super-120b-a12b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "openrouter/free" 
    ]
    
    for model in modelos_elite_2026:
        # Armazena o modelo original para restaurar depois
        orig_model = config.OPENROUTER_MODEL_NAME
        try:
            config.OPENROUTER_MODEL_NAME = model
            res = await _openrouter_chat_completion_async(messages)
            if res and ("registrar_lancamento" in res or "COMPLEXO" in res):
                return res
        except Exception as e:
            # Se der 404 (endpoint sumiu) ou 429 (cota), tenta o próximo modelo de elite
            if "404" in str(e) or "429" in str(e):
                logger.warning(f"⚠️ Modelo {model} indisponível no OpenRouter. Tentando próximo da elite...")
                continue
            break
        finally:
            config.OPENROUTER_MODEL_NAME = orig_model
            
    return None

async def _smart_ai_completion_async(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict | str | None:
    """
    Orquestrador Inteligente de Provedores de IA com Backoff.
    Ordem: Cerebras (Velocidade) -> Groq (Resiliência) -> Gemini (Fallback)
    """
    def _truncar_mensagens(msgs):
        new_msgs = [m.copy() for m in msgs]
        for m in new_msgs:
            # Cerebras/Groq têm limites entre 6k-8k. Truncamos agressivamente se falhar.
            if m.get("role") == "system" and len(m.get("content", "")) > 5000:
                m["content"] = m["content"][:5000] + "... [Contexto truncado]"
            if m.get("role") == "tool" and len(m.get("content", "")) > 8000:
                m["content"] = m["content"][:8000] + "... [Dados truncados]"
            if m.get("role") == "user" and len(m.get("content", "")) > 2000:
                m["content"] = m["content"][:2000] + "... [Msg truncada]"
        return new_msgs

    providers = []
    if config.GEMINI_API_KEY:
        providers.append(("GEMINI", _gemini_chat_completion_async))
    if config.CEREBRAS_API_KEY:
        providers.append(("CEREBRAS", _cerebras_chat_completion_async))
    if config.GROQ_API_KEY:
        providers.append(("GROQ", _groq_chat_completion_async))

    last_error = None
    for attempt, (name, fn) in enumerate(providers):
        try:
            logger.info(f"⚡ [AI] Tentando {name} (tentativa {attempt+1})...")
            if name == "GEMINI":
                return await fn(messages, tools=tools)
            else:
                return await fn(messages, tools, tool_choice)
        except Exception as e:
            last_error = e
            wait = min(2 ** attempt, 8)
            # Se for erro de cota (429), não reduzimos contexto, apenas tentamos o próximo se houver
            if "429" in str(e):
                logger.warning(f"⚠️ [{name}] Cota esgotada ou limite de velocidade (429).")
                # Se ainda houver outros provedores, tenta o próximo sem esperar muito
                if attempt < len(providers) - 1:
                    logger.info(f"🔄 Tentando próximo provedor devido a limite de cota...")
                    continue 
            elif "413" in str(e) or "400" in str(e):
                logger.warning(f"⚠️ [{name}] Erro de Payload. Reduzindo contexto...")
                messages = _truncar_mensagens(messages)
            else:
                logger.error(f"❌ [{name}] Falha técnica: {e}")
            
            if attempt < len(providers) - 1:
                await asyncio.sleep(wait)

    if last_error:
        logger.error(f"🚨 [AI] Todos os provedores falharam. Último erro: {last_error}")
    return None

async def _groq_transcribe_voice_async(voice_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    def _call():
        files = {"file": ("voice.ogg", voice_bytes, mime_type)}
        data = {"model": "whisper-large-v3-turbo", "response_format": "json", "language": "pt"}
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            files=files,
            data=data,
            timeout=60,
        )
        response.raise_for_status()
        return (response.json() or {}).get("text", "").strip()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call)

def _extrair_tool_calls_do_texto(content: str) -> list[dict]:
    """Extrai múltiplas chamadas de função de uma string, suportando JSON aninhado de forma robusta."""
    tool_calls = []
    
    # Encontra todos os possíveis inícios de JSON
    for match in re.finditer(r'\{', content):
        start_idx = match.start()
        balance = 0
        end_idx = -1
        
        # Percorre para encontrar o fechamento correspondente (suporta aninhamento)
        for i in range(start_idx, len(content)):
            if content[i] == '{':
                balance += 1
            elif content[i] == '}':
                balance -= 1
                if balance == 0:
                    end_idx = i + 1
                    break
        
        if end_idx != -1:
            bloco = content[start_idx:end_idx]
            try:
                # Limpeza básica de caracteres que a IA costuma colocar ao redor
                bloco_limpo = bloco.strip().strip(';').strip()
                obj = json.loads(bloco_limpo)
                
                fn_name = None
                args = {}

                if isinstance(obj, dict):
                    if "name" in obj and ("parameters" in obj or "arguments" in obj):
                        fn_name = obj["name"]
                        args = obj.get("parameters") or obj.get("arguments")
                    elif "function" in obj and isinstance(obj["function"], dict):
                        fn_name = obj["function"].get("name")
                        args = obj["function"].get("arguments") or obj["function"].get("parameters")
                    elif "type" in obj and obj.get("type") == "function" and "function" in obj:
                        fn_name = obj["function"].get("name")
                        args = obj["function"].get("arguments") or obj["function"].get("parameters")
                    elif len(obj) == 1 and list(obj.keys())[0] in _ALFREDO_TOOLS_NAMES:
                        fn_name = list(obj.keys())[0]
                        args = obj[fn_name]
                
                if fn_name:
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: pass
                    
                    tool_calls.append({
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": json.dumps(args) if isinstance(args, dict) else str(args)
                        }
                    })
            except:
                continue
    return tool_calls

def _contem_tool_call_json(texto: str) -> bool:
    """Detecta se o texto contém um JSON de chamada de função que não foi processado."""
    indicadores = [
        '"type": "function"', 
        '"name": "registrar_lancamento"', 
        '"name": "responder_duvida_financeira"',
        '"name": "consultar_faturas_cartao_real"',
        '"name": "consultar_livro_caixa_analitico"',
        '"name": "agendar_receita"',
        '"name": "agendar_despesa"',
        '"name": "criar_lembrete"',
        '"name": "criar_meta"',
        '"name": "definir_limite_orcamento"',
        '"name": "consultar_historico_financeiro"'
    ]
    return any(ind in texto for ind in indicadores)
