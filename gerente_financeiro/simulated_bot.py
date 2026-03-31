
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from gerente_financeiro.prompt_manager import PromptManager, PromptConfig


# --- Configuração do PromptManager para o bot simulado ---
# Assume que o diretório 'prompts' está no mesmo nível do 'simulated_bot.py'
PROMPTS_DIR = Path(__file__).parent / "prompts"
prompt_manager = PromptManager(template_dir=PROMPTS_DIR)

# --- Funções de Simulação para o Bot ---

def get_user_data(user_id: str, user_name: str) -> Dict[str, Any]:
    """
    Simula a obtenção de dados do usuário de um DB/estado.
    Você substituirá isso pela sua lógica real.
    """
    # Dados fictícios para demonstração
    financial_context = {
        "user_id": user_id,
        "user_name": user_name,
        "accounts": [{"name": "Conta Corrente", "balance": 2500.0}],
        "transactions": [
            {"description": "Uber", "amount": 45.0, "category": "Transporte"},
            {"description": "Jantar", "amount": 120.0, "category": "Alimentação"},
            {"description": "Salário", "amount": 3000.0, "category": "Receita"}
        ],
        "goals": [
            {"name": "Viagem Europa", "target": 10000.0, "current": 3500.0, "deadline": "2024-12-31"},
            {"name": "Emergência", "target": 5000.0, "current": 4800.0, "deadline": None}
        ],
    }
    conversation_history = "Na nossa última conversa, você perguntou sobre seus gastos com delivery e sugeri reduzir em 10%."
    behavioral_analysis = {"tendencia_gastos": "aumento_lazer_recente", "economia_potencial_delivery": 150}

    return {
        "financial_context": financial_context,
        "conversation_history": conversation_history,
        "behavioral_analysis_json": behavioral_analysis,
    }

def determine_user_intent(user_query: str) -> Tuple[str, Optional[Any]]: # Optional[Any] para aceitar dict ou list
    """
    SIMULA a detecção da intenção do usuário.
    Em produção, isso seria um LLM menor, embeddings + classificador, ou regex mais robusto.
    Retorna a intenção e, opcionalmente, parâmetros para function_call ou lista de skills para general_analysis.
    """
    query_lower = user_query.lower()

    if "último gasto" in query_lower or "listar" in query_lower or "detalhes" in query_lower or "transação" in query_lower:
        # Exemplo de extração de parâmetros simples (você faria isso de forma mais robusta)
        params = {"limit": 1}
        if "lazer" in query_lower:
            params["categoria_nome"] = "Lazer"
        if "alimentação" in query_lower:
            params["categoria_nome"] = "Alimentação"
        if "uber" in query_lower:
            params["query"] = "Uber"
        if "2 gastos" in query_lower:
            params["limit"] = 2
        if "3 maiores gastos" in query_lower:
            params["limit"] = 3
            if "alimentação" in query_lower:
                params["categoria_nome"] = "Alimentação"
        return "function_call", params
    
    elif "insight" in query_lower or "dica" in query_lower or "recomendaç" in query_lower or "economias" in query_lower:
        return "insight", None
    
    elif "relatório mensal" in query_lower or "resumo do mês" in query_lower or "gerar relatório" in query_lower:
        return "monthly_report", None
    
    elif "compare" in query_lower or "comparar" in query_lower:
        return "general_analysis", ["comparative_analysis", "proactive_insights"]
    
    elif any(greeting in query_lower for greeting in ["oi", "olá", "e aí", "bom dia", "boa tarde", "boa noite"]):
        return "conversation", None
    
    elif "meta de viagem" in query_lower or "minha meta" in query_lower:
         return "general_analysis", ["proactive_insights"] # Para monitorar e dar dicas sobre metas

    else:
        # Intenção padrão para análise geral com um conjunto de skills básicas
        return "general_analysis", [
            "strategic_questions",
            "proactive_insights",
            "payment_account_analysis",
            "lists_rankings",
            "period_summaries",
            "simple_predictive_analysis",
        ]

