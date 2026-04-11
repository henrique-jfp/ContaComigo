import unicodedata
from sqlalchemy.orm import Session
from models import Categoria, Subcategoria
import logging

logger = logging.getLogger(__name__)

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

# CAMADA 1: Mapa de Palavras-Chave
MAPA_CATEGORIAS = {
    'ALIMENTAÇÃO': {
        'Restaurantes/Lanchonetes': [
            'ifood', 'rappi', 'uber eats', 'mcdonalds', 'burger king', 'subway', 'pizza', 'lanche',
            'restaurante', 'padaria', 'cafeteria', 'pastelaria', 'sushi', 'japonês', 'churrascaria', 'espetinho'
        ],
        'Mercado/Supermercado': [
            'mercado', 'supermercado', 'extra', 'pão de açúcar', 'carrefour', 'atacadão', 'assaí',
            'hortifruti', 'sacolão', 'feira', 'açougue', 'hortifrutti'
        ],
        'Delivery': ['delivery', 'entrega', 'motoboy'],
        'Bebidas': ['bebida', 'cerveja', 'bar', 'boteco', 'choperia', 'vinho', 'destilaria']
    },
    'TRANSPORTE': {
        'Aplicativos': ['uber', '99', 'cabify', 'taxi', '99pop', 'ladydriver'],
        'Combustível': ['posto', 'combustivel', 'gasolina', 'etanol', 'shell', 'ipiranga', 'br distribuidora', 'ale combustiveis'],
        'Estacionamento': ['estacionamento', 'parking', 'park'],
        'Transporte Público': ['metro', 'metrô', 'onibus', 'ônibus', 'bilhete', 'riocard', 'cartão bom', 'sptrans'],
        'Pedágio': ['pedagio', 'pedágio', 'sem parar', 'conectcar', 'veloe']
    },
    'MORADIA': {
        'Aluguel': ['aluguel', 'locação', 'locacao', 'imobiliaria'],
        'Condomínio': ['condominio', 'condomínio', 'taxa condominial'],
        'Energia': ['cemig', 'copel', 'light', 'enel', 'energisa', 'coelba', 'celesc', 'elektro', 'cpfl', 'electropaulo', 'energia eletrica'],
        'Água': ['sabesp', 'cedae', 'copasa', 'embasa', 'saneago', 'caern', 'cagece', 'aguas do brasil'],
        'Internet/TV': ['claro', 'vivo', 'tim', 'oi', 'net', 'sky', 'starlink', 'brisanet', 'algar', 'telefonica', 'banda larga', 'fibra'],
        'Gás': ['gás', 'gas', 'comgas', 'ceg']
    },
    'SAÚDE': {
        'Farmácia': ['farmacia', 'drogasil', 'drogaria', 'ultrafarma', 'panvel', 'onofre', 'nissei'],
        'Plano de Saúde': ['plano saude', 'unimed', 'amil', 'bradesco saude', 'sulamerica saude', 'hapvida', 'notredame'],
        'Consultas': ['consulta', 'medico', 'médico', 'clinica', 'clínica', 'hospital', 'pronto socorro'],
        'Exames': ['exame', 'laboratorio', 'laboratório', 'fleury', 'dasa', 'labi', 'hermes pardini']
    },
    'EDUCAÇÃO': {
        'Mensalidade': ['escola', 'faculdade', 'universidade', 'mensalidade', 'anuidade', 'matricula', 'matrícula'],
        'Cursos': ['curso', 'udemy', 'coursera', 'alura', 'dio', 'hotmart', 'kiwify', 'edtech'],
        'Material': ['livraria', 'amazon livros', 'saraiva', 'cultura', 'papelaria', 'material escolar']
    },
    'LAZER E ENTRETENIMENTO': {
        'Streaming': ['netflix', 'spotify', 'amazon prime', 'disney', 'hbo', 'globoplay', 'youtube premium', 'deezer', 'apple tv', 'crunchyroll', 'paramount'],
        'Cinema/Teatro': ['cinema', 'teatro', 'show', 'ingresso', 'ticket', 'sympla', 'eventbrite'],
        'Jogos': ['steam', 'psn', 'xbox', 'nintendo', 'nuuvem', 'playstation', 'razer', 'game'],
        'Viagem': ['hotel', 'pousada', 'airbnb', 'booking', 'decolar', 'latam', 'gol', 'azul', 'ryanair', 'emirates', 'passagem']
    },
    'COMPRAS E VESTUÁRIO': {
        'Roupas': ['renner', 'riachuelo', 'c&a', 'hering', 'zara', 'marisa', 'forever 21', 'farm', 'arezzo', 'reserva'],
        'Eletrônicos': ['kabum', 'terabyte', 'pichau', 'americanas', 'magazineluiza', 'magazine luiza', 'shoptime', 'casas bahia', 'fast shop', 'apple store'],
        'E-commerce': ['amazon', 'mercado livre', 'shopee', 'alibaba', 'aliexpress', 'shein', 'wish']
    },
    'PETS': {
        'Pet Shop': ['petshop', 'pet shop', 'cobasi', 'petz', 'agropet', 'veterinario', 'veterinário', 'clinica veterinaria']
    },
    'FINANÇAS E INVESTIMENTOS': {
        'Salário': ['salario', 'salário', 'pagamento', 'folha'],
        'Investimentos': ['cdb', 'lci', 'lca', 'tesouro', 'dividendo', 'rendimento', 'juros recebidos', 'fundo'],
        'Transferência Recebida': ['transferencia recebida', 'pix recebido', 'ted recebido']
    },
    'SERVIÇOS': {
        'Assinaturas': ['assinatura', 'subscription', 'plano mensal'],
        'Financeiro': ['iof', 'tarifa', 'taxa bancaria', 'anuidade cartao', 'anuidade cartão', 'seguro']
    },
    'IMPOSTOS E TAXAS': {
        'Impostos': ['iptu', 'ipva', 'ir', 'imposto', 'receita federal', 'sefaz', 'detran', 'multa']
    },
    'PIX / TRANSFERÊNCIAS': {
        'Pix Enviado': ['pix enviado', 'transferencia enviada', 'ted enviado']
    }
}

