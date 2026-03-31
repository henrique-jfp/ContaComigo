import pytest
from sqlalchemy.orm import Session
from models import Lancamento
 
from database.database import get_db

@pytest.mark.asyncio
def test_categorizar_lancamentos(monkeypatch):
    # Setup: cria lançamentos sem categoria para um usuário fake
    db: Session = next(get_db())
    user_id = 999999
    l1 = Lancamento(id_usuario=user_id, descricao="supermercado", valor=100, tipo="Saída", id_categoria=None)
    l2 = Lancamento(id_usuario=user_id, descricao="uber", valor=50, tipo="Saída", id_categoria=None)
    db.add(l1)
    db.add(l2)
    db.commit()
    db.close()

    # Mock update/context
    class DummyMessage:
        def __init__(self):
            self.texts = []
        async def reply_text(self, text):
            self.texts.append(text)
    class DummyUpdate:
        effective_user = type('U', (), {'id': user_id})()
        message = DummyMessage()
    class DummyContext:
        pass

    # handler removido
    import asyncio
    update = DummyUpdate()
    context = DummyContext()
    asyncio.run(handler.categorizar_lancamentos(update, context))
    # Verifica se a resposta foi de sucesso
    assert any("categorizados" in t for t in update.message.texts)

    # Cleanup
    db: Session = next(get_db())
    db.query(Lancamento).filter(Lancamento.id_usuario == user_id).delete()
    db.commit()
    db.close()
