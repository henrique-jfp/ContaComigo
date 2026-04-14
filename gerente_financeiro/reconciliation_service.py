import logging
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
from models import Lancamento, Conta, Usuario
from database.database import get_db

logger = logging.getLogger(__name__)

class ReconciliationService:
    @staticmethod
    def get_or_create_digital_account(db, user_id):
        """Garante que o usuário tenha a Conta Digital ContaComigo."""
        conta = db.query(Conta).filter(
            Conta.id_usuario == user_id, 
            Conta.nome == "ContaComigo Digital"
        ).first()
        
        if not conta:
            logger.info(f"Criando Conta Digital para usuário {user_id}")
            conta = Conta(
                id_usuario=user_id,
                nome="ContaComigo Digital",
                tipo="PAYMENT_ACCOUNT",
                instituicao="ContaComigo",
                saldo_atual=0,
                ativo=True
            )
            db.add(conta)
            db.commit()
            db.refresh(conta)
        return conta

    @staticmethod
    def is_duplicate(db, user_id, valor, data, descricao, threshold_days=2):
        """
        Verifica se um lançamento já existe na Conta Digital.
        Critérios: Mesmo valor absoluto, data próxima (+/- threshold) e similaridade básica.
        """
        valor_abs = abs(float(valor))
        data_inicio = data - timedelta(days=threshold_days)
        data_fim = data + timedelta(days=threshold_days)
        
        # Busca potenciais duplicados
        # Filtramos por valor exato primeiro (mais performático)
        potenciais = db.query(Lancamento).filter(
            Lancamento.id_usuario == user_id,
            func.abs(Lancamento.valor) == valor_abs,
            Lancamento.data_transacao >= data_inicio,
            Lancamento.data_transacao <= data_fim
        ).all()
        
        if potenciais:
            # Se houver mais de um, poderíamos usar fuzzy string matching
            # Por enquanto, se o valor e data batem, consideramos duplicado para evitar sujeira
            logger.info(f"Duplicidade detectada: {descricao} | Valor: {valor_abs}")
            return potenciais[0]
        
        return None

    @staticmethod
    def register_transaction(db, user_id, valor, data, descricao, categoria_id=None, origem="manual", external_id=None):
        """Registra transação na Conta Digital com detecção de duplicidade."""
        digital_acc = ReconciliationService.get_or_create_digital_account(db, user_id)
        
        existing = ReconciliationService.is_duplicate(db, user_id, valor, data, descricao)
        
        if existing:
            # Se veio do Open Finance e já existia manual, atualizamos o ID externo e a origem
            if origem == "open_finance" and not existing.external_id:
                existing.external_id = external_id
                existing.origem = "open_finance_reconciled"
                db.commit()
            return existing, False # False = Não foi criado um novo
            
        # Cria novo lançamento
        novo = Lancamento(
            id_usuario=user_id,
            id_conta=digital_acc.id,
            valor=valor,
            data_transacao=data,
            descricao=descricao,
            id_categoria=categoria_id,
            origem=origem,
            external_id=external_id
        )
        db.add(novo)
        db.commit()
        db.refresh(novo)
        return novo, True
