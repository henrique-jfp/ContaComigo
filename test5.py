import re
def _limpar_resposta_ia(texto: str) -> str:
    # Relaxando a regex para pegar crases no início e no fim, mesmo com espaços o
    # Remove bloco markdown inteiro se houver
    # Melhor forma: pegar apenas o miolo se estiver entre ```json e ```
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', texto, re.DOTALL | re.IGNORECASE)
    if match:
        texto = match.group(1)
    else:
        # Se não encontrou o bloco completo, tenta limpar o sujo mesmo
        texto = re.sub(r'^```(html|json)?\s*\n?', '', texto, flags=re.MULTILINE | re.IGNORECASE)
        texto = re.sub(r'\n?```\s*$', '', texto, flags=re.MULTILINE)
        texto = re.sub(r'```', '', texto) # Força a remoção de crases perdidas
    return texto.strip()

print(repr(_limpar_resposta_ia("```json\n{\"a\": 1}\n```  ")))
print(repr(_limpar_resposta_ia("   ```\n{\"a\": 1}\n```")))
