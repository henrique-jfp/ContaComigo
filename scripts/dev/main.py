# gerente_financeiro/main.py

import json
from pathlib import Path
from prompt_manager import PromptManager, PromptConfig

def main():
    # Setup: aponta para o diretório raiz dos nossos prompts modulares
    template_path = Path(__file__).parent / "prompts"
    manager = PromptManager(template_dir=template_path)

    # --- DADOS DE EXEMPLO --- 
    mock_financial_context = {
        "receitas": {"salario": 3000, "freela": 500},
        "despesas": {"aluguel": 1000, "alimentacao": 800, "lazer": 500}
    }
    mock_conversation_history = "Na nossa última conversa, você perguntou sobre seus gastos com delivery e sugerimos reduzir em 10%."
    mock_behavioral_analysis = {"tendencia_gastos": "aumento_lazer"}

    print("\n" + "="*70)
    print("--- DEMONSTRAÇÃO DO PROMPTMANAGER --- ")
    print("="*70)

    # --- CENÁRIO 1: CHAMADA DE FUNÇÃO (PROMPT MÍNIMO) ---
    print("\n[CENÁRIO 1] Intenção: function_call (listar lançamentos)")
    config_func_call = PromptConfig(
        user_name="Ana",
        user_query="meus últimos 2 gastos com lazer",
        financial_context={},
        intent="function_call"
    )
    prompt_for_function = manager.build_prompt(config_func_call)
    print(f"Tamanho do Prompt (CENÁRIO 1 - palavras): {len(prompt_for_function.split())}")
    print("--- PROMPT GERADO (CENÁRIO 1) ---")
    print(prompt_for_function)
    print("\n" + "="*70)

    # --- CENÁRIO 2: ANÁLISE GERAL (com skills selecionadas) ---
    print("\n[CENÁRIO 2] Intenção: general_analysis (análise complexa com skills)")
    config_analysis = PromptConfig(
        user_name="João",
        user_query="Compare meus gastos de Q1 e Q2 deste ano e me dê insights.",
        financial_context=mock_financial_context,
        conversation_history=mock_conversation_history,
        intent="general_analysis",
        relevant_skills=["comparative_analysis", "proactive_insights", "strategic_questions"]
    ) # Apenas skills relevantes são carregadas
    prompt_for_analysis = manager.build_prompt(config_analysis)
    print(f"Tamanho do Prompt (CENÁRIO 2 - palavras): {len(prompt_for_analysis.split())}")
    print("--- PROMPT GERADO (CENÁRIO 2) ---")
    print(prompt_for_analysis)
    print("\n" + "="*70)

    # --- CENÁRIO 3: INSIGHT FINAL (PROMPT CURTO) ---
    print("\n[CENÁRIO 3] Intenção: insight (insights rápidos)")
    config_insight = PromptConfig(
        user_name="Maria",
        user_query="Me dê um insight rápido sobre meus gastos com alimentação este mês.",
        financial_context={},
        intent="insight"
    )
    prompt_for_insight = manager.build_prompt(config_insight)
    print(f"Tamanho do Prompt (CENÁRIO 3 - palavras): {len(prompt_for_insight.split())}")
    print("--- PROMPT GERADO (CENÁRIO 3) ---")
    print(prompt_for_insight)
    print("\n" + "="*70)

    # --- CENÁRIO 4: CONTEXTO DE CONVERSA (com histórico e análise comportamental) ---
    print("\n[CENÁRIO 4] Intenção: conversation (manter contexto da conversa)")
    config_conversation = PromptConfig(
        user_name="Pedro",
        user_query="E sobre aquilo que falamos das metas de investimento?",
        financial_context=mock_financial_context,
        conversation_history=mock_conversation_history,
        behavioral_analysis_json=mock_behavioral_analysis,
        intent="conversation"
    )
    prompt_for_conversation = manager.build_prompt(config_conversation)
    print(f"Tamanho do Prompt (CENÁRIO 4 - palavras): {len(prompt_for_conversation.split())}")
    print("--- PROMPT GERADO (CENÁRIO 4) ---")
    print(prompt_for_conversation)
    print("\n" + "="*70)

    # --- CENÁRIO 5: RELATÓRIO MENSAL ---
    print("\n[CENÁRIO 5] Intenção: monthly_report (análise de relatório mensal)")
    config_monthly_report = PromptConfig(
        user_name="Sofia",
        user_query="Gerar relatório mensal",
        financial_context={},
        intent="monthly_report",
        mes_nome="Novembro",
        ano=2023,
        receita_total=4500.0,
        despesa_total=3000.0,
        saldo_mes=1500.0,
        taxa_poupanca=33.3,
        gastos_agrupados="Alimentação (R$ 900), Lazer (R$ 600)"
    )
    prompt_for_monthly_report = manager.build_prompt(config_monthly_report)
    print(f"Tamanho do Prompt (CENÁRIO 5 - palavras): {len(prompt_for_monthly_report.split())}")
    print("--- PROMPT GERADO (CENÁRIO 5) ---")
    print(prompt_for_monthly_report)
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
