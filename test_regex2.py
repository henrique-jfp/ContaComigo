import os
os.environ["CONTACOMIGO_MODE"] = "BOT"
from gerente_financeiro.ia_handlers import _parse_br_money, _limpar_sujeira_string
import re

def _detectar_e_extrair_acao_direta(texto: str) -> tuple[str, dict] | None:
    t = texto.lower().strip()
    
    valor_re = r'(?:r\$?\s*)?([\d.,]+)\s*(mil(?:h[õo]es|ão)?|k)?'

    verbos = r'\b(?:gastei|paguei|recebi|lanç[ao]r?|registra?r?|coloque?i?|comprei|compras?|adiciona?r?|anota?r?|gastar|gastou|comprar|pagar|receber|recebeu)\b'
    fillers = r'(?:\s+(?:um|uma|o|a|os|as|do|da|no|na|em|com|de|valor|compra|gasto|despesa|receita|para|pra))*'
    
    p_lanc_a = verbos + fillers + r'\s+' + valor_re + r'\s*(?:reais|real)?\s*(?:no|na|em|com|de|para|pra)?\s*(.+)'
    
    print("t:", t)
    
    m_a = re.search(p_lanc_a, t)
    if m_a:
        print("m_a matches")
        g1 = m_a.group(1)
        g2 = m_a.group(2) or ""
        print(f"g1: '{g1}', g2: '{g2}'")
        valor = _parse_br_money(g1 + " " + g2)
        print("valor:", valor)
        if valor is not None:
            desc = _limpar_sujeira_string(m_a.group(3))
            print("desc:", desc)
            return "registrar_lancamento", {
                "valor": valor, "descricao": desc.capitalize(),
                "categoria": "Outros", "forma_pagamento": "Nao_informado", "tipo": "Saída"
            }
    return None

res = _detectar_e_extrair_acao_direta("Gastei 150 reais de gasolina hoje.")
print("RESULT:", res)
