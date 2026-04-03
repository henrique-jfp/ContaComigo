
from ..base import PromptBase
from schemas import PromptContext

class Prompt1(PromptBase):
    def __init__(self):
        super().__init__(
            nome='analise_financeira_geral', 
            descricao='Gera um insight rápido e inteligente sobre a saúde financeira atual do usuário.'
        )

    def executar(self, contexto: "PromptContext") -> str:
        """
        Executa uma análise financeira com base no relatório fornecido no contexto.
        """
        if not contexto.financial_report:
            return "Olá! Para que eu possa te dar um insight, preciso primeiro ter acesso aos seus dados financeiros."

        report = contexto.financial_report
        
        # --- Lógica de Análise Sofisticada ---
        
        # 1. Insight sobre a Taxa de Poupança (se houver renda)
        if report.total_income > 0:
            saving_rate = (report.balance / report.total_income) * 100
            if saving_rate > 20:
                insight = (
                    f"Excelente, {report.user_name}! Você poupou {saving_rate:.0f}% da sua renda. "
                    f"Isso está acima da média e te coloca no caminho certo para a independência financeira. 🚀"
                )
            elif saving_rate > 0:
                 insight = (
                    f"Bom trabalho, {report.user_name}! Você conseguiu poupar {saving_rate:.0f}% da sua renda. "
                    f"Que tal definirmos uma meta para chegar aos 20% no próximo mês?"
                )
            else:
                insight = (
                    f"Atenção, {report.user_name}. Suas despesas superaram sua renda este mês. "
                    f"Sua principal categoria de gasto foi '{report.top_expense_category}'. Vamos focar em otimizar isso?"
                )
        # 2. Insight para quando não há renda (foco em gastos)
        else:
            insight = (
                f"Olá, {report.user_name}. Vi que sua maior concentração de gastos foi em '{report.top_expense_category}'. "
                "Entender nossos padrões de gastos é o primeiro passo para o controle total das finanças. 💪"
            )
            
        # 3. Adicionar uma dica contextual
        dica = self._gerar_dica(report.top_expense_category)

        return f"💡 **Insight do Alfredo**\n{insight}\n\n**Dica Rápida:** {dica}"

    def _gerar_dica(self, categoria: str) -> str:
        """Gera uma dica prática baseada na categoria de maior gasto."""
        dicas_por_categoria = {
            "Alimentação": "Muitos gastos com delivery? Tente a regra de 'cozinhar 3x por semana'. Pequenas mudanças geram grandes economias.",
            "Transporte": "Seus custos com transporte estão altos. Já considerou otimizar suas rotas ou usar transporte público uma vez por semana?",
            "Lazer": "É ótimo se divertir! Para a próxima, que tal pesquisar por eventos gratuitos na sua cidade? Sempre há opções incríveis.",
            "Moradia": "Custos de moradia são fixos, mas que tal revisar suas contas de consumo? Pequenos vazamentos ou luzes acesas podem pesar no fim do mês.",
        }
        return dicas_por_categoria.get(categoria, "Revise seus pequenos gastos diários. Um café por dia pode somar centenas de reais no fim do ano!")

    # O método antigo agora é obsoleto, mas o mantemos para compatibilidade
    # durante a transição. Ele apenas chama o novo método com um contexto vazio.
    def obter_resposta(self) -> str:
        return self.executar(contexto=PromptContext(user_id=0)) # Exemplo com user_id dummy

