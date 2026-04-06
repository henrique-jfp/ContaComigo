from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gerente_financeiro.fatura_handler import _parse_fatura_pipeline


@dataclass(frozen=True)
class TxSignature:
    date: str
    value: float
    desc_prefix: str


ROOT = Path(__file__).resolve().parents[1]
INTER_PDF = ROOT / "fatura inter-1.pdf"
BRADESCO_PDF = ROOT / "Bradesco_Fatura.pdf"


# Amostras-âncora do PDF Inter para evitar regressões sem precisar listar 100+ itens.
INTER_ANCHORS = {
    TxSignature("10/11/2025", -8.87, "PIXCREDPARCELADO"),
    TxSignature("25/01/2026", -150.00, "COCOBAMBURIOBOTAFOG"),
    TxSignature("29/01/2026", -24.90, "CLAROFLEXREC"),
    TxSignature("06/02/2026", -12.90, "BOBSFIQUEIREDODEMAG"),
    TxSignature("06/02/2026", -293.10, "ZAPAY*DETRANRJ"),
    TxSignature("07/02/2026", -2.08, "JUROSPIXCREDITO"),
    TxSignature("02/02/2026", -6.20, "ECOVIASPONTE"),
    TxSignature("04/02/2026", -11.00, "MP*DELICIADOACAI"),
    TxSignature("05/02/2026", -15.99, "PREZUNIC731"),
    TxSignature("07/02/2026", -8.07, "HNTCOMERCIOHORTIFRUT"),
}

# Verdade-terreno extraída das linhas de lançamentos detectáveis do PDF Bradesco.
BRADESCO_EXPECTED = {
    TxSignature("02/03/2026", -1.71, "IOF ADIC ROTATIVO/ATRASO"),
    TxSignature("02/03/2026", -0.44, "IOF DIARIO ROTATIV/ATRASO"),
    TxSignature("25/03/2026", -31.53, "MP*PAGTESOURO"),
    TxSignature("07/06/2026", -16.27, "PG *I FRALDAS IFR"),
    TxSignature("08/07/2026", -310.79, "PARC.FACIL"),
    TxSignature("02/08/2026", -13.29, "MERCADOPAGO*FEVER"),
    TxSignature("03/08/2026", -5.21, "KIWIFY*ROTEIROBET"),
    TxSignature("13/10/2026", -10.71, "PG *TON TON.COM.B"),
    TxSignature("08/12/2026", -56.43, "PARC.FACIL"),
}


def _normalize(transacoes: list[dict]) -> set[TxSignature]:
    items: set[TxSignature] = set()
    for tx in transacoes:
        date = tx["data_transacao"].strftime("%d/%m/%Y")
        value = round(float(tx["valor"]), 2)
        desc = " ".join(str(tx.get("descricao", "")).split()).upper()
        items.add(TxSignature(date, value, desc))
    return items


def _match_by_prefix(sig: TxSignature, parsed: set[TxSignature]) -> bool:
    prefix = sig.desc_prefix.upper()
    for item in parsed:
        if item.date == sig.date and abs(item.value - sig.value) < 0.005 and item.desc_prefix.startswith(prefix):
            return True
    return False


def _f1(expected: set[TxSignature], parsed: set[TxSignature]) -> float:
    tp = 0
    for exp in expected:
        if _match_by_prefix(exp, parsed):
            tp += 1

    fp = 0
    for got in parsed:
        matched = False
        for exp in expected:
            if exp.date == got.date and abs(exp.value - got.value) < 0.005 and got.desc_prefix.startswith(exp.desc_prefix.upper()):
                matched = True
                break
        if not matched:
            fp += 1

    fn = max(0, len(expected) - tp)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _inter_score(parsed_set: set[TxSignature], parsed_count: int, debit_total: float) -> float:
    # Baseline real do PDF do workspace.
    expected_count = 139
    expected_total = 2210.36

    anchors_hit = sum(1 for a in INTER_ANCHORS if _match_by_prefix(a, parsed_set))
    anchors_score = anchors_hit / len(INTER_ANCHORS)

    count_score = 1.0 - min(abs(parsed_count - expected_count) / expected_count, 1.0)
    total_score = 1.0 - min(abs(debit_total - expected_total) / expected_total, 1.0)

    return 0.50 * total_score + 0.30 * anchors_score + 0.20 * count_score


def test_fatura_parse_assertividade_acima_98():
    assert INTER_PDF.exists(), f"PDF não encontrado: {INTER_PDF}"
    assert BRADESCO_PDF.exists(), f"PDF não encontrado: {BRADESCO_PDF}"

    inter_tx, _inter_ign, inter_origin = _parse_fatura_pipeline(INTER_PDF.read_bytes())
    br_tx, _br_ign, br_origin = _parse_fatura_pipeline(BRADESCO_PDF.read_bytes())

    assert inter_origin == "Inter"
    assert br_origin == "Bradesco"

    inter_set = _normalize(inter_tx)
    br_set = _normalize(br_tx)

    inter_debit_total = round(sum(-float(t["valor"]) for t in inter_tx if float(t["valor"]) < 0), 2)
    inter_score = _inter_score(inter_set, len(inter_tx), inter_debit_total)

    br_score = _f1(BRADESCO_EXPECTED, br_set)

    assertividade = (inter_score + br_score) / 2.0

    # Guard rail forte para regressão real do parser.
    assert assertividade >= 0.98, (
        f"Assertividade abaixo do alvo: {assertividade * 100:.2f}% "
        f"(Inter={inter_score * 100:.2f}%, Bradesco={br_score * 100:.2f}%)"
    )
