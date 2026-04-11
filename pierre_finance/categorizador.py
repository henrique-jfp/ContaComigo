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


def limpar_descricao(descricao: str) -> str:
    """
    Remove ruídos e prefixos comuns de transações bancárias (Open Finance) 
    para facilitar a categorização por palavras-chave.
    Ex: 'PIX ENVIADO NETFLIX COM' -> 'netflix com'
    """
    if not descricao:
        return ""
    
    desc = descricao.lower()
    
    # Prefixos que poluem a descrição e impedem o match correto
    prefixos = [
        "pix enviado ", "pix recebido ", "ted enviada ", "ted recebida ", 
        "doc enviado ", "doc recebido ", "pagamento efetuado ", "pagamento recebido ",
        "compra no cartao ", "compra no debito ", "compra no credito ",
        "transferencia enviada ", "transferencia recebida ", "pagamento fatura ",
        "transf.enviada ", "transf.recebida ", "pgto ", "pagto ", "liquidacao ",
        "pagamento de conta ", "compra ", "venda "
    ]
    
    for p in prefixos:
        if desc.startswith(p):
            desc = desc[len(p):].strip()
            
    # Remover caracteres especiais repetidos que o Open Finance às vezes envia
    desc = re.sub(r'[\-\*\#\@\(\)]+', ' ', desc)
    return desc.strip()


# Mapeamento de tipos retornados pela API Open Finance (Pluggy/Pierre)
# para o padrão interno do sistema.
TIPO_OPEN_FINANCE_MAP: dict[str, str] = {
    # Padrão Pluggy / Pierre
    "CREDIT":  "Receita",
    "DEBIT":   "Despesa",
    # Variações defensivas
    "credit":  "Receita",
    "debit":   "Despesa",
    "Receita": "Receita",
    "Despesa": "Despesa",
}


def normalizar_tipo(tipo_raw: str) -> str:
    """Converte o tipo retornado pela API para 'Receita' ou 'Despesa'."""
    return TIPO_OPEN_FINANCE_MAP.get(tipo_raw, "Despesa")


# ---------------------------------------------------------------------------
# CAMADA 1 — Mapa de Palavras-Chave (por prioridade de categoria)
# ---------------------------------------------------------------------------
# IMPORTANTE: Todas as keywords são verificadas com word-boundary regex
# para evitar falsos positivos em dados brutos do Open Finance.

