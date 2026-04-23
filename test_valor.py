import os
os.environ["CONTACOMIGO_MODE"] = "BOT"
from gerente_financeiro.ia_handlers import _detectar_e_extrair_acao_direta, _parse_br_money

res = _detectar_e_extrair_acao_direta("Gastei 150 reais de gasolina hoje.")
print("Acao Direta:", res)

args = res[1]
valor_raw = args.get("valor") or args.get("valor_alvo") or 0
if isinstance(valor_raw, (int, float)):
    valor = float(valor_raw)
else:
    valor = _parse_br_money(str(valor_raw))
print("Valor Final:", valor)
