#!/usr/bin/env python3
"""
Script para testar registro de handlers sem usar função privada
"""
import sys
sys.path.append('.')

# Carregar configurações
from secret_loader import setup_environment
setup_environment()

import config
from telegram.ext import ApplicationBuilder, CommandHandler
from gerente_financeiro.handlers import (
    create_gerente_conversation_handler,
    create_cadastro_email_conversation_handler,
    handle_analise_impacto_callback,
    help_callback,
    help_command,
    cancel,
    painel_notificacoes
)
from gerente_financeiro.agendamentos_handler import (
    agendamento_start, agendamento_conv, agendamento_menu_callback, cancelar_agendamento_callback
)
from gerente_financeiro.wishlist_handler import (
    wishlist_conv, listar_wishlist_command, deletar_meta_callback
)
from gerente_financeiro.onboarding_handler import configurar_conv
from gerente_financeiro.editing_handler import edit_conv
from gerente_financeiro.graficos import grafico_conv
from gerente_financeiro.relatorio_handler import relatorio_handler
from gerente_financeiro.manual_entry_handler import manual_entry_conv
from gerente_financeiro.contact_handler import contact_conv
from gerente_financeiro.delete_user_handler import delete_user_conv
from gerente_financeiro.dashboard_handler import (
    cmd_dashboard, cmd_dashstatus, dashboard_callback_handler
)
from gerente_financeiro.gamification_handler import show_profile, show_rankings, handle_gamification_callback
from gerente_financeiro.investment_handler import get_investment_handlers
from gerente_financeiro.assistente_proativo_handler import teste_assistente_handler
from gerente_financeiro.wrapped_anual_handler import meu_wrapped_handler

# Integração bancária removida
    # Blocos bancários removidos

def test_full_registration():
    print("🔄 Testando registro completo de handlers...")

    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    print("✅ Aplicação criada")

    # Simular _register_default_handlers
    def add(handler, name: str):
        try:
            app.add_handler(handler)
            print(f"✅ Handler {name} registrado")
        except Exception as exc:
            print(f"❌ Handler {name} falhou: {exc}")
            raise

    def build_and_add(name: str, builder):
        try:
            handler = builder()
            add(handler, name)
        except Exception as exc:
            print(f"❌ Falha ao construir {name}: {exc}")
            raise

    print("🔧 Registrando conversation handlers...")

    conversation_builders = [
        ("configurar_conv", lambda: configurar_conv),
        ("gerente_conv", create_gerente_conversation_handler),
        ("cadastro_email_conv", create_cadastro_email_conversation_handler),
        ("manual_entry_conv", lambda: manual_entry_conv),
        ("delete_user_conv", lambda: delete_user_conv),
        ("contact_conv", lambda: contact_conv),
        ("grafico_conv", lambda: grafico_conv),
        ("wishlist_conv", lambda: wishlist_conv),
        ("agendamento_conv", lambda: agendamento_conv),
        ("edit_conv", lambda: edit_conv),
    ]

    # Integração bancária removida
    # Blocos bancários removidos

    for name, builder in conversation_builders:
        build_and_add(name, builder)

    print("🔧 Registrando command handlers...")

    command_builders = [
        ("relatorio_handler", lambda: relatorio_handler),
        ("/help", lambda: CommandHandler("help", help_command)),
        ("/alerta", lambda: CommandHandler("alerta", lambda u, c: None)),  # Placeholder
        ("/metas", lambda: CommandHandler("metas", listar_wishlist_command)),
        ("/agendar", lambda: CommandHandler("agendar", agendamento_start)),
        ("/notificacoes", lambda: CommandHandler("notificacoes", painel_notificacoes)),
        ("/perfil", lambda: CommandHandler("perfil", show_profile)),
        ("/ranking", lambda: CommandHandler("ranking", show_rankings)),
        ("/dashboard", lambda: CommandHandler("dashboard", cmd_dashboard)),
        ("/dashstatus", lambda: CommandHandler("dashstatus", cmd_dashstatus)),
        ("/dashboarddebug", lambda: CommandHandler("dashboarddebug", lambda u, c: None)),  # Placeholder
        ("/debugocr", lambda: CommandHandler("debugocr", lambda u, c: None)),  # Placeholder
        ("/debuglogs", lambda: CommandHandler("debuglogs", lambda u, c: None)),  # Placeholder
        ("/teste_assistente", lambda: teste_assistente_handler),
        ("/meu_wrapped", lambda: meu_wrapped_handler),

    ]

    # Comandos bancários removidos
        # Blocos bancários removidos

    for name, builder in command_builders:
        print(f"🔧 Tentando registrar comando: {name}")
        build_and_add(name, builder)
        print(f"✅ Comando {name} registrado com sucesso")

    # Investment handlers
    try:
        print("🔧 Registrando handlers de investimentos...")
        investment_handlers = get_investment_handlers()
        for handler in investment_handlers:
            app.add_handler(handler)
        print(f"✅ {len(investment_handlers)} handlers de investimentos registrados")
    except Exception as e:
        print(f"❌ Erro ao registrar handlers de investimentos: {e}")

    # Callback handlers
    callback_builders = [
        ("help_callback", lambda: CallbackQueryHandler(help_callback, pattern="^help_")),
        ("analise_callback", lambda: CallbackQueryHandler(handle_analise_impacto_callback, pattern="^analise_")),
        ("deletar_meta_callback", lambda: CallbackQueryHandler(deletar_meta_callback, pattern="^deletar_meta_")),
        ("agendamento_menu_callback", lambda: CallbackQueryHandler(agendamento_menu_callback, pattern="^agendamento_")),
        ("cancelar_agendamento_callback", lambda: CallbackQueryHandler(cancelar_agendamento_callback, pattern="^ag_cancelar_")),
        ("gamificacao_callback", lambda: CallbackQueryHandler(handle_gamification_callback, pattern="^(show_rankings|show_stats|show_rewards)$")),
        ("dashboard_callback", lambda: CallbackQueryHandler(dashboard_callback_handler, pattern="^dashboard_")),
    ]

    # Callbacks bancários removidos
        # Blocos bancários removidos

    for name, builder in callback_builders:
        build_and_add(name, builder)

    # Verificar comandos registrados
    commands_found = []
    for i, handler_group in enumerate(app.handlers):
        try:
            if hasattr(handler_group, '__iter__'):
                for handler in handler_group:
                    if hasattr(handler, 'commands') and handler.commands:
                        commands_found.extend(list(handler.commands))
        except:
            pass

    print(f"📋 Comandos finais registrados: {sorted(set(commands_found))}")

    if 'importar' in commands_found:
        print("🎉 SUCESSO: Comando /importar está registrado!")
    else:
        print("💥 FALHA: Comando /importar NÃO está registrado!")

if __name__ == "__main__":
    test_full_registration()