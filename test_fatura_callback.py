#!/usr/bin/env python3
"""
Debug script para testar o callback de edição de fatura.
Simula o que deveria acontecer quando o usuário clica no botão "✏️ Editar".
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from unittest.mock import MagicMock, AsyncMock, patch
from telegram import Update, User, Message, Chat, CallbackQuery
from telegram.ext import ContextTypes

async def test_fatura_callback():
    """Simula um callback de fatura_editar_inline"""
    
    # Mock setup
    user = User(id=123456, first_name="Test", is_bot=False)
    chat = Chat(id=123456, type="private")
    message = Message(
        message_id=1,
        date=None,
        chat=chat,
        text="Test message"
    )
    
    callback_query = CallbackQuery(
        id="test_callback_id",
        from_user=user,
        chat_instance=123,
        data="fatura_editar_inline",  # This is what the button sends
        message=message
    )
    
    update = Update(update_id=1, callback_query=callback_query)
    
    # Create mock context
    context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {
        "fatura_transacoes": [{"valor": -50, "descricao": "Test"}],
        "fatura_conta_id": 1,
        "fatura_origem_label": "Inter"
    }
    
    # Import handler
    from gerente_financeiro.fatura_handler import fatura_confirm
    
    # Mock the database and other functions
    with patch('gerente_financeiro.fatura_handler.get_db') as mock_db:
        mock_conta = MagicMock()
        mock_conta.nome = "Test Conta"
        
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_conta
        mock_session.close = MagicMock()
        
        mock_db.return_value = iter([mock_session])
        
        with patch('gerente_financeiro.fatura_handler.create_fatura_draft') as mock_draft:
            mock_draft.return_value = "test_token_123"
            
            with patch('gerente_financeiro.fatura_handler.set_pending_editor_token'):
                with patch('gerente_financeiro.fatura_handler._get_fatura_webapp_url') as mock_url:
                    mock_url.return_value = "https://example.com/webapp?page=fatura_editor&token=test"
                    
                    # Mock callback query methods
                    callback_query.answer = AsyncMock()
                    callback_query.edit_message_text = AsyncMock()
                    message.reply_text = AsyncMock()
                    
                    # Call the handler
                    print("🧪 Calling fatura_confirm with data='fatura_editar_inline'...")
                    try:
                        result = await fatura_confirm(update, context)
                        print(f"✅ Handler returned: {result}")
                        print(f"📞 query.answer() called: {callback_query.answer.called}")
                        print(f"✏️ query.edit_message_text() called: {callback_query.edit_message_text.called}")
                        print(f"📤 message.reply_text() called: {message.reply_text.called}")
                        
                        if message.reply_text.called:
                            call_args = message.reply_text.call_args
                            print(f"\n📝 reply_text called with:")
                            print(f"   Text: {call_args[0][0][:100]}...")
                            print(f"   reply_markup: {call_args[1].get('reply_markup')}")
                            
                    except Exception as e:
                        print(f"❌ Error in handler: {e}")
                        import traceback
                        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fatura_callback())