MAPA_CATEGORIAS: dict[str, dict[str, list[str]]] = {
    'SERVIÇOS E ASSINATURAS': {
        'Assinaturas': [
            'netflix', 'spotify', 'amazon prime', 'amazonprime', 'disney', 'hbo', 'globoplay',
            'youtube premium', 'deezer', 'apple tv', 'crunchyroll', 'paramount', 'claro flex',
            'claro rec', 'vivo', 'tim', 'oi', 'net virtua', 'sky', 'starlink', 'assinatura',
            'subscription', 'plano mensal', 'gympass', 'totalpass', 'canva', 'chatgpt', 'openai', 'wellhub',
            'midjourney', 'icloud', 'google one', 'dropbox', 'microsoft 365', 'adobe',
        ],
        'Financeiro': [
            'iof', 'tarifa', 'taxa bancaria', 'anuidade cartao', 'seguro', 'encargos', 'juros',
            'multa', 'mora', 'tbi', 'tar ', 'cesta servicos',
        ],
    },
    'ALIMENTAÇÃO': {
        'Restaurantes/Lanchonetes': [
            'ifood', 'rappi', 'uber eats', 'mcdonalds', 'burger king', 'subway', 'pizza', 'lanche',
            'restaurante', 'padaria', 'cafeteria', 'pastelaria', 'sushi', 'japones', 'churrascaria',
            'espetinho', 'outback', 'bacio di latte', 'madeiro', 'coco bambu', 'starbucks', 'habibs',
        ],
        'Mercado/Supermercado': [
            'mercado', 'supermercado', 'extra', 'pao de acucar', 'carrefour', 'atacadao', 'assai',
            'hortifruti', 'sacolao', 'feira', 'acougue', 'hortifrutti', 'zona sul', 'mundial', 'prezunic',
            'superprix', 'guanabara', 'st marche', 'obahortifruti',
        ],
        'Delivery': ['delivery', 'entrega', 'motoboy'],
    },
    'TRANSPORTE': {
        'Aplicativos': ['uber', '99pop', 'cabify', 'taxi', 'ladydriver', 'indriver'],
        'Combustivel': [
            'posto', 'combustivel', 'gasolina', 'etanol', 'shell', 'ipiranga',
            'br distribuidora', 'ale combustiveis', 'petrobras',
        ],
        'Estacionamento': ['estacionamento', 'parking', 'park', 'zona azul', 'sem parar', 'veloe'],
        'Transporte Publico': [
            'metro', 'metrô', 'onibus', 'oônibus', 'bilhete', 'riocard', 'cartao bom', 'sptrans',
        ],
    },
    'MORADIA': {
        'Aluguel': ['aluguel', 'locacao', 'imobiliaria', 'quinto andar', 'quintoandar'],
        'Condominio': ['condominio', 'taxa condominial', 'lume'],
        'Energia': [
            'cemig', 'copel', 'light', 'enel', 'energisa', 'coelba', 'celesc',
            'elektro', 'cpfl', 'electropaulo',
        ],
        'Agua': ['sabesp', 'cedae', 'copasa', 'embasa', 'saneago'],
        'Gas': ['comgas', 'ceg', 'ultragaz', 'liquigas'],
    },
    'SAÚDE': {
        'Farmacia': [
            'farmacia', 'drogasil', 'drogaria', 'ultrafarma', 'panvel',
            'onofre', 'nissei', 'pacheco', 'venancio', 'raia', 'droga raia',
        ],
        'Plano de Saude': [
            'plano saude', 'unimed', 'amil', 'bradesco saude', 'sulamerica saude',
            'hapvida', 'notredame', 'bradesco saude', 'saude bradesco',
        ],
        'Consultas': ['consulta medica', 'medico', 'clinica', 'hospital', 'pronto socorro', 'exame'],
    },
    'EDUCAÇÃO': {
        'Mensalidade': ['mensalidade', 'escola', 'faculdade', 'universidade', 'colegio', 'curso', 'udemy', 'alura', 'hotmart'],
        'Material': ['livraria', 'papelaria', 'saraiva', 'amazon livros', 'leitura'],
    },
    'VESTUÁRIO E BELEZA': {
        'Roupas e Calcados': [
            'zara', 'renner', 'cea', 'riachuelo', 'hering', 'marisa',
            'netshoes', 'centauro', 'lojas americanas', 'nike', 'adidas', 'arezzo',
        ],
        'Beleza': ['salao', 'barbearia', 'estetica', 'manicure', 'spa', 'oboticario', 'natura', 'sephora'],
    },
    'PET': {
        'Veterinario': ['veterinario', 'clinica veterinaria', 'petshop', 'pet shop', 'petz', 'cobasi'],
    },
    'LAZER E ENTRETENIMENTO': {
        'Cinema/Teatro': ['cinema', 'teatro', 'show', 'ingresso', 'ticket', 'sympla', 'eventbrite', 'cinemark', 'kinoplex'],
        'Jogos': ['steam', 'psn', 'xbox', 'nintendo', 'nuuvem', 'playstation', 'razer', 'epic games', 'roblox'],
        'Viagem': [
            'hotel', 'pousada', 'airbnb', 'booking', 'decolar', 'latam', 'gol',
            'azul', 'ryanair', 'passagem', 'voegol',
        ],
    },
    'FINANÇAS E INVESTIMENTOS': {
        'Salario': ['salario', 'pagamento folha', 'folha pagamento', 'vencimento', 'prolabore'],
        'Investimentos': [
            'cdb', 'lci', 'lca', 'tesouro', 'dividendo', 'rendimento',
            'juros recebidos', 'fundo', 'xp investimentos', 'btg pactual', 'nu invest',
        ],
        'Transferencia Recebida': ['transferencia recebida', 'pix recebido', 'ted recebido', 'ted recebida'],
    },
    'IMPOSTOS E TAXAS': {
        'Impostos': ['iptu', 'ipva', 'receita federal', 'sefaz', 'detran', 'multa', 'darf', 'irpf'],
    },
    'TRANSFERÊNCIAS': {
        'Enviada': ['pix enviado', 'ted enviado', 'doc enviado', 'transferencia enviada', 'ted enviada'],
        'Fatura': ['pagamento fatura', 'fatura cartao', 'pgto fatura'],
    },
}

# Normalização de nomes internos (UPPER) → nome exibido no banco
_MAPA_NOME_CATEGORIA: dict[str, str] = {
    'SERVIÇOS E ASSINATURAS':    'Serviços e Assinaturas',
    'ALIMENTAÇÃO':               'Alimentação',
    'TRANSPORTE':                'Transporte',
    'MORADIA':                   'Moradia',
    'SAÚDE':                     'Saúde',
    'EDUCAÇÃO':                  'Educação',
    'VESTUÁRIO E BELEZA':        'Vestuário e Beleza',
    'PET':                       'Pet',
    'LAZER E ENTRETENIMENTO':    'Lazer e Entretenimento',
    'FINANÇAS E INVESTIMENTOS':  'Financeiro',
    'IMPOSTOS E TAXAS':          'Impostos e Taxas',
    'TRANSFERÊNCIAS':            'Transferências',
}


def _build_pattern(keyword_norm: str) -> re.Pattern:
    """Compila um regex com word-boundary para a keyword normalizada."""
    return re.compile(rf'(?<!\w){re.escape(keyword_norm)}(?!\w)')


