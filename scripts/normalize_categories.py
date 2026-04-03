from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from database.database import get_db
from models import Categoria, Subcategoria, Lancamento, Agendamento

logging.basicConfig(level=logging.INFO)

# Canonical taxonomy
TARGET_SUBCATEGORIES = {
    "Alimentação": [
        "Supermercado",
        "Restaurante/Delivery",
        "Padaria e Lanches",
        "Bares e Vida Noturna",
    ],
    "Moradia": [
        "Aluguel/Prestação",
        "Condomínio",
        "Contas (Luz/Água/Gás)",
        "Internet/TV",
        "Manutenção/Reforma",
        "Móveis/Decoração",
    ],
    "Transporte": [
        "Combustível",
        "App de Transporte",
        "Transporte Público",
        "Manutenção Veicular",
        "Estacionamento/Pedágio",
        "Seguro/IPVA",
    ],
    "Saúde": [
        "Farmácia",
        "Plano de Saúde",
        "Consultas/Exames",
        "Academia/Esportes",
    ],
    "Lazer e Entretenimento": [
        "Cinema/Streaming",
        "Eventos/Shows",
        "Hobbies",
        "Viagens/Turismo",
        "Bares e Vida Noturna",
    ],
    "Cuidados Pessoais": [
        "Salão/Barbearia",
        "Cosméticos/Perfumes",
    ],
    "Educação": [
        "Cursos/Especializações",
        "Livros/Material",
        "Mensalidade",
    ],
    "Compras": [
        "Roupas/Acessórios",
        "Eletrônicos",
        "Presentes",
        "Itens para Casa",
        "Casa/Decoração",
    ],
    "Serviços e Assinaturas": [
        "Assinaturas Digitais",
        "Telefone Celular",
        "Serviços Profissionais",
    ],
    "Financeiro": [
        "Juros/Encargos",
        "Taxas Bancárias",
        "Empréstimos/Financiamentos",
        "Seguros",
    ],
    "Receitas": [
        "Salário",
        "Bônus/13º",
        "Freelance/Renda Extra",
        "Vendas",
        "Reembolsos",
        "Rendimentos",
        "Outras Receitas",
    ],
    "Investimentos": [
        "Aporte",
        "Resgate",
        "Dividendos/Rendimentos",
    ],
    "Transferências": [
        "Entre Contas",
        "PIX Enviado",
        "PIX Recebido",
    ],
    "Outros": [
        "Doações",
        "Ajuste de Saldo",
        "Despesa não Identificada",
        "Presentes",
        "Despesas não categorizadas",
    ],
}

DELETE_OLD_CATEGORIES = True

CATEGORY_MERGE = {
    "Lazer": "Lazer e Entretenimento",
    "Serviços": "Serviços e Assinaturas",
    "Transferência": "Transferências",
}

