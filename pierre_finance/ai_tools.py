from .client import PierreClient

def obter_tools_pierre():
    """Retorna as definições de tools do Groq para o Open Finance."""
    return [
        {
            "type": "function",
            "function": {
                "name": "consultar_saldos_bancarios_reais",
                "description": "Consulta o saldo atual em tempo real das contas bancárias e cartões de crédito reais do usuário conectados via Open Finance.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_extrato_bancario_real",
                "description": "Consulta o extrato e histórico de transações reais do usuário nas suas contas conectadas via Open Finance.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Número de transações para retornar (padrão 10)"
                        }
                    },
                    "required": []
                }
            }
        }
    ]

def executar_tool_pierre(tool_name: str, arguments: dict, api_key: str) -> str:
    """Executa a chamada da tool real do Pierre."""
    client = PierreClient(api_key)
    
    if tool_name == "consultar_saldos_bancarios_reais":
        resultado = client.get_accounts()
        return str(resultado)
    
    elif tool_name == "consultar_extrato_bancario_real":
        resultado = client.get_transactions(**arguments)
        return str(resultado)
        
    return "Tool Open Finance não encontrada."