def call_llm_api_and_get_response(prompt: str, intent: str, additional_intent_data: Optional[Any]) -> str:
    """
    SIMULA a chamada à API do seu LLM (e.g., Gemini, GPT-4).
    Em produção, você faria uma requisição HTTP real aqui.
    """
    print(f"\n--- CHAMANDO O LLM COM ESTE PROMPT (Truncado para leitura, {len(prompt.split())} palavras) ---")
    print(prompt[:1000] + "\n... (fim do prompt)\n") # Imprime apenas o começo para não poluir

    # --- Lógica de Resposta Simulada APRIMORADA ---
    if intent == "function_call":
        # Se a intenção é function_call, o LLM deve retornar APENAS o JSON.
        # Simulamos que ele faria isso usando os additional_intent_data (os parâmetros)
        func_name = "listar_lancamentos"
        params_str = json.dumps(additional_intent_data, indent=2)
        return f"DEBUG: LLM respondeu com JSON para {func_name}: {{ \"funcao\": \"{func_name}\", \"parametros\": {params_str} }}"

    # Respostas simuladas baseadas em palavras-chave no prompt (substitua pela lógica real do LLM)
    if "último gasto" in prompt.lower() or "listar lançamentos" in prompt.lower():
        return "DEBUG: Analisado pelo LLM: Seu último gasto foi <code>R$ 45,00</code> com <i>Uber</i> em <i>Transporte</i>. Que tal explorar alternativas de transporte mais econômicas em dias específicos? 💡"
    elif "compare" in prompt.lower():
        return "DEBUG: Analisado pelo LLM: <b>📊 Comparativo de Gastos (Q1 vs Q2)</b>\n• Seus gastos em Alimentação aumentaram <i>15%</i> no Q2, totalizando <code>R$ 1.200,00</code>. \n• <b>💡 Insight:</b> Percebo que seus gastos com refeições fora de casa foram o principal motor. Que tal planejar 2-3 refeições caseiras por semana para economizar? 🍳"
    elif "insight" in prompt.lower():
        return "DEBUG: Analisado pelo LLM: 💡 <b>Insights do Maestro</b>\nVocê tem uma excelente disciplina! Sua meta de <i>Emergência</i> está quase completa. Foco total na <i>Viagem Europa</i> agora! 🚀"
    elif "olá" in prompt.lower() or "tudo bem" in prompt.lower():
        return "DEBUG: Analisado pelo LLM: Olá! Que bom ter você por aqui. Estou pronto para te ajudar a conquistar seus objetivos financeiros. Como posso te auxiliar hoje? ✨"
    elif "relatório mensal" in prompt.lower():
        return "DEBUG: Analisado pelo LLM: <b>🎯 Resumo de Novembro</b>\n• Receitas: <code>R$ 4.500,00</code>\n• Despesas: <code>R$ 3.000,00</code>\n• Saldo: <code>R$ 1.500,00</code>\n• <b>💡 Insight:</b> Sua taxa de poupança de <i>33.3%</i> é fantástica! Continue monitorando os gastos com <i>Lazer</i> para manter o ritmo. 📈"
    elif "meta de viagem" in prompt.lower():
        return "DEBUG: Analisado pelo LLM: Sua meta de <i>Viagem Europa</i> está em <code>35%</code>. Faltam <code>R$ 6.500,00</code>. Com o ritmo atual, você a alcança em 7 meses. Quer uma dica para acelerar? ✈️"
    elif "maiores gastos com alimentação" in prompt.lower():
         return "DEBUG: Analisado pelo LLM: Seus 3 maiores gastos com <i>Alimentação</i> foram: \n• Restaurante X (<code>R$ 80,00</code>)\n• Supermercado Y (<code>R$ 75,00</code>)\n• Delivery Z (<code>R$ 60,00</code>)\n Considere cozinhar mais em casa para otimizar. 🛒"
    
    return "DEBUG: Analisado pelo LLM: Sua pergunta foi processada. Estou sempre aprendendo para te dar as melhores informações financeiras! 🤔"


# --- Função Principal de Processamento de Mensagem do Bot Unificada ---

