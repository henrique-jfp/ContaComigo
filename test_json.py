import re
def _limpar_resposta_ia(texto: str) -> str:
    texto_limpo = re.sub(r'^```(html|json)?\n', '', texto, flags=re.MULTILINE)
    texto_limpo = re.sub(r'```$', '', texto_limpo, flags=re.MULTILINE)
    return texto_limpo

s = "```json\n{\"funcao\": \"listar_lancamentos\", \"parametros\": {\"limit\": 1}}\n```"
print("CLEAN:", repr(_limpar_resposta_ia(s)))
