import importlib.util
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Lancamento, Usuario
from gerente_financeiro.audio_handler import _normalizar_forma_pagamento as audio_norm
from gerente_financeiro.handlers import _parse_filtros_lancamento
from gerente_financeiro.ia_handlers import _normalizar_forma_pagamento as ia_norm
from gerente_financeiro.quick_entry_handler import _normalizar_forma_pagamento as quick_norm
from gerente_financeiro.services import _preparar_dados_lancamento


def load_dashboard_normalizer():
    dashboard_path = Path("analytics/dashboard_app.py").resolve()
    spec = importlib.util.spec_from_file_location("dashboard_app_isolated", dashboard_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module._normalize_forma_pagamento


def run():
    dashboard_norm = load_dashboard_normalizer()

    samples = {
        "pix": "Pix",
        "credito": "Crédito",
        "debito": "Débito",
        "boleto": "Boleto",
        "dinheiro": "Dinheiro",
        "": "Nao_informado",
        "n/a": "Nao_informado",
        None: "Nao_informado",
    }

    for raw, expected in samples.items():
        assert quick_norm(raw) == expected, ("quick", raw)
        assert audio_norm(raw) == expected, ("audio", raw)
        assert ia_norm(raw) == expected, ("ia", raw)
        assert dashboard_norm(raw) == expected, ("miniapp", raw)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    user = Usuario(telegram_id=1010, nome_completo="Smoke")
    session.add(user)
    session.commit()

    lanc = Lancamento(id_usuario=user.id, descricao="Teste", valor=10, tipo="Saída")
    session.add(lanc)
    session.commit()
    session.refresh(lanc)

    assert lanc.forma_pagamento == "Nao_informado"
    assert not hasattr(lanc, "id_conta")

    payload = _preparar_dados_lancamento({"descricao": "A", "valor": 12.5, "tipo": "Saída"}, user.id, 999, db=session)
    assert "id_conta" not in payload
    assert payload["forma_pagamento"] == "Nao_informado"

    filtros = _parse_filtros_lancamento("gastei no pix ontem", session, user.id)
    assert "id_conta" not in filtros
    assert filtros.get("forma_pagamento") == "pix"

    html = Path("templates/miniapp.html").read_text(encoding="utf-8")
    removed_tokens = ["contasList", "novaContaSalvar", "createConta(", "Adicionar conta/cartão"]
    for token in removed_tokens:
        assert token not in html, token

    print("SMOKE_OK")


if __name__ == "__main__":
    run()
