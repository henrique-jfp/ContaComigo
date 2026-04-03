import re
import json
def _limpar_resposta_ia(texto: str) -> str:
    texto_limpo = re.sub(r'^```(html|json)?\n', '', texto, flags=re.MULTILINE)
    texto_limpo = re.sub(r'```$', '', texto_limpo, flags=re.MULTILINE)
    return texto_limpo

s = "```json\n{\"funcao\": \"listar_lancamentos\"}\n```\n"
print("CLEAN:", repr(_limpar_resposta_ia(s)))
try:
    print(json.loads(_limpar_resposta_ia(s)))
except Exception as e:
    print("ERR:", e)
