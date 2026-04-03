files = [
    'gerente_financeiro/handlers.py',
    'gerente_financeiro/manual_entry_handler.py',
    'gerente_financeiro/editing_handler.py'
]
for file in files:
    with open(file, 'r') as f:
        text = f.read()
    
    if ")]]," in text:
        text = text.replace(")]],", ")],")
    
    with open(file, 'w') as f:
        f.write(text)
