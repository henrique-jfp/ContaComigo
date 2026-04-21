from datetime import date

from alerts import _avancar_data_recorrente
from gerente_financeiro.ia_handlers import _alternar_tipo_compromisso


def test_avancar_data_recorrente_para_semanal_e_mensal():
    base = date(2026, 4, 21)
    assert _avancar_data_recorrente(base, "semanal") == date(2026, 4, 28)
    assert _avancar_data_recorrente(base, "mensal") == date(2026, 5, 21)
    assert _avancar_data_recorrente(base, "unico") is None


def test_toggle_de_agendamento_para_lembrete_preserva_dados():
    dados = {
        "acao": "agendar_despesa",
        "descricao": "Conta de luz",
        "valor": 257.0,
        "data": "2026-04-23",
        "frequencia": "mensal",
        "parcelas": None,
        "tipo": "Saída",
    }
    convertido = _alternar_tipo_compromisso(dados, "lembrete")
    assert convertido["acao"] == "criar_lembrete"
    assert convertido["descricao"] == "Conta de luz"
    assert convertido["valor"] == 257.0
    assert convertido["frequencia"] == "mensal"


def test_toggle_de_lembrete_para_agendamento_escolhe_despesa_por_padrao():
    dados = {
        "acao": "criar_lembrete",
        "descricao": "Pagar Michel",
        "valor": None,
        "data": "2026-04-29",
        "frequencia": "unico",
        "parcelas": 1,
        "tipo": "Saída",
    }
    convertido = _alternar_tipo_compromisso(dados, "agendamento")
    assert convertido["acao"] == "agendar_despesa"
    assert convertido["valor"] == 0.0
