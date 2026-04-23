import re

valor_re = r'(?:r\$?\s*)?([\d.,]+)\s*(mil(?:h[õo]es|ão)?|k)?'
verbos = r'\b(?:gastei|paguei|recebi|lanç[ao]r?|registra?r?|coloque?i?|comprei|compras?|adiciona?r?|anota?r?|gastar|gastou|comprar|pagar|receber|recebeu)\b'
fillers = r'(?:\s+(?:um|uma|o|a|os|as|do|da|no|na|em|com|de|valor|compra|gasto|despesa|receita|para|pra))*'

p_lanc_a = verbos + fillers + r'\s+' + valor_re + r'\s*(?:reais|real)?\s*(?:no|na|em|com|de|para|pra)?\s*(.+)'
p_lanc_b = verbos + fillers + r'\s+(.+?)\s+(?:por|de|foi|valor de|custou|r\$?\s*)?\s*' + valor_re + r'\s*(?:reais|real)?$'

t = "gastei 150 reais de gasolina hoje."
print("P_LANC_A:", re.search(p_lanc_a, t))
print("P_LANC_B:", re.search(p_lanc_b, t))
