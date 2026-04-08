"""
Funções utilitárias para validação e formatação reutilizáveis
Elimina duplicações de código entre handlers
"""

import re
from decimal import Decimal, InvalidOperation
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


def validar_valor_monetario(valor_str: str) -> tuple[bool, float]:
    """
    Valida e converte string de valor monetário para float.
    
    Args:
        valor_str: String com valor (ex: "150", "R$ 150,50", "150.50")
    
    Returns:
        tuple: (is_valid: bool, valor_convertido: float)
    """
    try:
        # Remove espaços, R$, pontos de milhares
        valor_limpo = re.sub(r'[R$\s\.]', '', valor_str.strip())
        
        # Substitui vírgula por ponto
        valor_limpo = valor_limpo.replace(',', '.')
        
        # Converte para Decimal para precisão
        valor_decimal = Decimal(valor_limpo)
        
        # Verifica se é positivo
        if valor_decimal <= 0:
            return False, 0.0
            
        # Verifica se não é muito grande (> 1 bilhão)
        if valor_decimal > 1_000_000_000:
            return False, 0.0
            
        return True, float(valor_decimal)
        
    except (InvalidOperation, ValueError, AttributeError):
        return False, 0.0


def validar_descricao(descricao_str: str) -> tuple[bool, str]:
    """
    Valida e limpa descrição de transação.
    
    Args:
        descricao_str: String com descrição
    
    Returns:
        tuple: (is_valid: bool, descricao_limpa: str)
    """
    if not descricao_str or not isinstance(descricao_str, str):
        return False, ""
    
    # Remove espaços extras e quebras de linha
    descricao_limpa = re.sub(r'\s+', ' ', descricao_str.strip())
    
    # Verifica tamanho mínimo e máximo
    if len(descricao_limpa) < 2:
        return False, ""
    
    if len(descricao_limpa) > 200:
        return False, ""
    
    # Remove caracteres especiais perigosos (mas mantém acentos)
    descricao_limpa = re.sub(r'[<>{}[\]\\"|;]', '', descricao_limpa)
    
    return True, descricao_limpa


def criar_teclado_confirmar(callback_confirmar: str = "confirmar", 
                          callback_cancelar: str = "cancelar",
                          texto_confirmar: str = "✅ Confirmar",
                          texto_cancelar: str = "❌ Cancelar") -> InlineKeyboardMarkup:
    """
    Cria teclado padrão de confirmação reutilizável.
    
    Args:
        callback_confirmar: Callback data para botão confirmar
        callback_cancelar: Callback data para botão cancelar
        texto_confirmar: Texto do botão confirmar
        texto_cancelar: Texto do botão cancelar
    
    Returns:
        InlineKeyboardMarkup: Teclado com botões
    """
    keyboard = [
        [
            InlineKeyboardButton(texto_confirmar, callback_data=callback_confirmar),
            InlineKeyboardButton(texto_cancelar, callback_data=callback_cancelar)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def criar_teclado_colunas_otimizado(botoes: list, colunas: int = 2) -> list:
    """
    Versão otimizada da função criar_teclado_colunas para eliminar duplicação.
    
    Args:
        botoes: Lista de InlineKeyboardButton
        colunas: Número de colunas por linha
    
    Returns:
        list: Lista de listas (linhas do teclado)
    """
    if not botoes:
        return []
    
    return [botoes[i:i + colunas] for i in range(0, len(botoes), colunas)]


async def ask_valor_generico(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           estado_proximo: int, contexto_msg: str = None,
                           campo_contexto: str = "valor") -> int:
    """
    Função genérica para solicitar valor monetário.
    Elimina duplicação entre manual_entry_handler e agendamentos_handler.
    
    Args:
        update: Update do Telegram
        context: Context do Telegram
        estado_proximo: Próximo estado do ConversationHandler
        contexto_msg: Mensagem personalizada (opcional)
        campo_contexto: Nome do campo no context.user_data
    
    Returns:
        int: Próximo estado
    """
    if contexto_msg is None:
        contexto_msg = "💰 Digite o valor da transação:"
    
    await update.message.reply_text(
        f"{contexto_msg}\n\n"
        "📝 <i>Exemplos:</i> 150 | R$ 150,50 | 1500.00\n"
        "❌ Use /cancelar para interromper",
        parse_mode='HTML'
    )
    
    return estado_proximo


async def ask_descricao_generica(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                estado_proximo: int, contexto_msg: str = None,
                                campo_contexto: str = "descricao") -> int:
    """
    Função genérica para solicitar descrição.
    Elimina duplicação entre manual_entry_handler e agendamentos_handler.
    
    Args:
        update: Update do Telegram
        context: Context do Telegram
        estado_proximo: Próximo estado do ConversationHandler
        contexto_msg: Mensagem personalizada (opcional)
        campo_contexto: Nome do campo no context.user_data
    
    Returns:
        int: Próximo estado
    """
    if contexto_msg is None:
        contexto_msg = "📝 Digite uma descrição para a transação:"
    
    await update.message.reply_text(
        f"{contexto_msg}\n\n"
        "📝 <i>Exemplos:</i> Almoço no restaurante | Salário | Uber para casa\n"
        "❌ Use /cancelar para interromper",
        parse_mode='HTML'
    )
    
    return estado_proximo


def formatar_valor_brasileiro(valor: float) -> str:
    """
    Formata valor para padrão brasileiro com vírgula.
    
    Args:
        valor: Valor numérico
    
    Returns:
        str: Valor formatado (ex: "R$ 1.500,50")
    """
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def extrair_periodo_texto(texto: str) -> tuple[str, str]:
    """
    Extrai indicações de período de um texto.
    
    Args:
        texto: Texto com possível indicação de período
    
    Returns:
        tuple: (periodo_detectado: str, resto_do_texto: str)
    """
    texto_lower = texto.lower()
    
    periodos = {
        'este mês': 'mes_atual',
        'mês passado': 'mes_anterior', 
        'esta semana': 'semana_atual',
        'semana passada': 'semana_anterior',
        'hoje': 'hoje',
        'ontem': 'ontem',
        'últimos 30 dias': 'ultimos_30_dias',
        'últimos 7 dias': 'ultimos_7_dias'
    }
    
    for periodo_texto, periodo_codigo in periodos.items():
        if periodo_texto in texto_lower:
            resto = texto_lower.replace(periodo_texto, '').strip()
            return periodo_codigo, resto
    
    return '', texto