SUBCATEGORY_MERGE = {
    "Restaurante e Delivery": "Restaurante/Delivery",
    "Restaurante/Delivery": "Restaurante/Delivery",
    "Restaurante": "Restaurante/Delivery",
    "Delivery": "Restaurante/Delivery",
    "Padaria": "Padaria e Lanches",
    "Padaria e Lanches": "Padaria e Lanches",
    "Bares e Lanches": "Bares e Vida Noturna",
    "Cinema e Streaming": "Cinema/Streaming",
    "Cinema/Streaming": "Cinema/Streaming",
    "Viagens e Turismo": "Viagens/Turismo",
    "Eventos e Shows": "Eventos/Shows",
    "Hobbies e Atividades": "Hobbies",
    "Cursos e Especializações": "Cursos/Especializações",
    "Cursos": "Cursos/Especializações",
    "Livros e Material de Estudo": "Livros/Material",
    "Livros/Material": "Livros/Material",
    "Mensalidade Escolar/Faculdade": "Mensalidade",
    "Assinaturas Digitais (Software, etc)": "Assinaturas Digitais",
    "Serviços Profissionais (Contador, etc)": "Serviços Profissionais",
    "Juros e Encargos": "Juros/Encargos",
    "Juros": "Juros/Encargos",
    "Empréstimos e Financiamentos": "Empréstimos/Financiamentos",
    "Empréstimos": "Empréstimos/Financiamentos",
    "Seguros (Vida, Residencial)": "Seguros",
    "Bônus e 13º": "Bônus/13º",
    "Freelance e Renda Extra": "Freelance/Renda Extra",
    "Dividendos e Rendimentos": "Dividendos/Rendimentos",
    "Aporte (Renda Fixa, Variável)": "Aporte",
    "Resgate de Investimento": "Resgate",
    "App de Transporte (Uber, 99)": "App de Transporte",
    "App de Transporte": "App de Transporte",
    "Estacionamento e Pedágio": "Estacionamento/Pedágio",
    "Manutenção do Veículo": "Manutenção Veicular",
    "Manutenção Veicular": "Manutenção Veicular",
    "Contas (Luz, Água, Gás)": "Contas (Luz/Água/Gás)",
    "Internet e TV": "Internet/TV",
    "Salão e Barbearia": "Salão/Barbearia",
    "Cosméticos e Perfumes": "Cosméticos/Perfumes",
    "Academia e Esportes": "Academia/Esportes",
    "Consultas e Exames": "Consultas/Exames",
    "Consulta Médica": "Consultas/Exames",
    "Viagens": "Viagens/Turismo",
    "Móveis e Decoração": "Móveis/Decoração",
    "Manutenção e Reparos": "Manutenção/Reforma",
    "Aluguel": "Aluguel/Prestação",
    "Aluguel / Prestação": "Aluguel/Prestação",
    "Seguro e IPVA": "Seguro/IPVA",
    "Freelance": "Freelance/Renda Extra",
    "Renidmentos": "Rendimentos",
    "Roupas e Acessórios": "Roupas/Acessórios",
    "Casa e Decoração": "Casa/Decoração",
    "Assinaturas (Internet, Celular)": "Assinaturas Digitais",
    "PIX Enviado (Terceiros)": "PIX Enviado",
    "PIX Recebido (Terceiros)": "PIX Recebido",
    "Entre Contas Próprias": "Entre Contas",
}


def ensure_category(db, name: str) -> Categoria:
    cat = db.query(Categoria).filter(Categoria.nome == name).first()
    if not cat:
        cat = Categoria(nome=name)
        db.add(cat)
    return cat


def ensure_subcategory(db, cat_id: int, name: str) -> Subcategoria:
    sub = (
        db.query(Subcategoria)
        .filter(Subcategoria.id_categoria == cat_id, Subcategoria.nome == name)
        .first()
    )
    if not sub:
        sub = Subcategoria(nome=name, id_categoria=cat_id)
        db.add(sub)
    return sub


