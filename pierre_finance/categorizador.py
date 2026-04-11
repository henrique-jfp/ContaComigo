import unicodedata
import re
from sqlalchemy.orm import Session
from models import Categoria, Subcategoria
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

TIPO_OPEN_FINANCE_MAP: dict[str, str] = {
    "CREDIT":  "Receita",
    "DEBIT":   "Despesa",
    "credit":  "Receita",
    "debit":   "Despesa",
    "Receita": "Receita",
    "Despesa": "Despesa",
}

def normalizar_tipo(tipo_raw: str) -> str:
    return TIPO_OPEN_FINANCE_MAP.get(tipo_raw, "Despesa")

# ---------------------------------------------------------------------------
# MAPA DE CATEGORIAS (Nomes exatos conforme o Banco de Dados)
# ---------------------------------------------------------------------------
MAPA_CATEGORIAS: dict[str, dict[str, list[str]]] = {
    'Serviços e Assinaturas': {
        'Assinaturas': [
            'netflix', 'spotify', 'amazon prime', 'amazonprime', 'disney', 'hbo', 'globoplay',
            'youtube premium', 'deezer', 'apple tv', 'crunchyroll', 'paramount', 'claro flex',
            'claro rec', 'vivo', 'tim', 'oi', 'net virtua', 'sky', 'starlink', 'assinatura',
            'subscription', 'plano mensal', 'gympass', 'totalpass',
        ],
    },
    'Financeiro': {
        'Encargos': [
            'iof', 'tarifa', 'taxa bancaria', 'anuidade cartao', 'seguro',
            'juros', 'multa', 'encargo', 'rotativo'
        ],
    },
    'Alimentação': {
        'Restaurantes/Lanchonetes': [
            'ifood', 'rappi', 'uber eats', 'mcdonalds', 'burger king', 'subway', 'pizza', 'lanche',
            'restaurante', 'padaria', 'cafeteria', 'pastelaria', 'sushi', 'japones', 'churrascaria',
            'espetinho', 'outback', 'bacio di latte', 'madeiro', 'coco bambu', 'starbucks',
        ],
        'Mercado/Supermercado': [
            'mercado', 'supermercado', 'extra', 'pao de acucar', 'carrefour', 'atacadao', 'assai',
            'hortifruti', 'sacolao', 'feira', 'acougue', 'hortifrutti', 'zona sul', 'mundial', 'prezunic',
        ],
        'Delivery': ['delivery', 'entrega', 'motoboy'],
    },
    'Transporte': {
        'Aplicativos': ['uber', '99pop', 'cabify', 'taxi', 'ladydriver'],
        'Combustivel': [
            'posto', 'combustivel', 'gasolina', 'etanol', 'shell', 'ipiranga',
            'br distribuidora', 'ale combustiveis',
        ],
        'Estacionamento': ['estacionamento', 'parking', 'park'],
        'Transporte Publico': [
            'metro', 'metrô', 'onibus', 'bilhete', 'riocard', 'cartao bom', 'sptrans',
        ],
    },
    'Moradia': {
        'Aluguel': ['aluguel', 'locacao', 'imobiliaria'],
        'Condominio': ['condominio', 'taxa condominial'],
        'Energia': [
            'cemig', 'copel', 'light', 'enel', 'energisa', 'coelba', 'celesc',
            'elektro', 'cpfl', 'electropaulo',
        ],
        'Agua': ['sabesp', 'cedae', 'copasa', 'embasa', 'saneago'],
        'Gas': ['comgas', 'ceg'],
    },
    'Saúde': {
        'Farmacia': [
            'farmacia', 'drogasil', 'drogaria', 'ultrafarma', 'panvel',
            'onofre', 'nissei', 'pacheco',
        ],
        'Plano de Saude': [
            'plano saude', 'unimed', 'amil', 'bradesco saude', 'sulamerica saude',
            'hapvida', 'notredame',
        ],
        'Consultas': ['consulta medica', 'medico', 'clinica', 'hospital', 'pronto socorro'],
    },
    'Educação': {
        'Mensalidade': ['mensalidade', 'escola', 'faculdade', 'universidade', 'colegio', 'curso'],
        'Material': ['livraria', 'papelaria', 'saraiva', 'amazon livros'],
    },
    'Lazer e Entretenimento': {
        'Cinema/Teatro': ['cinema', 'teatro', 'show', 'ingresso', 'ticket', 'sympla', 'eventbrite'],
        'Jogos': ['steam', 'psn', 'xbox', 'nintendo', 'nuuvem', 'playstation', 'razer'],
        'Viagem': [
            'hotel', 'pousada', 'airbnb', 'booking', 'decolar', 'latam', 'gol',
            'azul', 'ryanair', 'passagem',
        ],
    },
    'Receitas': {
        'Salario': ['salario', 'pagamento folha', 'folha pagamento'],
        'Investimentos': [
            'cdb', 'lci', 'lca', 'tesouro', 'dividendo', 'rendimento',
            'juros recebidos', 'fundo',
        ],
        'Recebidos': ['transferencia recebida', 'pix recebido', 'ted recebido'],
    },
    'Impostos e Taxas': {
        'Impostos': ['iptu', 'ipva', 'receita federal', 'sefaz', 'detran', 'multa', 'darf'],
    },
    'Transferências': {
        'Enviada': ['pix enviado', 'ted enviado', 'doc enviado', 'transferencia enviada'],
        'Fatura': ['pagamento fatura', 'fatura cartao'],
    },
}

