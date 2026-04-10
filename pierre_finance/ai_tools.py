import json
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
                        "startDate": {
                            "type": "string",
                            "description": "Data inicial para filtro (formato YYYY-MM-DD)"
                        },
                        "endDate": {
                            "type": "string",
                            "description": "Data final para filtro (formato YYYY-MM-DD)"
                        },
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
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_faturas_passadas",
                "description": "Consulta faturas de cartão de crédito já fechadas ou vencidas.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "accountId": {
                            "type": "string",
                            "description": "ID da conta de cartão de crédito para filtrar as faturas (opcional)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_parcelamentos",
                "description": "Consulta específica das compras parceladas do usuário, vendo o passado e projetando o futuro.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "startDate": {
                            "type": "string",
                            "description": "Data inicial para filtro (formato YYYY-MM-DD)"
                        },
                        "endDate": {
                            "type": "string",
                            "description": "Data final para filtro (formato YYYY-MM-DD)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gerenciar_data_fechamento_cartao",
                "description": "Lista, cria, atualiza ou deleta a data de fechamento do cartão de crédito.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "accountId": {
                            "type": "string",
                            "description": "ID da conta do cartão"
                        },
                        "closingDay": {
                            "type": "integer",
                            "description": "Dia de fechamento do cartão (1 a 31)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_maiores_gastos",
                "description": "Mapeia as categorias mais caras de despesas no período.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "startDate": {
                            "type": "string",
                            "description": "Data inicial para análise (formato YYYY-MM-DD). Padrão: 7 dias atrás."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_livro_caixa_analitico",
                "description": "Obtém um relatório analítico consolidado gigante (Livro Caixa) com contas, transações, saldos e categorias.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "includeAllPeriods": {
                            "type": "boolean",
                            "description": "Se deve incluir dados de todos os períodos (padrão false)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "consultar_memorias_ia",
                "description": "Recupera ou adiciona memórias financeiras de longo prazo do usuário.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Mensagem do usuário para adicionar à memória (opcional)"
                        }
                    },
                    "required": []
                }
            }
        }
    ]

def executar_tool_pierre(tool_name: str, arguments: dict, api_key: str) -> any:
    """Executa a chamada da tool real do Pierre e retorna o objeto de dados."""
    client = PierreClient(api_key)

    if tool_name == "consultar_saldos_bancarios_reais":
        return client.get_accounts()

    elif tool_name == "consultar_saldo_consolidado_real":
        return client.get_balance()

    elif tool_name == "consultar_faturas_cartao_real":
        return client.get_bill_summary()

    elif tool_name == "consultar_extrato_bancario_real":
        return client.get_transactions(**arguments)

    elif tool_name == "forcar_sincronizacao_bancaria":
        return client.manual_update()

    elif tool_name == "consultar_faturas_passadas":
        return client.get_bills(account_id=arguments.get("accountId"))

    elif tool_name == "consultar_parcelamentos":
        return client.get_installments(
            start_date=arguments.get("startDate"), 
            end_date=arguments.get("endDate")
        )

    elif tool_name == "gerenciar_data_fechamento_cartao":
        return client.manage_closing_date(arguments)

    elif tool_name == "consultar_maiores_gastos":
        return client.get_expensive_categories(start_date=arguments.get("startDate"))

    elif tool_name == "consultar_livro_caixa_analitico":
        return client.get_book(include_all_periods=arguments.get("includeAllPeriods", False))

    elif tool_name == "consultar_memorias_ia":
        return client.get_memories(message=arguments.get("message"))

    return {"error": "Tool Open Finance não encontrada."}