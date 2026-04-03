import re
def extract_json(texto):
    match = re.search(r'(\{.*\})', texto, re.DOTALL)
    if match:
        return match.group(1)
    return texto

s = "Aqui está:\n```json\n{\"a\": 1}\n```\nE pronto."
print(repr(extract_json(s)))