def _build_pattern(keyword_norm: str) -> re.Pattern:
    return re.compile(rf'(?<!\w){re.escape(keyword_norm)}(?!\w)')

_PADROES_COMPILADOS: dict[tuple[str, str, str], re.Pattern] = {
    (cat, sub, kw): _build_pattern(remove_accents(kw))
    for cat, subcats in MAPA_CATEGORIAS.items()
    for sub, keywords in subcats.items()
    for kw in keywords
}

def categorizar_transacao(
    descricao: str,
    tipo_raw: str,
    db: Session,
    cat_cache: dict | None = None,
    subcat_cache: dict | None = None,
) -> tuple[int | None, int | None]:
    tipo = normalizar_tipo(tipo_raw)
    
    # Normalização agressiva: remove espaços duplos antes da análise
    desc_norm = remove_accents(descricao)
    desc_norm = re.sub(r'\s+', ' ', desc_norm).strip()

    cat_nome: str | None = None
    subcat_nome: str | None = None

    # CAMADA 1: Busca por Keywords (Regex Word-boundary)
    for c_nome, subcategorias in MAPA_CATEGORIAS.items():
        if c_nome == 'Receitas' and tipo != 'Receita':
            continue

        for s_nome, keywords in subcategorias.items():
            for kw in keywords:
                pattern = _PADROES_COMPILADOS.get((c_nome, s_nome, kw))
                if pattern and pattern.search(desc_norm):
                    cat_nome = c_nome
                    subcat_nome = s_nome
                    break
            if cat_nome: break
        if cat_nome: break

    # CAMADA 2: Fallback por tipo
    if not cat_nome:
        if tipo == 'Receita':
            cat_nome = 'Receitas'
            subcat_nome = 'Outras Receitas'
        else:
            cat_nome = 'Outros'
            subcat_nome = 'Geral'

    # CAMADA 3: Persistência no Banco com Cache
    try:
        if cat_cache is not None and cat_nome in cat_cache:
            cat_id = cat_cache[cat_nome]
        else:
            categoria_db = db.query(Categoria).filter(Categoria.nome == cat_nome).first()
            if not categoria_db:
                categoria_db = Categoria(nome=cat_nome)
                db.add(categoria_db)
                db.flush()
            cat_id = categoria_db.id
            if cat_cache is not None: cat_cache[cat_nome] = cat_id

        sub_key = (cat_id, subcat_nome)
        if subcat_cache is not None and sub_key in subcat_cache:
            subcat_id = subcat_cache[sub_key]
        else:
            subcat_db = db.query(Subcategoria).filter(
                Subcategoria.nome == subcat_nome,
                Subcategoria.id_categoria == cat_id,
            ).first()
            if not subcat_db:
                subcat_db = Subcategoria(nome=subcat_nome, id_categoria=cat_id)
                db.add(subcat_db)
                db.flush()
            subcat_id = subcat_db.id
            if subcat_cache is not None: subcat_cache[sub_key] = subcat_id

        return cat_id, subcat_id

    except Exception as e:
        logger.error(f"Erro ao persistir categoria/subcategoria para '{descricao}': {e}")
        db.rollback()
        return None, None
