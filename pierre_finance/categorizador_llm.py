"""
Categorizador LLM — Fallback Inteligente para Transações Não Categorizadas
===========================================================================
v4 — Reescrita completa.

Melhorias principais:
- Prompt drasticamente melhorado com exemplos reais brasileiros
- Categorias carregadas do banco com fallback para lista hardcoded
- Parsing robusto: JSON, markdown code block, e fallback de texto
- Proteção contra loops infinitos no pipeline
- Logging detalhado para diagnóstico
- Função `processar_todos_pendentes` renomeada mas mantém alias retrocompatível
"""

import logging
import json
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import Lancamento, Categoria, Subcategoria, Usuario
from gerente_financeiro.ai_service import _smart_ai_completion_async
from .categorizador import (
    NOME_CATEGORIA_OUTROS_DESPESA,
    NOME_CATEGORIA_OUTROS_RECEITA,
    MAPA_CATEGORIAS,
    classificar_nomes_por_regras,
    aplicar_regras_lancamentos_open_finance,
)

logger = logging.getLogger(__name__)

# Tamanho do lote enviado ao LLM — balanceia contexto vs custo
TAMANHO_LOTE_LLM = 40

# Máximo de batches por chamada de pipeline (proteção anti-loop)
MAX_BATCHES_LLM = 20


# ---------------------------------------------------------------------------
# Categorias hardcoded como fallback caso o banco esteja vazio
# ---------------------------------------------------------------------------
_CATEGORIAS_HARDCODED = list(MAPA_CATEGORIAS.keys()) + [
    NOME_CATEGORIA_OUTROS_DESPESA,
    NOME_CATEGORIA_OUTROS_RECEITA,
]


