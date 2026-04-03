"""
ContaComigo Analytics Module
Sistema de analytics e monitoramento para o bot Telegram
"""

__version__ = "1.0.0"
__author__ = "ContaComigo Team"

from .bot_analytics import BotAnalytics, analytics, track_command

__all__ = [
    'BotAnalytics',
    'analytics', 
    'track_command'
]