def process_user_message_unified(user_id: str, user_name: str, user_query: str) -> str:
    """
    Processa a mensagem do usuário de ponta a ponta:
    1. Obtém dados do usuário (simulado).
    2. Determina a intenção do usuário (simulado).
    3. Constrói o PromptConfig.
    4. Gera o prompt otimizado usando o PromptManager.
    5. Chama a API do LLM (simulado).
    6. Retorna a resposta final.
    """
    print(f"\n{'='*20} NOVO PEDIDO {'='*20}")
    print(f">>> Processando mensagem de {user_name} (ID: {user_id}): '{user_query}' <<<")

    # 1. Obter dados relevantes do usuário (substitua pela sua lógica real de DB/estado)
    user_data = get_user_data(user_id, user_name)
    financial_context = user_data["financial_context"]
    conversation_history = user_data["conversation_history"]
    behavioral_analysis_json = user_data["behavioral_analysis_json"]

    # 2. Determinar a intenção do usuário (substitua pela sua lógica real)
    # determine_user_intent retorna (intent_str, optional_params_or_skills_list)
    intent, additional_intent_data = determine_user_intent(user_query)
    
    print(f"Intenção detectada: '{intent}'. Dados adicionais: {additional_intent_data}")

    # 3. Preparar a configuração do prompt
    prompt_config_kwargs = {
        "user_name": user_name,
        "user_query": user_query,
        "financial_context": financial_context,
        "conversation_history": conversation_history,
        "behavioral_analysis_json": behavioral_analysis_json,
        "intent": intent,
    }

    # Adiciona dados específicos dependendo da intenção
    if intent == "general_analysis":
        prompt_config_kwargs["relevant_skills"] = additional_intent_data # additional_intent_data é a lista de skills
    elif intent == "monthly_report":
        # Em um cenário real, você buscaria ou calcularia os dados reais do relatório mensal aqui
        monthly_report_params = {
            "mes_nome": "Novembro",
            "ano": 2023,
            "receita_total": 4500.0,
            "despesa_total": 3000.0,
            "saldo_mes": 1500.0,
            "taxa_poupanca": 33.3,
            "gastos_agrupados": "Alimentação (R$ 900), Lazer (R$ 600)"
        }
        prompt_config_kwargs.update(monthly_report_params)


    prompt_config = PromptConfig(**prompt_config_kwargs)

    # 4. Construir o prompt dinamicamente
    final_prompt = prompt_manager.build_prompt(prompt_config)

    # 5. Chamar o LLM com o prompt gerado e obter a resposta simulada
    llm_response = call_llm_api_and_get_response(final_prompt, intent, additional_intent_data)

    return llm_response

# --- Execução de Exemplo para Testar o Bot Simulado ---
if __name__ == "__main__":
    print(f"\n{'#'*80}")
    print(f"{'#'*8} DEMONSTRAÇÃO DO BOT SIMULADO COM NOVO SISTEMA DE PROMPTS {'#'*8}")
    print(f"{'#'*80}\n")

    # Testes com diferentes tipos de mensagens
    test_cases = [
        ("user_001", "Alice", "Me mostre meu último gasto."),
        ("user_002", "Bruno", "Quais foram meus últimos 2 gastos com lazer?"), 
        ("user_003", "Cecília", "Me dê um insight sobre minhas economias."),
        ("user_004", "Daniel", "Olá ContaComigo, tudo bem?"),
        ("user_005", "Elaine", "Gere o relatório mensal de Novembro."),
        ("user_006", "Fábio", "Compare meus gastos de janeiro e fevereiro com transporte."),
        ("user_007", "Gustavo", "Como está minha meta de viagem?"),
        ("user_008", "Helena", "Liste meus 3 maiores gastos com alimentação."),
        ("user_009", "Ivo", "Não entendi bem o balanço do mês passado. Pode explicar?"), 
    ]

    for user_id, user_name, user_query in test_cases:
        response = process_user_message_unified(user_id, user_name, user_query)
        print(f"\n{'='*5} RESPOSTA FINAL DO BOT PARA '{user_query}' {'='*5}\n{response}\n")
        print(f"{'='*60}\n")
