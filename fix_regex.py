import glob

files = glob.glob("gerente_financeiro/*.py")
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    old = r"r'^(?i)/?\s*(cancelar|cancel|sair|parar)$'"
    new = r"r'(?i)^/?\s*(cancelar|cancel|sair|parar)$'"
    
    if old in content:
        content = content.replace(old, new)
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Fixed {f}")