def categorizar_transacao(descricao: str, tipo: str, db: Session, cat_cache: dict = None, subcat_cache: dict = None) -> tuple[int|None, int|None]:
    desc_norm = remove_accents(descricao)
    
    cat_nome = None
    subcat_nome = None

    # CAMADA 1: Busca por Keywords
    for c_nome, subcategorias in MAPA_CATEGORIAS.items():
        # Regra: Finanças e Investimentos apenas para Receita
        if c_nome == 'FINANÇAS E INVESTIMENTOS' and tipo != 'Receita':
            continue
            
        for s_nome, keywords in subcategorias.items():
            if any(remove_accents(kw) in desc_norm for kw in keywords):
                cat_nome = c_nome
                subcat_nome = s_nome
                break
        if cat_nome: break

    # CAMADA 2: Fallback por tipo
    if not cat_nome:
        if tipo == "Receita":
            cat_nome = "Receita / Outros"
            subcat_nome = "Outras Receitas"
        else:
            cat_nome = "Outros"
            subcat_nome = "Geral"

    # CAMADA 3: Persistência no Banco com Cache
    try:
        # Busca Categoria
        if cat_cache is not None and cat_nome in cat_cache:
            cat_id = cat_cache[cat_nome]
        else:
            categoria_db = db.query(Categoria).filter(Categoria.nome == cat_nome).first()
            if not categoria_db:
                categoria_db = Categoria(nome=cat_nome)
                db.add(categoria_db)
                db.flush()
            cat_id = categoria_db.id
            if cat_cache is not None:
                cat_cache[cat_nome] = cat_id

        # Busca Subcategoria
        sub_key = (cat_id, subcat_nome)
        if subcat_cache is not None and sub_key in subcat_cache:
            subcat_id = subcat_cache[sub_key]
        else:
            subcat_db = db.query(Subcategoria).filter(
                Subcategoria.nome == subcat_nome,
                Subcategoria.id_categoria == cat_id
            ).first()
            if not subcat_db:
                subcat_db = Subcategoria(nome=subcat_nome, id_categoria=cat_id)
                db.add(subcat_db)
                db.flush()
            subcat_id = subcat_db.id
            if subcat_cache is not None:
                subcat_cache[sub_key] = subcat_id

        return cat_id, subcat_id
    except Exception as e:
        logger.error(f"Erro ao persistir categoria/subcat: {e}")
        return None, None
