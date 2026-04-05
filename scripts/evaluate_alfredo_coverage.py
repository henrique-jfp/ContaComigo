#!/usr/bin/env python3
"""Avalia cobertura funcional do Alfredo para um conjunto extenso de perguntas.

Objetivo:
- Medir o que o handler atual consegue responder de forma confiavel.
- Diferenciar respostas diretas (logica local) de respostas dependentes do LLM.
- Mostrar lacunas de contexto por usuario com base no banco atual.

Uso:
    python scripts/evaluate_alfredo_coverage.py --telegram-user-id 123456
    python scripts/evaluate_alfredo_coverage.py --all-users
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Iterable

from database.database import get_db
from models import Agendamento, Lancamento, Objetivo, Usuario


@dataclass
class CoverageRule:
    reliability: str
    rationale: str


QUESTIONS_BY_CATEGORY: dict[str, list[str]] = {
    "dia_a_dia": [
        "Quanto eu tenho hoje disponivel?",
        "Da pra eu gastar hoje sem me ferrar?",
        "Quanto eu gastei essa semana?",
        "Meu dinheiro ta acabando rapido esse mes?",
        "Quanto sobrou do meu salario?",
        "To gastando mais do que deveria?",
        "Quanto eu tenho na conta agora?",
        "Ja paguei tudo esse mes?",
        "Tem alguma conta vencendo hoje?",
        "O que eu ainda preciso pagar essa semana?",
    ],
    "controle_visao_geral": [
        "Como estao minhas financas esse mes?",
        "Me da um resumo geral de tudo",
        "Estou no positivo ou negativo?",
        "Qual foi meu saldo final no mes passado?",
        "Meu padrao de gastos ta saudavel?",
        "Meu dinheiro ta sendo bem distribuido?",
        "Estou evoluindo ou piorando financeiramente?",
        "Como esse mes se compara com o anterior?",
        "Meu custo de vida aumentou?",
        "Estou gastando mais do que ganho?",
    ],
    "analise_gastos": [
        "Onde eu mais estou gastando dinheiro?",
        "Qual categoria mais pesa no meu orcamento?",
        "O que eu poderia cortar agora?",
        "Tem algum gasto fora do normal?",
        "Quais gastos sao desnecessarios?",
        "Estou gastando muito com iFood/lanche?",
        "Quanto eu gasto com besteira por mes?",
        "Me mostra meus gastos invisiveis (pequenos e recorrentes)",
        "Qual foi meu maior gasto recente?",
        "Me mostra padroes de desperdicio",
    ],
    "investigativas": [
        "Por que meu dinheiro esta acabando tao rapido?",
        "O que mudou no meu comportamento financeiro esse mes?",
        "Em que momentos eu mais gasto?",
        "Tem algum padrao ruim nos meus gastos?",
        "Estou comprando por impulso?",
        "Quais dias eu mais gasto dinheiro?",
        "Tem algum habito financeiro me prejudicando?",
        "Onde estou me sabotando financeiramente?",
        "Meu estilo de vida e compativel com minha renda?",
        "O que esta me impedindo de guardar dinheiro?",
    ],
    "planejamento_previsao": [
        "Se eu continuar assim, como termino o mes?",
        "Vou conseguir fechar o mes no positivo?",
        "Quanto posso gastar ate o fim do mes?",
        "Se eu gastar X hoje, isso vai impactar como?",
        "Quanto eu preciso economizar pra ficar tranquilo?",
        "Da pra eu fazer essa compra sem apertar o orcamento?",
        "Quanto posso gastar por dia?",
        "Me da um limite seguro de gasto semanal",
        "Se eu continuar nesse ritmo, vou ficar sem dinheiro quando?",
        "Quanto preciso reduzir pra equilibrar?",
    ],
    "metas_objetivos": [
        "Estou conseguindo guardar dinheiro?",
        "Quanto consegui economizar esse mes?",
        "Quanto falta pra minha meta?",
        "Em quanto tempo eu alcanco esse objetivo?",
        "Quanto preciso guardar por mes pra chegar la?",
        "Estou no caminho certo?",
        "Estou falhando nas minhas metas?",
        "Como posso acelerar minha meta?",
        "Onde posso economizar pra atingir meu objetivo?",
        "Vale a pena eu continuar com essa meta?",
    ],
    "alertas_prevencao": [
        "Estou correndo risco financeiro?",
        "Tem algo preocupante nas minhas financas?",
        "Vou ficar no vermelho?",
        "Tem alguma conta que esqueci?",
        "Meu padrao atual e perigoso?",
        "Estou gastando mais do que o normal?",
        "Tem algo fora do meu comportamento comum?",
        "Minha situacao exige atencao agora?",
        "Estou perto de estourar meu orcamento?",
        "Tem algum gasto suspeito ou incomum?",
    ],
    "contas_compromissos": [
        "Quais contas tenho pra pagar hoje?",
        "O que vence essa semana?",
        "Ja paguei aluguel/luz/internet?",
        "Tem contas atrasadas?",
        "Quanto tenho de contas fixas?",
        "Me lembra do que preciso pagar amanha",
        "Qual o total de contas desse mes?",
        "Quanto estou comprometido ja?",
        "O que ainda falta pagar?",
        "Quanto sobra depois das contas?",
    ],
    "premium": [
        "Se voce fosse meu gerente, o que eu deveria fazer agora?",
        "Qual e o maior erro que estou cometendo hoje?",
        "Me da 3 acoes praticas pra melhorar minha situacao",
        "Onde posso melhorar imediatamente?",
        "O que voce mudaria nos meus habitos?",
        "Me da um plano simples pra organizar minha vida financeira",
        "Estou vivendo acima da minha realidade?",
        "Qual decisao financeira eu deveria evitar agora?",
        "O que eu estou ignorando nas minhas financas?",
        "Se eu continuar assim por 6 meses, onde eu vou parar?",
    ],
    "natural_hibridas": [
        "Cara, to sem dinheiro... o que aconteceu?",
        "Da uma analisada ai pra mim, to preocupado",
        "Acho que to gastando muito, confere isso",
        "To meio perdido com meu dinheiro",
        "Me ajuda a organizar minha vida financeira",
        "To com medo de ficar sem grana esse mes",
        "Da pra eu comprar isso ou melhor segurar?",
        "Fui irresponsavel esse mes?",
        "To indo bem ou mal?",
        "Me fala a real, sem filtro",
        "Gastei muito hoje?",
        "Esse gasto foi fora do padrao?",
        "Esse valor ta dentro do esperado?",
        "Isso compromete meu mes?",
        "Posso continuar gastando hoje?",
        "Esse gasto foi consciente ou impulsivo?",
        "Isso vai impactar minhas contas?",
        "Esse valor e aceitavel pra mim?",
        "Eu deveria ter feito essa compra?",
        "Isso ta alinhado com minhas metas?",
    ],
}


def classify_question(question: str) -> CoverageRule:
    q = question.lower()

    direct_triggers = [
        "quanto eu tenho hoje disponivel",
        "quanto eu tenho na conta agora",
        "estou no positivo ou negativo",
        "to indo bem ou mal",
        "quanto eu gastei essa semana",
        "maior gasto recente",
        "dias eu mais gasto",
        "conta vencendo hoje",
        "vencendo hoje",
        "vence essa semana",
        "contas atrasadas",
        "contas fixas",
        "comprometido",
        "sobra depois das contas",
        "ja paguei aluguel",
        "ja paguei luz",
        "ja paguei internet",
        "ifood",
        "lanche",
        "gastos invisiveis",
        "pequenos e recorrentes",
    ]
    if any(t in q for t in direct_triggers):
        return CoverageRule(
            reliability="alta",
            rationale="Coberta por logica local de saldo/entradas/saidas no handler.",
        )

    if "ultimo" in q and ("lancamento" in q or "gasto" in q or "transacao" in q):
        return CoverageRule(
            reliability="alta",
            rationale="Coberta por busca direta do ultimo lancamento no banco.",
        )

    hard_gaps = [
        "aluguel/luz/internet",
        "me lembra",
        "gasto suspeito",
    ]
    if any(t in q for t in hard_gaps):
        return CoverageRule(
            reliability="baixa",
            rationale="Nao ha contexto especifico injetado para esse tipo de pergunta no fluxo atual.",
        )

    return CoverageRule(
        reliability="media",
        rationale=(
            "Depende do LLM com contexto financeiro detalhado (comparativo mensal, categorias, pagamentos, "
            "agendamentos e metas). Boa utilidade consultiva, mas ainda sem garantias matemáticas para toda previsão."
        ),
    )


def collect_user_stats(db, usuario: Usuario) -> dict:
    lancamentos = db.query(Lancamento).filter(Lancamento.id_usuario == usuario.id).all()
    metas = db.query(Objetivo).filter(Objetivo.id_usuario == usuario.id).all()
    agendamentos = db.query(Agendamento).filter(Agendamento.id_usuario == usuario.id).all()

    entradas = sum(float(l.valor or 0) for l in lancamentos if str(l.tipo).lower().startswith("entr"))
    saidas = sum(abs(float(l.valor or 0)) for l in lancamentos if not str(l.tipo).lower().startswith("entr"))

    return {
        "lancamentos": len(lancamentos),
        "metas": len(metas),
        "agendamentos": len(agendamentos),
        "saldo": round(entradas - saidas, 2),
        "entradas": round(entradas, 2),
        "saidas": round(saidas, 2),
    }


def evaluate_for_user(db, usuario: Usuario) -> dict:
    stats = collect_user_stats(db, usuario)
    questions: list[dict] = []

    totals = {"alta": 0, "media": 0, "baixa": 0}

    for category, items in QUESTIONS_BY_CATEGORY.items():
        for q in items:
            result = classify_question(q)
            totals[result.reliability] += 1
            questions.append(
                {
                    "categoria": category,
                    "pergunta": q,
                    "confianca": result.reliability,
                    "motivo": result.rationale,
                }
            )

    total_questions = len(questions)
    coverage_score = round(((totals["alta"] + (totals["media"] * 0.5)) / total_questions) * 100, 1)

    return {
        "usuario": {
            "id": usuario.id,
            "telegram_id": usuario.telegram_id,
            "nome": usuario.nome_completo,
        },
        "dados": stats,
        "resumo": {
            "total_perguntas": total_questions,
            "alta": totals["alta"],
            "media": totals["media"],
            "baixa": totals["baixa"],
            "score_cobertura": coverage_score,
        },
        "amostra_lacunas": [q for q in questions if q["confianca"] == "baixa"][:15],
    }


def load_target_users(db, telegram_user_id: int | None, all_users: bool) -> Iterable[Usuario]:
    query = db.query(Usuario)
    if telegram_user_id is not None:
        user = query.filter(Usuario.telegram_id == telegram_user_id).first()
        return [user] if user else []
    if all_users:
        return query.order_by(Usuario.id.asc()).all()
    return query.order_by(Usuario.id.asc()).limit(1).all()


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia cobertura do Alfredo para perguntas de usuario")
    parser.add_argument("--telegram-user-id", type=int, default=None, help="Avalia um usuario especifico")
    parser.add_argument("--all-users", action="store_true", help="Avalia todos os usuarios")
    parser.add_argument("--pretty", action="store_true", help="Imprime JSON formatado")
    args = parser.parse_args()

    db = next(get_db())
    try:
        users = list(load_target_users(db, args.telegram_user_id, args.all_users))
        if not users:
            print(json.dumps({"ok": False, "message": "Nenhum usuario encontrado para os filtros."}, ensure_ascii=False))
            return

        report = {
            "ok": True,
            "avaliacoes": [evaluate_for_user(db, user) for user in users],
            "observacao": (
                "Esta avaliacao mede confiabilidade funcional do fluxo atual (handlers + contexto injetado), "
                "nao qualidade absoluta do modelo de linguagem."
            ),
        }

        if args.pretty:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(report, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
