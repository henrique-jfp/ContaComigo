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
                tipo="Carteira Digital",
                external_id=f"digital_wallet_{user_id}"
            )
            db.add(conta)
            db.commit()
            db.refresh(conta)
        return conta

    @staticmethod
    def is_duplicate(db, user_id, valor, data, descricao, external_id=None, threshold_days=1):
        """
        Verifica se um lançamento já existe.
        Critérios: ID Externo idêntico OU (Mesmo valor E descrição similar no mesmo dia).
        """
        if external_id:
            existing_ext = db.query(Lancamento).filter(
                Lancamento.id_usuario == user_id,
                Lancamento.external_id == external_id
            ).first()
            if existing_ext: return existing_ext

        valor_abs = abs(float(valor))
        data_inicio = data - timedelta(days=threshold_days)
        data_fim = data + timedelta(days=threshold_days)
        
        # Busca potenciais duplicados por valor e data aproximada
        potenciais = db.query(Lancamento).filter(
            Lancamento.id_usuario == user_id,
            func.abs(Lancamento.valor) == valor_abs,
            Lancamento.data_transacao >= data_inicio,
            Lancamento.data_transacao <= data_fim
        ).all()
        
        desc_nova = str(descricao).lower().strip()
        for p in potenciais:
            desc_existente = str(p.descricao).lower().strip()
            # Se a descrição for muito parecida ou o external_id bater, é duplicado
            if desc_nova == desc_existente:
                logger.info(f"Duplicidade exata detectada: {descricao} | R$ {valor_abs}")
                return p
        
        return None

    @staticmethod
    def register_transaction(db, user_id, valor, data, descricao, categoria_id=None, origem="manual", external_id=None, tipo=None, id_conta=None):
        """Registra transação na ContaComigo Digital (Conta Central Única)."""
        digital_acc = ReconciliationService.get_or_create_digital_account(db, user_id)
        
        if not tipo:
            tipo = "Receita" if float(valor) > 0 else "Despesa"

        # Passamos o external_id para a verificação ser precisa
        existing = ReconciliationService.is_duplicate(db, user_id, valor, data, descricao, external_id=external_id)
        
        if existing:
            # Se veio do Open Finance, apenas garantimos o external_id para evitar duplicatas futuras
            if origem == "open_finance" and not existing.external_id:
                existing.external_id = external_id
                db.commit()
            return existing, False # False = Não foi criado um novo
            
        # Cria novo lançamento na conta central
        novo = Lancamento(
            id_usuario=user_id,
            id_conta=digital_acc.id,
            valor=valor,
            tipo=tipo,
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
