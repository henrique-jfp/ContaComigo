import re
import json
def _limpar_resposta_ia(texto: str) -> str:
    texto_limpo = re.sub(r'^```(html|json)?\n', '', texto, flags=re.MULTILINE)
    texto_limpo = re.sub(r'```$', '', texto_limpo, flags=re.MULTILINE)
    return texto_limpo

s = "```\n{\"funcao\": \"listar_lancamentos\", \"parametros\": {\"limit\": 1}}\n```"
clean = _limpar_resposta_ia(s)
print('CLEAN:', repr(clean))
try:
    json.loads(clean)
    print('JSON LOAD OK')
except Exception as e:
    print('JSON LOAD FAILED:', e)
