import unicodedata
from sqlalchemy.orm import Session
from models import Categoria, Subcategoria

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

MAPA_CATEGORIAS = {
    'ALIMENTAÇÃO': {
        'Restaurantes/Lanchonetes': [
            'ifood', 'rappi', 'uber eats', 'mcdonalds', 'burger king', 'subway', 'pizza', 'lanche',
            'restaurante', 'padaria', 'cafeteria', 'pastelaria', 'sushi', 'japonês', 'churrascaria', 'espetinho',
            'japones'
        ],
        'Mercado/Supermercado': [
            'mercado', 'supermercado', 'extra', 'pão de açúcar', 'pao de acucar', 'carrefour', 'atacadão', 'atacadao', 'assaí', 'assai',
            'hortifruti', 'sacolão', 'sacolao', 'feira', 'açougue', 'acougue', 'hortifrutti'
        ],
        'Delivery': [
            'delivery', 'entrega', 'motoboy'
        ],
        'Bebidas': [
            'bebida', 'cerveja', 'bar', 'boteco', 'choperia', 'vinho', 'destilaria'
        ]
    },
    'TRANSPORTE': {
        'Aplicativos': [
            'uber', '99', 'cabify', 'taxi', '99pop', 'ladydriver'
        ],
        'Combustível': [
            'posto', 'combustivel', 'gasolina', 'etanol', 'shell', 'ipiranga', 'br distribuidora', 'ale combustiveis'
        ],
        'Estacionamento': [
            'estacionamento', 'parking', 'park'
        ],
        'Transporte Público': [
            'metro', 'metrô', 'onibus', 'ônibus', 'bilhete', 'riocard', 'cartão bom', 'cartao bom', 'sptrans'
        ],
        'Pedágio': [
            'pedagio', 'pedágio', 'sem parar', 'conectcar', 'veloe'
        ]
    },
    'MORADIA': {
        'Aluguel': [
            'aluguel', 'locação', 'locacao', 'imobiliaria'
        ],
        'Condomínio': [
            'condominio', 'condomínio', 'taxa condominial'
        ],
        'Energia': [
            'cemig', 'copel', 'light', 'enel', 'energisa', 'coelba', 'celesc', 'elektro', 'cpfl',
            'electropaulo', 'energia eletrica'
        ],
        'Água': [
            'sabesp', 'cedae', 'copasa', 'embasa', 'saneago', 'caern', 'cagece', 'aguas do brasil', 'agua'
        ],
        'Internet/TV': [
            'claro', 'vivo', 'tim', 'oi', 'net', 'sky', 'starlink', 'brisanet', 'algar', 'telefonica',
            'banda larga', 'fibra'
        ],
        'Gás': [
            'gás', 'gas', 'comgas', 'ceg'
        ]
    },
    'SAÚDE': {
        'Farmácia': [
            'farmacia', 'drogasil', 'drogaria', 'ultrafarma', 'panvel', 'onofre', 'nissei'
        ],
        'Plano de Saúde': [
            'plano saude', 'unimed', 'amil', 'bradesco saude', 'sulamerica saude', 'hapvida', 'notredame'
        ],
        'Consultas': [
            'consulta', 'medico', 'médico', 'clinica', 'clínica', 'hospital', 'pronto socorro'
        ],
        'Exames': [
            'exame', 'laboratorio', 'laboratório', 'fleury', 'dasa', 'labi', 'hermes pardini'
        ]
    },
    'EDUCAÇÃO': {
        'Mensalidade': [
            'escola', 'faculdade', 'universidade', 'mensalidade', 'anuidade', 'matricula', 'matrícula'
        ],
        'Cursos': [
            'curso', 'udemy', 'coursera', 'alura', 'dio', 'hotmart', 'kiwify', 'edtech'
        ],
        'Material': [
            'livraria', 'amazon livros', 'saraiva', 'cultura', 'papelaria', 'material escolar'
        ]
    },
    'LAZER E ENTRETENIMENTO': {
        'Streaming': [
            'netflix', 'spotify', 'amazon prime', 'disney', 'hbo', 'globoplay', 'youtube premium',
            'deezer', 'apple tv', 'crunchyroll', 'paramount'
        ],
        'Cinema/Teatro': [
            'cinema', 'teatro', 'show', 'ingresso', 'ticket', 'sympla', 'eventbrite'
        ],
        'Jogos': [
            'steam', 'psn', 'xbox', 'nintendo', 'nuuvem', 'playstation', 'razer', 'game'
        ],
        'Viagem': [
            'hotel', 'pousada', 'airbnb', 'booking', 'decolar', 'latam', 'gol', 'azul', 'ryanair',
            'emirates', 'passagem'
        ]
    },
    'COMPRAS E VESTUÁRIO': {
        'Roupas': [
            'renner', 'riachuelo', 'c&a', 'hering', 'zara', 'marisa', 'forever 21', 'farm',
            'arezzo', 'reserva'
        ],
        'Eletrônicos': [
            'kabum', 'terabyte', 'pichau', 'americanas', 'magazineluiza', 'magazine luiza',
            'shoptime', 'casas bahia', 'fast shop', 'apple store'
        ],
        'E-commerce': [
            'amazon', 'mercado livre', 'shopee', 'alibaba', 'aliexpress', 'shein', 'wish'
        ]
    },
    'PETS': {
        'Pet Shop': [
            'petshop', 'pet shop', 'cobasi', 'petz', 'agropet', 'veterinario', 'veterinário',
            'clinica veterinaria'
        ]
    },
    'FINANÇAS E INVESTIMENTOS': {
        'Salário': [
            'salario', 'salário', 'pagamento', 'folha'
        ],
        'Investimentos': [
            'cdb', 'lci', 'lca', 'tesouro', 'dividendo', 'rendimento', 'juros recebidos', 'fundo'
        ],
        'Transferência Recebida': [
            'transferencia recebida', 'pix recebido', 'ted recebido'
        ]
    },
    'SERVIÇOS': {
        'Assinaturas': [
            'assinatura', 'subscription', 'plano mensal'
        ],
        'Financeiro': [
            'iof', 'tarifa', 'taxa bancaria', 'anuidade cartao', 'anuidade cartão', 'seguro', 'juros'
        ]
    },
    'IMPOSTOS E TAXAS': {
        'Impostos': [
            'iptu', 'ipva', 'ir', 'imposto', 'receita federal', 'sefaz', 'detran', 'multa'
        ]
    },
    'PIX / TRANSFERÊNCIAS': {
        'Pix Enviado': [
            'pix enviado', 'transferencia enviada', 'ted enviado'
        ]
    }
}