def _build_lista_categorias(db: Session) -> str:
    """
    Monta string legível de categorias/subcategorias para o prompt.
    Prioriza banco de dados; cai para hardcoded se o banco estiver vazio.
    """
    try:
        categorias_db = db.query(Categoria).all()
        if categorias_db:
            linhas = []
            for c in categorias_db:
                subcats = [s.nome for s in c.subcategorias]
                if subcats:
                    linhas.append(f"- {c.nome}: {', '.join(subcats)}")
                else:
                    linhas.append(f"- {c.nome}")
            return "\n".join(linhas)
    except Exception as e:
        logger.warning("Não foi possível carregar categorias do banco: %s", e)

    # Fallback: usa o mapa hardcoded
    linhas = []
    for cat, subcats in MAPA_CATEGORIAS.items():
        subcats_list = list(subcats.keys())
        linhas.append(f"- {cat}: {', '.join(subcats_list)}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Você é um especialista em finanças pessoais brasileiras. Sua tarefa é categorizar transações bancárias reais.

CATEGORIAS E SUBCATEGORIAS DISPONÍVEIS:
{lista_categorias}

REGRAS OBRIGATÓRIAS (siga à risca):
1. NUNCA retorne "Outros" se houver qualquer pista na descrição. Use seu conhecimento de mercado brasileiro.
2. IDENTIFIQUE o estabelecimento real: limpe prefixos bancários e retorne o nome amigável.
   - "PIX ENVIADO NETFLIX COM" → nome limpo: "Netflix", categoria: Serviços e Assinaturas / Streaming
   - "COMPRA DEBITO IFOOD*PEDIDO" → nome limpo: "iFood", categoria: Alimentação / Delivery
   - "PAG* STARBUCKS SAO PAULO" → nome limpo: "Starbucks", categoria: Alimentação / Restaurantes/Lanchonetes
3. ESTABELECIMENTOS CONHECIDOS:
   - Zamp / Burger King / BK = Alimentação / Restaurantes/Lanchonetes
   - Ecovias / Sem Parar / AutoPista = Transporte / Pedágio
   - Gympass / Wellhub / TotalPass = Serviços e Assinaturas / Academia/Saúde
   - BV Financeira / Itaú Fin = Empréstimos e Financiamentos / Parcela de Veículo
   - Drogasil / Raia / Pacheco = Saúde / Farmácia
   - Porto Seguro / Allianz / Mapfre = Serviços e Assinaturas / Seguros
   - iFood / Rappi / Uber Eats = Alimentação / Delivery
   - 99 / Uber (trip/viagem) = Transporte / Aplicativos
   - Kabum / Pichau / Terabyte = Compras Online / Eletrônicos
   - Shopee / Shein / AliExpress = Vestuário e Beleza / Roupas e Calçados (se roupas) ou Compras Online
4. PIX para pessoa física SEM indicação de serviço = Transferências / PIX Enviado
5. PIX para pessoa com título (Dr., Dra., Clínica, Studio, Salão) = categoria específica (Saúde, Beleza, etc)
6. Valores de parcela (parc, x de, parcela N/M) = Empréstimos e Financiamentos
7. Descrições de juros, mora, IOF, tarifa = Juros e Encargos

FORMATO DE SAÍDA — retorne APENAS JSON puro, sem markdown, sem explicações:
[
  {{"id": 123, "descricao_limpa": "Nome Amigável do Estabelecimento", "categoria": "Nome Exato da Categoria", "subcategoria": "Nome Exato da Subcategoria"}},
  ...
]"""


# ---------------------------------------------------------------------------
# Lote LLM
# ---------------------------------------------------------------------------

async def categorizar_lote_llm(db: Session, lancamentos: list[Lancamento]) -> int:
    """
    Envia um lote de lançamentos ao LLM para categorização.
    Retorna quantos registros foram efetivamente alterados.
    """
    if not lancamentos:
        return 0

    # Snapshot para comparar depois
    antes = {
        l.id: (l.id_categoria, l.id_subcategoria, l.descricao or "")
        for l in lancamentos
    }

    lista_categorias = _build_lista_categorias(db)

    # Prepara payload enxuto para o LLM (só o necessário)
    dados = []
    for l in lancamentos:
        dados.append({
            "id": l.id,
            "descricao": l.descricao or "",
            "contraparte": l.nome_contraparte or "",
            "valor": float(l.valor or 0),
            "tipo": l.tipo or "Despesa",
        })

    messages = [
        {
            "role": "system",
            "content": _SYSTEM_PROMPT.format(lista_categorias=lista_categorias),
        },
        {
            "role": "user",
            "content": (
                f"Categorize estas {len(dados)} transações bancárias brasileiras.\n"
                f"Retorne APENAS o JSON, sem texto adicional:\n\n"
                f"{json.dumps(dados, ensure_ascii=False)}"
            ),
        },
    ]

    try:
        response = await _smart_ai_completion_async(messages)
    except Exception as e:
        logger.error("Erro ao chamar LLM para categorização: %s", e)
        return 0

    # Extrai conteúdo de texto da resposta (suporta dict e str)
    content = ""
    if isinstance(response, dict):
        content = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    elif isinstance(response, str):
        content = response

    if not content:
        logger.warning("LLM retornou resposta vazia para lote de categorização.")
        return 0

    # ── Parse robusto ────────────────────────────────────────────────────────
    resultados = _parse_json_response(content)
    if not resultados:
        logger.warning("LLM não retornou JSON válido. Conteúdo: %s", content[:300])
        return 0

    # Carrega IDs do banco para lookup eficiente
    cat_ids: dict[str, int] = {}
    subcat_ids: dict[tuple[int, str], int] = {}

    try:
        for c in db.query(Categoria).all():
            cat_ids[c.nome.lower()] = c.id
        for s in db.query(Subcategoria).all():
            subcat_ids[(s.id_categoria, s.nome.lower())] = s.id
    except Exception as e:
        logger.error("Erro ao carregar IDs de categorias: %s", e)
        return 0

    # Aplica resultados
    alterados = 0
    for res in resultados:
        l_id = res.get("id")
        l_obj = next((x for x in lancamentos if x.id == l_id), None)
        if not l_obj:
            continue

        # Atualiza descrição limpa se fornecida e não estiver vazia
        desc_limpa = (res.get("descricao_limpa") or "").strip()
        if desc_limpa and len(desc_limpa) > 1:
            l_obj.descricao = desc_limpa

        cat_nome = (res.get("categoria") or "").strip()
        sub_nome = (res.get("subcategoria") or "").strip()

        if not cat_nome or not sub_nome:
            continue

        # Evita persistir "Outros" explícito (deixa para próxima rodada)
        if cat_nome.lower() in ("outros", "outro", "other"):
            continue

        c_id = cat_ids.get(cat_nome.lower())
        if not c_id:
            # Tenta criar categoria nova
            try:
                nova_cat = Categoria(nome=cat_nome)
                db.add(nova_cat)
                db.flush()
                c_id = nova_cat.id
                cat_ids[cat_nome.lower()] = c_id
            except Exception:
                continue

        s_id = subcat_ids.get((c_id, sub_nome.lower()))
        if not s_id:
            # Tenta criar subcategoria nova
            try:
                nova_sub = Subcategoria(nome=sub_nome, id_categoria=c_id)
                db.add(nova_sub)
                db.flush()
                s_id = nova_sub.id
                subcat_ids[(c_id, sub_nome.lower())] = s_id
            except Exception:
                continue

        l_obj.id_categoria = c_id
        l_obj.id_subcategoria = s_id

    # Conta efetivamente alterados
    for l in lancamentos:
        depois = (l.id_categoria, l.id_subcategoria, l.descricao or "")
        if depois != antes.get(l.id):
            alterados += 1

    try:
        db.commit()
    except Exception as e:
        logger.error("Erro ao fazer commit após categorização LLM: %s", e)
        db.rollback()
        return 0

    logger.info(
        "[LLM] Lote processado: %d enviados, %d alterados.", len(lancamentos), alterados
    )
    return alterados


def _parse_json_response(content: str) -> list[dict] | None:
    """
    Tenta extrair uma lista JSON de uma string, suportando:
    - JSON puro
    - JSON dentro de ```json ... ```
    - JSON dentro de ``` ... ```
    - JSON precedido de texto livre
    """
    content = content.strip()

    # Tenta parse direto
    if content.startswith("["):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # Remove blocos markdown
    for pattern in [r"```json\s*([\s\S]*?)```", r"```\s*([\s\S]*?)```"]:
        import re
        match = re.search(pattern, content)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # Tenta encontrar o array JSON em qualquer posição
    import re
    match = re.search(r"\[[\s\S]*\]", content)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Pipeline de fallback
# ---------------------------------------------------------------------------

def _ids_categorias_fallback_llm(db: Session) -> set[int]:
    """Retorna IDs das categorias genéricas que o LLM deve refinar."""
    try:
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
    except Exception:
        return set()


async def processar_fallback_outros_llm(db: Session, user_id: int) -> int:
    """
    Envia ao LLM lançamentos Open Finance que:
    - Estão sem categoria (id_categoria IS NULL), OU
    - Foram classificados como "Outros" / "Receita / Outros" pelas regras locais.

    Retorna total de lançamentos efetivamente recategorizados.
    """
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        logger.warning("[LLM fallback] Usuário %d não encontrado.", user_id)
        return 0

    ids_outros = _ids_categorias_fallback_llm(db)
    total_atualizados = 0
    n_batch = 0

    while n_batch < MAX_BATCHES_LLM:
        n_batch += 1

        # Constrói condição: sem categoria OU em Outros
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
            logger.info("[LLM fallback] Nenhum pendente restante. Encerrando após %d batches.", n_batch - 1)
            break

        atualizados = await categorizar_lote_llm(db, pendentes)
        total_atualizados += atualizados

        logger.info(
            "[LLM fallback] batch=%d pendentes=%d alterados=%d total_acum=%d",
            n_batch, len(pendentes), atualizados, total_atualizados,
        )

        # Se nenhum foi alterado, evita loop infinito
        if atualizados == 0:
            logger.info("[LLM fallback] Sem progresso no batch. Encerrando.")
            break

    return total_atualizados


# ---------------------------------------------------------------------------
# Pipeline pós-ingestão (chamado após sync Pierre)
# ---------------------------------------------------------------------------

async def pipeline_categorizacao_pos_ingestao(
    db: Session, user_id: int
) -> dict[str, int]:
    """
    Pipeline completo pós-ingestão Open Finance:
    1. Aplica regras locais aos lançamentos sem categoria
    2. Envia ao LLM o que ainda estiver sem categoria ou em "Outros"

    Isolamento de falhas: uma etapa não derruba a outra.
    Não chama a API Pierre.
    """
    n_regras = 0
    n_llm = 0

    try:
        n_regras = aplicar_regras_lancamentos_open_finance(
            db, user_id, escopo="sem_categoria"
        )
        logger.info("[pipeline pós-ingestão] Regras: %d atualizados (user=%d)", n_regras, user_id)
    except Exception as e:
        logger.warning("[pipeline pós-ingestão] Regras locais falharam (user=%d): %s", user_id, e)

    try:
        n_llm = await processar_fallback_outros_llm(db, user_id)
        logger.info("[pipeline pós-ingestão] LLM: %d atualizados (user=%d)", n_llm, user_id)
    except Exception as e:
        logger.warning("[pipeline pós-ingestão] LLM fallback falhou (user=%d): %s", user_id, e)

    return {"regras": n_regras, "llm": n_llm}


# ---------------------------------------------------------------------------
# Alias retrocompatível
# ---------------------------------------------------------------------------

async def processar_todos_pendentes(db: Session, user_id: int) -> int:
    """Alias retrocompatível — apenas refinamento LLM (fallback Outros + sem categoria)."""
    return await processar_fallback_outros_llm(db, user_id)
