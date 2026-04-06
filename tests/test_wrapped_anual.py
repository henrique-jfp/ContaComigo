from dataclasses import dataclass
from datetime import datetime

from gerente_financeiro.wrapped_anual import (
    derive_lancamento_meta,
    infer_category_from_description,
    infer_payment_method,
    resumir_itens_comprados,
)


@dataclass
class DummyCategoria:
    nome: str


@dataclass
class DummyLancamento:
    tipo: str = ''
    categoria: DummyCategoria | None = None
    descricao: str | None = None
    meio_pagamento: str | None = None
    origem: str | None = None
    valor: float = 0.0
    data_transacao: datetime = datetime.now()
    itens: list | None = None


@dataclass
class DummyItem:
    nome_item: str
    quantidade: float = 1.0
    valor_unitario: float = 0.0


def test_infer_category_from_description_ifood():
    assert infer_category_from_description('Compra iFood do almoço') == 'Alimentação'


def test_infer_payment_method_pix_and_card():
    assert infer_payment_method('PIX', None) == 'Pix'
    assert infer_payment_method('Cartao Visa', 'Pagamento com Visa') == 'Cartão de Crédito'
    assert infer_payment_method(None, 'boleto bancario') == 'Boleto'


def test_derive_lancamento_meta_prefers_inferred_when_categoria_receita_on_despesa():
    # Caso onde categoria registrada diz 'Receitas' mas tipo é 'Despesa' -> usar inferência
    lanc = DummyLancamento(
        tipo='Despesa',
        categoria=DummyCategoria(nome='Receitas Extras'),
        descricao='Compra no mercado',
        meio_pagamento='cartao debito',
        valor=123.45
    )

    tipo_eff, categoria_eff, metodo = derive_lancamento_meta(lanc)
    assert tipo_eff in ('Despesa', 'Receita')
    # A inferência deve reconhecer 'mercado' -> Alimentação
    assert categoria_eff == 'Alimentação'
    assert metodo.lower().startswith('cart') or metodo == 'Cartão' or metodo == 'Cartão de Crédito'


def test_resumir_itens_comprados_gera_topos():
    lancamentos = [
        DummyLancamento(itens=[
            DummyItem(nome_item='Leite', quantidade=2, valor_unitario=5.0),
            DummyItem(nome_item='Pão', quantidade=1, valor_unitario=10.0),
        ]),
        DummyLancamento(itens=[
            DummyItem(nome_item='Leite', quantidade=1, valor_unitario=5.0),
            DummyItem(nome_item='Chocolate', quantidade=1, valor_unitario=25.0),
        ]),
    ]

    resumo = resumir_itens_comprados(lancamentos)

    assert resumo['top_por_qtd'][0]['nome'] == 'Leite'
    assert resumo['top_por_valor'][0]['nome'] == 'Chocolate'
    assert resumo['baratos_por_valor'][0]['nome'] == 'Pão'