def main():
    db = next(get_db())
    try:
        logging.info("Iniciando normalizacao de categorias...")

        target_categories = set(TARGET_SUBCATEGORIES.keys())

        # Ensure target categories exist
        target_cat_ids = {}
        for cat_name in TARGET_SUBCATEGORIES.keys():
            cat = ensure_category(db, cat_name)
            target_cat_ids[cat_name] = cat.id

        db.flush()

        categories = db.query(Categoria).all()
        subcategories = db.query(Subcategoria).all()
        cat_by_id = {c.id: c for c in categories}

        # Ensure target subcategories exist (batch)
        needed_keys = set()
        for sub in subcategories:
            old_cat = cat_by_id.get(sub.id_categoria)
            if not old_cat:
                continue
            target_cat_name = CATEGORY_MERGE.get(old_cat.nome, old_cat.nome)
            target_sub_name = SUBCATEGORY_MERGE.get(sub.nome, sub.nome)
            needed_keys.add((target_cat_name, target_sub_name))

        for cat_name, subs in TARGET_SUBCATEGORIES.items():
            for sub_name in subs:
                needed_keys.add((cat_name, sub_name))

        sub_by_key = {(cat_by_id[s.id_categoria].nome, s.nome): s for s in subcategories}
        for cat_name, sub_name in needed_keys:
            if (cat_name, sub_name) in sub_by_key:
                continue
            cat_id = target_cat_ids.get(cat_name)
            if not cat_id:
                cat = ensure_category(db, cat_name)
                cat_id = cat.id
                target_cat_ids[cat_name] = cat_id
            sub = ensure_subcategory(db, cat_id, sub_name)
            sub_by_key[(cat_name, sub_name)] = sub

        db.flush()
        # Refresh map with assigned IDs
        subcategories = db.query(Subcategoria).all()
        sub_by_key = {(cat_by_id[s.id_categoria].nome, s.nome): s for s in subcategories}

        # Move subcategories + lancamentos
        moved = 0
        for sub in subcategories:
            old_cat = cat_by_id.get(sub.id_categoria)
            if not old_cat:
                continue
            target_cat_name = CATEGORY_MERGE.get(old_cat.nome, old_cat.nome)
            target_cat_id = target_cat_ids.get(target_cat_name)
            if not target_cat_id:
                target_cat = ensure_category(db, target_cat_name)
                target_cat_id = target_cat.id
                target_cat_ids[target_cat_name] = target_cat_id

            target_sub_name = SUBCATEGORY_MERGE.get(sub.nome, sub.nome)
            target_sub = sub_by_key.get((target_cat_name, target_sub_name))
            if not target_sub:
                target_sub = ensure_subcategory(db, target_cat_id, target_sub_name)
                sub_by_key[(target_cat_name, target_sub_name)] = target_sub

            if sub.id != target_sub.id:
                db.query(Lancamento).filter(Lancamento.id_subcategoria == sub.id).update(
                    {"id_subcategoria": target_sub.id, "id_categoria": target_cat_id},
                    synchronize_session=False,
                )
                db.query(Agendamento).filter(Agendamento.id_subcategoria == sub.id).update(
                    {"id_subcategoria": target_sub.id, "id_categoria": target_cat_id},
                    synchronize_session=False,
                )
                db.delete(sub)
                moved += 1

        # Merge categories (for lancamentos without subcategory)
        for old_name, new_name in CATEGORY_MERGE.items():
            old_cat = db.query(Categoria).filter(Categoria.nome == old_name).first()
            new_cat = db.query(Categoria).filter(Categoria.nome == new_name).first()
            if old_cat and new_cat and old_cat.id != new_cat.id:
                db.query(Lancamento).filter(
                    Lancamento.id_categoria == old_cat.id
                ).update({"id_categoria": new_cat.id}, synchronize_session=False)
                db.query(Agendamento).filter(
                    Agendamento.id_categoria == old_cat.id
                ).update({"id_categoria": new_cat.id}, synchronize_session=False)

        if DELETE_OLD_CATEGORIES:
            # Remove subcategorias legacy que nao fazem parte do alvo e nao tem uso.
            subcategories = db.query(Subcategoria).all()
            sub_to_delete = []
            for sub in subcategories:
                cat = cat_by_id.get(sub.id_categoria)
                if not cat:
                    continue
                allowed = TARGET_SUBCATEGORIES.get(cat.nome)
                is_canonical = bool(allowed and sub.nome in allowed)
                if is_canonical:
                    continue

                has_lanc = (
                    db.query(Lancamento.id)
                    .filter(Lancamento.id_subcategoria == sub.id)
                    .first()
                    is not None
                )
                has_agd = (
                    db.query(Agendamento.id)
                    .filter(Agendamento.id_subcategoria == sub.id)
                    .first()
                    is not None
                )
                if has_lanc or has_agd:
                    logging.warning(
                        "Subcategoria legacy em uso, mantendo: %s/%s",
                        cat.nome,
                        sub.nome,
                    )
                    continue
                sub_to_delete.append(sub)

            for sub in sub_to_delete:
                db.delete(sub)

            # Remove categorias legacy sem subcategorias e sem uso.
            categories = db.query(Categoria).all()
            for cat in categories:
                if cat.nome in target_categories:
                    continue
                has_sub = (
                    db.query(Subcategoria.id)
                    .filter(Subcategoria.id_categoria == cat.id)
                    .first()
                    is not None
                )
                if has_sub:
                    logging.warning("Categoria legacy com subcategorias: %s", cat.nome)
                    continue

                has_lanc = (
                    db.query(Lancamento.id)
                    .filter(Lancamento.id_categoria == cat.id)
                    .first()
                    is not None
                )
                has_agd = (
                    db.query(Agendamento.id)
                    .filter(Agendamento.id_categoria == cat.id)
                    .first()
                    is not None
                )
                if has_lanc or has_agd:
                    logging.warning("Categoria legacy em uso, mantendo: %s", cat.nome)
                    continue
                db.delete(cat)

        db.commit()
        logging.info("Categorias normalizadas com sucesso. Subcategorias movidas: %s", moved)
    except Exception as exc:
        db.rollback()
        logging.error("Erro ao normalizar categorias: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
