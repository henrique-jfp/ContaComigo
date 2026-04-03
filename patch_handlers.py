import sys
with open('gerente_financeiro/handlers.py', 'r', encoding='utf-8') as f:
    text = f.read()

OLD = """        try:
            # Tenta decodificar a resposta como JSON
            dados_funcao = json.loads(resposta_ia)
            if isinstance(dados_funcao, dict) and "funcao" in dados_funcao:"""
            
NEW = """        dados_funcao = None
        # 🔥 Magia negra do Enzo: Se tiver "funcao", a gente arranca o JSON na marra, mesmo com lixo em volta!
        import re
        if '"funcao"' in resposta_ia or "'funcao'" in resposta_ia:
            match = re.search(r'(\\{[\\s\\S]*"funcao"[\\s\\S]*\\})', resposta_ia)
            if match:
                try: dados_funcao = json.loads(match.group(1))
                except: pass
                
        try:
            # Se não extraiu no regex maluco, tenta o parser normal
            if not dados_funcao:
                dados_funcao = json.loads(resposta_ia)
                
            if isinstance(dados_funcao, dict) and "funcao" in dados_funcao:"""

if OLD in text:
    text = text.replace(OLD, NEW)
    with open('gerente_financeiro/handlers.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("PATCH APPLIED SUCCESSFULLY")
else:
    print("OLD STRING NOT FOUND")
