import sys
import os

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.database import SessionLocal
from models import Categoria, Subcategoria

def setup_juros_category():
    db = SessionLocal()
    try:
        # 1. Cria Categoria Principal
        cat_nome = "JUROS E ENCARGOS"
        cat = db.query(Categoria).filter(Categoria.nome == cat_nome).first()
        if not cat:
            cat = Categoria(nome=cat_nome)
            db.add(cat)
            db.flush()
            print(f"✅ Categoria '{cat_nome}' criada.")
        else:
            print(f"ℹ️ Categoria '{cat_nome}' já existe.")

        # 2. Cria Subcategorias
        subcategorias = ["Juros", "IOF", "Anuidade", "Multas"]
        for sub_nome in subcategorias:
            sub = db.query(Subcategoria).filter(
                Subcategoria.nome == sub_nome, 
                Subcategoria.id_categoria == cat.id
            ).first()
            if not sub:
                sub = Subcategoria(nome=sub_nome, id_categoria=cat.id)
                db.add(sub)
                print(f"   - Subcategoria '{sub_nome}' criada.")
            else:
                print(f"   - Subcategoria '{sub_nome}' já existe.")
        
        db.commit()
        print("✨ Setup de categorias financeiras finalizado.")
    except Exception as e:
        db.rollback()
        print(f"❌ Erro no setup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    setup_juros_category()
