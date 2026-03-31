from importlib import import_module
from prompts import gerente_financeiro, analytics

class PromptManager:
    def __init__(self):
        self.prompts = {
            'gerente_financeiro': [],
            'analytics': []
        }

    def carregar_prompts(self):
        for modulo in [gerente_financeiro, analytics]:
            for nome_arquivo in dir(modulo):
                if nome_arquivo.startswith('Prompt'):
                    classe_prompt = getattr(modulo, nome_arquivo)
                    # Extrai apenas o nome do submódulo (ex: 'gerente_financeiro')
                    nome_submodulo = modulo.__name__.split('.')[-1]
                    self.prompts[nome_submodulo].append(classe_prompt())

    def obter_prompts(self, categoria=None):
        if categoria:
            return self.prompts[categoria]
        return [prompt for prompts in self.prompts.values() for prompt in prompts]


# --- PONTO DE ENTRADA E DEMONSTRAÇÃO DA NOVA ARQUITETURA ---
if __name__ == "__main__":
    from decimal import Decimal
    from datetime import datetime
    from schemas import PromptContext, FinancialReportSchema, TransactionSchema

    # 1. Criar dados de exemplo para a demonstração
    print("--- Simulando a criação de um contexto financeiro ---")
    
    transacoes_exemplo = [
        TransactionSchema(id=1, description="Salário", amount=Decimal("5000.00"), category="Renda", date=datetime.now()),
        TransactionSchema(id=2, description="Aluguel", amount=Decimal("-1500.00"), category="Moradia", date=datetime.now()),
        TransactionSchema(id=3, description="Supermercado", amount=Decimal("-800.00"), category="Alimentação", date=datetime.now()),
        TransactionSchema(id=4, description="iFood", amount=Decimal("-250.00"), category="Alimentação", date=datetime.now()),
        TransactionSchema(id=5, description="Cinema", amount=Decimal("-100.00"), category="Lazer", date=datetime.now()),
    ]
    
    relatorio_financeiro = FinancialReportSchema(
        user_name="Walter",
        transactions=transacoes_exemplo,
        total_income=Decimal("5000.00"),
        total_expense=Decimal("2650.00")
    )
    
    contexto = PromptContext(
        user_id=123,
        financial_report=relatorio_financeiro
    )
    print("Contexto criado para o usuário: Walter\n")

    # 2. Carregar os prompts usando o manager
    print("--- Carregando prompts com o PromptManager ---")
    prompt_manager = PromptManager()
    prompt_manager.carregar_prompts()
    print(f"{len(prompt_manager.obter_prompts())} prompts carregados.\n")

    # 3. Obter e executar um prompt específico
    print("--- Executando um prompt de análise financeira ---")
    # Vamos pegar o primeiro prompt da categoria 'gerente_financeiro'
    prompt_analise = prompt_manager.obter_prompts('gerente_financeiro')[0]
    
    resultado = prompt_analise.executar(contexto)
    
    # 4. Imprimir o resultado
    print("\nResultado da Execução:")
    print("="*25)
    print(resultado)
    print("="*25)

