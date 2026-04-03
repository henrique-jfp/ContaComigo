import sys
with open('gerente_financeiro/services.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Correcao 1: Pandas Dataframe (analisar_comportamento_financeiro)
OLD1 = """    despesas_df = df[df['tipo'] == 'Despesa'].copy()
    receitas_df = df[df['tipo'] == 'Receita'].copy()"""
    
NEW1 = """    despesas_df = df[df['tipo'].isin(['Despesa', 'despesa', 'Saída', 'saída', 'Saida', 'saida'])].copy()
    receitas_df = df[df['tipo'].isin(['Receita', 'receita', 'Entrada', 'entrada'])].copy()"""

if OLD1 in text:
    text = text.replace(OLD1, NEW1)
    
# Correcao 2: resumo_mensal no cache base
OLD2 = """        if l.tipo == 'Receita':
            resumo_mensal[mes_ano]['receitas'] += float(l.valor)
        else:
            resumo_mensal[mes_ano]['despesas'] += float(l.valor)"""
            
NEW2 = """        tipo_min = (l.tipo or '').lower()
        if tipo_min in ['receita', 'entrada']:
            resumo_mensal[mes_ano]['receitas'] += float(l.valor)
        elif tipo_min in ['despesa', 'saída', 'saida']:
            resumo_mensal[mes_ano]['despesas'] += float(l.valor)"""

if OLD2 in text:
    text = text.replace(OLD2, NEW2)

with open('gerente_financeiro/services.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Fix aplicado ao services.py")

