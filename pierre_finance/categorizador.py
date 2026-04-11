import unicodedata
import re
from sqlalchemy.orm import Session
from models import Categoria, Subcategoria
import logging

logger = logging.getLogger(__name__)

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

# CAMADA 1: Mapa de Palavras-Chave (Organizado por prioridade)
MAPA_CATEGORIAS = {
    'SERVIÇOS E ASSINATURAS': {
        'Assinaturas': [
            'netflix', 'spotify', 'amazon prime', 'amazonprime', 'disney', 'hbo', 'globoplay', 
            'youtube premium', 'deezer', 'apple tv', 'crunchyroll', 'paramount', 'claro flex', 
            'claro rec', 'vivo', 'tim', 'oi', 'net virtua', 'sky', 'starlink', 'assinatura', 
            'subscription', 'plano mensal', 'gympass', 'totalpass'
        ],
        'Financeiro': ['iof', 'tarifa', 'taxa bancaria', 'anuidade cartao', 'anuidade cartão', 'seguro']
    },
    'ALIMENTAÇÃO': {
        'Restaurantes/Lanchonetes': [
            'ifood', 'rappi', 'uber eats', 'mcdonalds', 'burger king', 'subway', 'pizza', 'lanche',
            'restaurante', 'padaria', 'cafeteria', 'pastelaria', 'sushi', 'japones', 'churrascaria', 
            'espetinho', 'outback', 'bacio di latte', 'madeiro', 'coco bambu', 'starbucks'
        ],
        'Mercado/Supermercado': [
            'mercado', 'supermercado', 'extra', 'pao de acucar', 'carrefour', 'atacadao', 'assai',
            'hortifruti', 'sacolao', 'feira', 'acougue', 'hortifrutti', 'zona sul', 'mundial', 'prezunic'
        ],
        'Delivery': ['delivery', 'entrega', 'motoboy']
    },
    'TRANSPORTE': {
        'Aplicativos': ['uber', '99', 'cabify', 'taxi', '99pop', 'ladydriver'],
        'Combustivel': ['posto', 'combustivel', 'gasolina', 'etanol', 'shell', 'ipiranga', 'br distribuidora', 'ale combustiveis'],
        'Estacionamento': ['estacionamento', 'parking', 'park'],
        'Transporte Publico': ['metro', 'metrô', 'onibus', 'ônibus', 'bilhete', 'riocard', 'cartão bom', 'sptrans']
    },
    'MORADIA': {
        'Aluguel': ['aluguel', 'locação', 'locacao', 'imobiliaria'],
        'Condominio': ['condominio', 'condomínio', 'taxa condominial'],
        'Energia': ['cemig', 'copel', 'light', 'enel', 'energisa', 'coelba', 'celesc', 'elektro', 'cpfl', 'electropaulo'],
        'Agua': ['sabesp', 'cedae', 'copasa', 'embasa', 'saneago'],
        'Gas': ['gás', 'gas', 'comgas', 'ceg']
    },
    'SAÚDE': {
        'Farmacia': ['farmacia', 'drogasil', 'drogaria', 'ultrafarma', 'panvel', 'onofre', 'nissei', 'pacheco'],
        'Plano de Saude': ['plano saude', 'unimed', 'amil', 'bradesco saude', 'sulamerica saude', 'hapvida', 'notredame'],
        'Consultas': ['consulta', 'medico', 'médico', 'clinica', 'clínica', 'hospital', 'pronto socorro']
    },
    'LAZER E ENTRETENIMENTO': {
        'Cinema/Teatro': ['cinema', 'teatro', 'show', 'ingresso', 'ticket', 'sympla', 'eventbrite'],
        'Jogos': ['steam', 'psn', 'xbox', 'nintendo', 'nuuvem', 'playstation', 'razer'],
        'Viagem': ['hotel', 'pousada', 'airbnb', 'booking', 'decolar', 'latam', 'gol', 'azul', 'ryanair', 'passagem']
    },
    'FINANÇAS E INVESTIMENTOS': {
        'Salario': ['salario', 'salário', 'pagamento', 'folha'],
        'Investimentos': ['cdb', 'lci', 'lca', 'tesouro', 'dividendo', 'rendimento', 'juros recebidos', 'fundo'],
        'Transferencia Recebida': ['transferencia recebida', 'pix recebido', 'ted recebido']
    },
    'IMPOSTOS E TAXAS': {
        'Impostos': ['iptu', 'ipva', 'receita federal', 'sefaz', 'detran', 'multa', 'darf']
    }
}

def categorizar_transacao(descricao: str, tipo: str, db: Session, cat_cache: dict = None, subcat_cache: dict = None) -> tuple[int|None, int|None]:
    # Normalização agressiva: remove acentos, minúsculo e colapsa espaços duplos/triplos
    desc_norm = remove_accents(descricao)
    desc_norm = re.sub(r'\s+', ' ', desc_norm).strip()
    
    cat_nome = None
    subcat_nome = None

    # Regra de Ouro: Encargos financeiros (Juros, IOF, Multas)
    if any(k in desc_norm for k in ['juros', 'iof', 'multa', 'encargo', 'rotativo']):
        cat_nome = 'Financeiro'
        subcat_nome = 'Encargos e Juros'

    # CAMADA 1: Busca por Keywords (Apenas se não for juros)
    if not cat_nome:
        for c_nome, subcategorias in MAPA_CATEGORIAS.items():
            # Regra: Finanças e Investimentos apenas para Receita
            if c_nome == 'FINANÇAS E INVESTIMENTOS' and tipo != 'Receita':
                continue
                
            for s_nome, keywords in subcategorias.items():
                for kw in keywords:
                    kw_norm = remove_accents(kw)
                    # Proteção contra palavras curtas (ex: 'ir'): exige fronteira de palavra
                    if len(kw_norm) <= 2:
                        pattern = rf'\b{re.escape(kw_norm)}\b'
                        if re.search(pattern, desc_norm):
                            cat_nome = c_nome
                            subcat_nome = s_nome
                            break
                    elif kw_norm in desc_norm:
                        cat_nome = c_nome
                        subcat_nome = s_nome
                        break
                if cat_nome: break
            if cat_nome: break

    # CAMADA 2: Fallback por tipo
    if not cat_nome:
        if tipo == "Receita":
            cat_nome = "Receitas"
            subcat_nome = "Outras Receitas"
        else:
            cat_nome = "Outros"
            subcat_nome = "Geral"

    # Normalização de nomes para bater com o que está no banco (EXATO)
    mapa_fixo = {
        'SERVIÇOS E ASSINATURAS': 'Serviços e Assinaturas',
        'ALIMENTAÇÃO': 'Alimentação',
        'TRANSPORTE': 'Transporte',
        'MORADIA': 'Moradia',
        'SAÚDE': 'Saúde',
        'LAZER E ENTRETENIMENTO': 'Lazer e Entretenimento',
        'FINANÇAS E INVESTIMENTOS': 'Financeiro',
        'IMPOSTOS E TAXAS': 'Impostos e Taxas',
        'COMPRAS E VESTUÁRIO': 'Compras'
    }
    cat_nome = mapa_fixo.get(cat_nome, cat_nome)

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