# Normalizando o mapa uma vez na carga
MAPA_NORMALIZADO = {}
for cat, subcats in MAPA_CATEGORIAS.items():
    MAPA_NORMALIZADO[cat] = {}
    for subcat, keywords in subcats.items():
        MAPA_NORMALIZADO[cat][subcat] = [remove_accents(kw) for kw in keywords]


def categorizar_transacao(descricao: str, tipo: str, db: Session) -> tuple[int|None, int|None]:
    """
    Categoriza uma transação baseada na descrição. Retorna (id_categoria, id_subcategoria).
    """
    desc_norm = remove_accents(descricao)
    
    cat_encontrada = None
    subcat_encontrada = None
    
    # Camada 1: Busca no mapa
    for cat_nome, subcats in MAPA_NORMALIZADO.items():
        # Regra especial: Finanças e Investimentos apenas para receitas
        if cat_nome == 'FINANÇAS E INVESTIMENTOS' and tipo != 'Receita':
            continue
            
        for subcat_nome, keywords in subcats.items():
            if any(kw in desc_norm for kw in keywords):
                cat_encontrada = cat_nome
                subcat_encontrada = subcat_nome
                break
        if cat_encontrada:
            break
            
    # Camada 2: Fallback por tipo
    if not cat_encontrada:
        if tipo == 'Receita':
            cat_encontrada = 'Receita / Outros'
            subcat_encontrada = 'Outras Receitas'
        else:
            cat_encontrada = 'Outros'
            subcat_encontrada = 'Geral'
            
    # Camada 3: Buscar ou Criar no BD
    # Buscar Categoria
    categoria_db = db.query(Categoria).filter(Categoria.nome == cat_encontrada).first()
    if not categoria_db:
        categoria_db = Categoria(nome=cat_encontrada)
        db.add(categoria_db)
        db.flush()
        
    # Buscar Subcategoria
    subcategoria_db = db.query(Subcategoria).filter(
        Subcategoria.nome == subcat_encontrada,
        Subcategoria.id_categoria == categoria_db.id
    ).first()
    
    if not subcategoria_db:
        subcategoria_db = Subcategoria(nome=subcat_encontrada, id_categoria=categoria_db.id)
        db.add(subcategoria_db)
        db.flush()
        
    return categoria_db.id, subcategoria_db.id
