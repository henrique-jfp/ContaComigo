import re
import json

def extract_json_or_text(texto):
    # Se contém a flag "funcao":, vamos arrancar esse JSON por bem ou por mal
    if '"funcao"' in texto or "'funcao'" in texto:
        match = re.search(r'(\{[\s\S]*"funcao"[\s\S]*\})', texto)
        if match:
            try:
                # Tenta parsear. Se for JSON mesmo, bingo
                return json.loads(match.group(1))
            except:
                pass
    return None

print(extract_json_or_text("Claro! Vou buscar: ```json\n{\"funcao\": \"test\"}\n``` "))
print(extract_json_or_text("{\"funcao\": \"test\"}"))
