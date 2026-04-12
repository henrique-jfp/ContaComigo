import logging
import json
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import Lancamento, Categoria, Subcategoria, Usuario
from gerente_financeiro.ai_service import _smart_ai_completion_async
from .categorizador import (
    NOME_CATEGORIA_OUTROS_DESPESA,
    NOME_CATEGORIA_OUTROS_RECEITA,
    aplicar_regras_lancamentos_open_finance,
)

logger = logging.getLogger(__name__)

# Tamanho do lote enviado ao LLM (contexto x custo)
TAMANHO_LOTE_LLM = 50

PROMPT_CATEGORIZACAO = """
Você é um especialista em finanças pessoais brasileiras e sua tarefa é categorizar transações bancárias.
Receberei uma lista de transações com descrição, valor e tipo (Receita/Despesa).

Regras de Ouro:
1. Identifique o estabelecimento/serviço: Limpe a descrição para um nome amigável (ex: "PAG* IFOOD" -> "iFood").
2. **Assinaturas vs Financiamentos**: 
   - Se for um serviço recorrente (Netflix, Spotify, Wellhub, Sócio Torcedor, Flamengo, Academias, SaaS), use a categoria "Serviços e Assinaturas" e subcategoria "Assinaturas".
   - Se for uma parcela de dívida de longo prazo (BV Financeira, Banco Itaú Financiamento, Carro, Moto, Imóvel), use a categoria "Empréstimos e Financiamentos".
3. Se for um PIX enviado para uma pessoa sem indicação de serviço, use a categoria "Transferências" e subcategoria "PIX Enviado".
4. Retorne APENAS um JSON no formato:
[
  {{"id": 123, "descricao_limpa": "Nome Amigável", "categoria": "Nome Categoria", "subcategoria": "Nome Subcategoria"}},
  ...
]

Categorias e Subcategorias Disponíveis:
{lista_categorias}

Importante: Retorne apenas o JSON, sem explicações.
"""

async def categorizar_lote_llm(db: Session, lancamentos: list[Lancamento]) -> int:
    """Envia um lote de lançamentos para o LLM categorizar. Retorna quantos registros foram alterados."""
    if not lancamentos:
        return 0

    antes = {
        l.id: (l.id_categoria, l.id_subcategoria, (l.descricao or ""))
        for l in lancamentos
    }

    # Preparar a lista de categorias para o prompt
    categorias_db = db.query(Categoria).all()
    mapa_cat = []
    for c in categorias_db:
        subcats = [s.nome for s in c.subcategorias]
        mapa_cat.append(f"- {c.nome}: {', '.join(subcats)}")
    
    lista_categorias_str = "\n".join(mapa_cat)

    # Preparar dados das transações
    dados_transacoes = []
    for l in lancamentos:
        dados_transacoes.append({
            "id": l.id,
            "descricao": l.descricao,
            "valor": float(l.valor),
            "tipo": l.tipo
        })

    messages = [
        {"role": "system", "content": PROMPT_CATEGORIZACAO.format(lista_categorias=lista_categorias_str)},
        {"role": "user", "content": f"Categorize estas transações: {json.dumps(dados_transacoes)}"}
    ]

    try:
        response = await _smart_ai_completion_async(messages)
        
        # O smart_ai pode retornar dict (Cerebras/Groq) ou str (Gemini)
        content = ""
        if isinstance(response, dict):
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        elif isinstance(response, str):
            content = response
        
        # Limpar markdown do JSON se houver
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        resultados = json.loads(content)
        
        # Cache de IDs para evitar queries repetitivas
        cat_ids = {c.nome: c.id for c in categorias_db}
        subcat_ids = {(s.id_categoria, s.nome): s.id for s in db.query(Subcategoria).all()}

        for res in resultados:
            l_id = res.get("id")
            l_obj = next((x for x in lancamentos if x.id == l_id), None)

            if l_obj:
                l_obj.descricao = res.get("descricao_limpa", l_obj.descricao)

                cat_nome = res.get("categoria")
                sub_nome = res.get("subcategoria")

                c_id = cat_ids.get(cat_nome)
                if c_id:
                    l_obj.id_categoria = c_id
                    s_id = subcat_ids.get((c_id, sub_nome))
                    if s_id:
                        l_obj.id_subcategoria = s_id

        alterados = 0
        for l in lancamentos:
            depois = (l.id_categoria, l.id_subcategoria, (l.descricao or ""))
            if depois != antes.get(l.id):
                alterados += 1

        db.commit()
        return alterados

    except Exception as e:
        logger.error(f"Erro na categorização via LLM: {e}")
        db.rollback()
        return 0

def _ids_categorias_fallback_llm(db: Session) -> set[int]:
    """IDs das categorias genéricas 'Outros' / 'Receita / Outros' (pós-regras)."""
    rows = (
        db.query(Categoria.id)
        .filter(
            Categoria.nome.in_(
                [NOME_CATEGORIA_OUTROS_DESPESA, NOME_CATEGORIA_OUTROS_RECEITA]
            )
        )
        .all()
    )
    return {r[0] for r in rows}


async def processar_fallback_outros_llm(db: Session, user_id: int) -> int:
    """
    Refinamento por LLM: lançamentos Open Finance ainda sem categoria OU
    classificados apenas como Outros / Receita / Outros após as regras locais.
    """
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        return 0

    ids_outros = _ids_categorias_fallback_llm(db)
    total_atualizados = 0
    max_batches = 500
    n_batch = 0

    while n_batch < max_batches:
        n_batch += 1
        if ids_outros:
            cat_cond = or_(
                Lancamento.id_categoria.is_(None),
                Lancamento.id_categoria.in_(ids_outros),
            )
        else:
            cat_cond = Lancamento.id_categoria.is_(None)

        pendentes = (
            db.query(Lancamento)
            .filter(
                Lancamento.id_usuario == user_id,
                Lancamento.origem == "open_finance",
                cat_cond,
            )
            .order_by(Lancamento.id)
            .limit(TAMANHO_LOTE_LLM)
            .all()
        )
        if not pendentes:
            break

        atualizados = await categorizar_lote_llm(db, pendentes)
        if atualizados == 0:
            break

        total_atualizados += atualizados
        logger.info("Categorização LLM (fallback Outros): %s processados no total...", total_atualizados)

    return total_atualizados


async def pipeline_categorizacao_pos_ingestao(db: Session, user_id: int) -> dict[str, int]:
    """
    Pós-ingestão Pierre (fora do sync): regras em lançamentos ainda sem categoria,
    depois LLM no que permanecer NULL ou em Outros. Não chama a API Pierre.
    Falhas em cada etapa são isoladas para não derrubar a outra.
    """
    n_regras = 0
    n_llm = 0
    try:
        n_regras = aplicar_regras_lancamentos_open_finance(
            db, user_id, escopo="sem_categoria"
        )
    except Exception as e:
        logger.warning(
            "[PIERRE pipeline] Regras locais falharam (user_id=%s): %s",
            user_id,
            e,
        )
    try:
        n_llm = await processar_fallback_outros_llm(db, user_id)
    except Exception as e:
        logger.warning(
            "[PIERRE pipeline] LLM fallback falhou (user_id=%s): %s",
            user_id,
            e,
        )
    return {"regras": n_regras, "llm": n_llm}


async def processar_todos_pendentes(db: Session, user_id: int) -> int:
    """Alias retrocompatível — apenas refinamento LLM (fallback Outros + sem categoria)."""
    return await processar_fallback_outros_llm(db, user_id)
