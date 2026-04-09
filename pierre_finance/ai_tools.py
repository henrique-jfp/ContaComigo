from .client import PierreClient

def obter_tools_pierre():
    """Retorna as definições de tools do Groq para o Open Finance."""
    return [
        {
            "type": "function",
            "function": {
                "name": "consultar_saldos_bancarios_reais",
                "description": "Consulta o saldo atual em tempo real de cada conta bancária conectada individualmente.",
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
                "name": "consultar_saldo_consolidado_real",
                "description": "Retorna o saldo total somado de todas as contas bancárias e investimentos conectados via Open Finance.",
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
                "name": "consultar_faturas_cartao_real",
                "description": "Consulta o resumo da fatura atual dos cartões de crédito: limite total, disponível e valor da fatura aberta.",
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
                "description": "Consulta o extrato e histórico de transações reais do usuário nas suas contas conectadas.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Número de transações para retornar (padrão 10)"
                        },
                        "clientMessage": {
                            "type": "string",
                            "description": "Filtro em linguagem natural (ex: 'gastos com mercado')"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "forcar_sincronizacao_bancaria",
                "description": "Solicita que o Pierre Finance atualize os dados diretamente com os bancos agora mesmo.",
                "parameters": {
                    "type": "object",
                    "properties": {},
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

    elif tool_name == "consultar_saldo_consolidado_real":
        resultado = client.get_balance()
        return str(resultado)

    elif tool_name == "consultar_faturas_cartao_real":
        resultado = client.get_bill_summary()
        return str(resultado)

    elif tool_name == "consultar_extrato_bancario_real":
        resultado = client.get_transactions(**arguments)
        return str(resultado)

    elif tool_name == "forcar_sincronizacao_bancaria":
        resultado = client.manual_update()
        return str(resultado)

    return "Tool Open Finance não encontrada."