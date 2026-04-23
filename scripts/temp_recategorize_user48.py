import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no `sys.path`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import get_db
from models import Lancamento
from pierre_finance.categorizador import persistir_ids_categoria

def recategorize():
    db = next(get_db())
    try:
        user_id = 48
        
        # Mapeamento de substrings na descrição para (Categoria, Subcategoria)
        # Note: Ordem importa (as mais específicas primeiro)
        mapping = [
            ("Food To Save", "Alimentação", "Aplicativos De Comida"),
            ("Quiosque Aonde", "Alimentação", "Lanche"),
            ("Shpp Brasil", "Compras", "E-Commerce"),
            ("Frogpay", "Serviços E Assinaturas", "Serviços Digitais"),
            ("Pushinpay", "Serviços E Assinaturas", "Serviços Digitais"),
            ("Pagar Me", "Compras", "E-Commerce"),
            ("Banca do Largo", "Lazer", "Banca E Revistas"),
            ("Banca Presidente Wilso", "Lazer", "Banca E Revistas"),
            ("Banca", "Lazer", "Banca E Revistas"),
            ("Henrique De Jesus Freitas Pereira", "Transferência", "Entre Contas"),
            ("Rita Mari", "Serviços", "Serviços Pessoais") # Ex: Ritamaria Barros
        ]

        lancamentos = db.query(Lancamento).filter(Lancamento.id_usuario == user_id).all()
        atualizados = 0

        print(f"Iniciando recategorização para o usuário {user_id}...\n")

        for lanc in lancamentos:
            desc = lanc.descricao or ""
            for substring, cat_nome, subcat_nome in mapping:
                if substring.lower() in desc.lower():
                    # Evitar falsos positivos com a palavra "Banca" se não for o início de uma frase ou tiver espaço
                    if substring == "Banca" and "Banca" not in desc:
                        continue
                        
                    cat_id, subcat_id = persistir_ids_categoria(db, cat_nome, subcat_nome)
                    
                    if lanc.id_categoria != cat_id or lanc.id_subcategoria != subcat_id:
                        print(f" -> '{desc}' | {lanc.valor} | De: {lanc.id_categoria or '?'}/{lanc.id_subcategoria or '?'} PARA: {cat_nome}/{subcat_nome}")
                        lanc.id_categoria = cat_id
                        lanc.id_subcategoria = subcat_id
                        atualizados += 1
                    
                    break # Interrompe após o primeiro match de mapping
        
        if atualizados > 0:
            db.commit()
            print(f"\n✅ Sucesso! {atualizados} lançamentos foram recategorizados para o usuário {user_id}.")
        else:
            print("\nℹ️ Nenhum lançamento precisou ser atualizado (mapeamento não encontrado ou já aplicado).")

    except Exception as e:
        db.rollback()
        print(f"❌ Erro durante a recategorização: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    recategorize()