# Pré-compila todos os padrões na inicialização do módulo para ganho de performance.
_PADROES_COMPILADOS: dict[tuple[str, str, str], re.Pattern] = {
    (cat, sub, kw): _build_pattern(remove_accents(kw))
    for cat, subcats in MAPA_CATEGORIAS.items()
    for sub, keywords in subcats.items()
    for kw in keywords
}


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def categorizar_transacao(
    descricao: str,
    tipo_raw: str,
    db: Session,
    cat_cache: dict | None = None,
    subcat_cache: dict | None = None,
) -> tuple[int | None, int | None]:
    """
    Categoriza uma transação retornada pela API Open Finance (Pluggy/Pierre).

    Args:
        descricao:    Descrição bruta da transação (ex: 'PIX ENVIADO NETFLIX COM').
        tipo_raw:     Tipo conforme a API — 'CREDIT'/'DEBIT' ou 'Receita'/'Despesa'.
        db:           Sessão SQLAlchemy ativa.
        cat_cache:    Cache externo de {nome_cat: id}. Opcional.
        subcat_cache: Cache externo de {(cat_id, nome_sub): id}. Opcional.

    Returns:
        (categoria_id, subcategoria_id) ou (None, None) em caso de erro.
    """
    tipo = normalizar_tipo(tipo_raw)
    
    # 🛡️ NOVO: Limpeza da descrição antes da categorização
    desc_limpa = limpar_descricao(descricao)
    desc_norm = remove_accents(desc_limpa)

    cat_nome: str | None = None
    subcat_nome: str | None = None

    # ------------------------------------------------------------------
    # CAMADA 1: Busca por Keywords (com word-boundary, pré-compiladas)
    # ------------------------------------------------------------------
    # Prioridade para categorias específicas
    for c_nome, subcategorias in MAPA_CATEGORIAS.items():

        # 'FINANÇAS E INVESTIMENTOS' só para créditos (Receita)
        if c_nome == 'FINANÇAS E INVESTIMENTOS' and tipo != 'Receita':
            continue
            
        # Pula Transferências na primeira passada para dar chance a categorias específicas
        if c_nome == 'TRANSFERÊNCIAS':
            continue

        for s_nome, keywords in subcategorias.items():
            for kw in keywords:
                pattern = _PADROES_COMPILADOS[(c_nome, s_nome, kw)]
                if pattern.search(desc_norm):
                    cat_nome = c_nome
                    subcat_nome = s_nome
                    break
            if cat_nome:
                break
        if cat_nome:
            break

    # ------------------------------------------------------------------
    # CAMADA 1.5: Busca específica para TRANSFERÊNCIAS (baixa prioridade)
    # ------------------------------------------------------------------
    if not cat_nome:
        c_nome = 'TRANSFERÊNCIAS'
        subcategorias = MAPA_CATEGORIAS[c_nome]
        # Aqui usamos a descrição ORIGINAL pois os prefixos são as keywords de transferência
        desc_original_norm = remove_accents(descricao)
        
        for s_nome, keywords in subcategorias.items():
            for kw in keywords:
                pattern = _PADROES_COMPILADOS[(c_nome, s_nome, kw)]
                if pattern.search(desc_original_norm):
                    cat_nome = c_nome
                    subcat_nome = s_nome
                    break
            if cat_nome:
                break
    # ------------------------------------------------------------------
    # CAMADA 2: Fallback por tipo de transação
    # ------------------------------------------------------------------
    if not cat_nome:
        if tipo == 'Receita':
            cat_nome = 'Receita / Outros'
            subcat_nome = 'Outras Receitas'
        else:
            cat_nome = 'Outros'
            subcat_nome = 'Geral'

    # Converte nome interno (UPPER) para nome do banco
    cat_nome_db = _MAPA_NOME_CATEGORIA.get(cat_nome, cat_nome)

    # ------------------------------------------------------------------
    # CAMADA 3: Persistência no Banco com Cache
    # ------------------------------------------------------------------
    try:
        # --- Categoria ---
        if cat_cache is not None and cat_nome_db in cat_cache:
            cat_id = cat_cache[cat_nome_db]
        else:
            categoria_db = db.query(Categoria).filter(Categoria.nome == cat_nome_db).first()
            if not categoria_db:
                categoria_db = Categoria(nome=cat_nome_db)
                db.add(categoria_db)
                db.flush()
            cat_id = categoria_db.id
            if cat_cache is not None:
                cat_cache[cat_nome_db] = cat_id

        # --- Subcategoria ---
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
            if subcat_cache is not None:
                subcat_cache[sub_key] = subcat_id

        return cat_id, subcat_id

    except Exception as e:
        logger.error(f"Erro ao persistir categoria/subcategoria para '{descricao}': {e}")
        db.rollback()
        
        return None, None