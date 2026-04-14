import unicodedata
import re
from sqlalchemy.orm import Session
from models import Categoria, Subcategoria, Lancamento
import logging
from finance_utils import normalize_financial_type

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
        "pagamento de conta ", "compra ", "venda ", "pago por ", "enviado por ",
        "pagamento ", "liquidação "
    ]
    
    for p in prefixos:
        if desc.startswith(p):
            desc = desc[len(p):].strip()
            
    # Remover IDs de transação e datas comuns no final (ex: '20240325' ou '12345678')
    desc = re.sub(r'\d{6,20}', '', desc)
    # Remover caracteres especiais repetidos que o Open Finance às vezes envia
    desc = re.sub(r'[\-\*\#\@\(\)\.]+ ', ' ', desc)
    desc = re.sub(r' +', ' ', desc)
    return desc.strip()


# Mapeamento de tipos retornados pela API Open Finance (Pluggy/Pierre)
# para o padrão interno do sistema.
def normalizar_tipo(tipo_raw: str) -> str:
    """Converte o tipo retornado pela API para 'Receita' ou 'Despesa'."""
    return normalize_financial_type(tipo_raw, default="Despesa")


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
            'midjourney', 'icloud', 'google one', 'dropbox', 'microsoft 365', 'adobe', 'smartfit',
            'bluefit', 'selfit', 'sky', 'directv', 'globomail', 'uol', 'terra', 'globo.com', 'cr flamengo',
            'socio torcedor', 'flamengo', 'sportv', 'premiere',
        ],
        'Financeiro': [
            'seguro', 'seguro vida', 'seguro residencial', 'seguro celular', 'pagamento seguro',
        ],
    },
    'JUROS E ENCARGOS': {
        'Juros': ['juros', 'mora', 'encargo', 'encargos'],
        'IOF': ['iof'],
        'Anuidade': ['anuidade', 'taxa anuidade', 'anuidade cartao'],
        'Multas': ['multa', 'tarifa', 'taxa bancaria', 'tbi', 'tar ', 'cesta servicos', 'manutencao conta', 'mensalidade banco', 'pacote servicos'],
    },
    'EMPRÉSTIMOS E FINANCIAMENTOS': {
        'Parcela de Veículo': ['financiamento veiculo', 'bv financeira', 'itau financiamento', 'parcela carro', 'moto'],
        'Empréstimo Pessoal': ['emprestimo', 'credito pessoal', 'parcela emprestimo', 'consignado'],
        'Financiamento Imobiliário': ['financiamento habitacional', 'caixa habita', 'parcela imovel', 'mcmv'],
    },
    'ALIMENTAÇÃO': {
        'Restaurantes/Lanchonetes': [
            'ifood', 'rappi', 'uber eats', 'mcdonalds', 'burger king', 'subway', 'pizza', 'lanche',
            'restaurante', 'padaria', 'cafeteria', 'pastelaria', 'sushi', 'japones', 'churrascaria',
            'espetinho', 'outback', 'bacio di latte', 'madeiro', 'coco bambu', 'starbucks', 'habibs',
            'giraffas', 'spoleto', 'bob s', 'domino s', 'pizzaria', 'chocolates', 'cacau show', 'kopenhagen',
            'sorveteria', 'doceria', 'bar ', 'boteco', 'cervejaria', 'pub', 'gastrobar',
        ],
        'Mercado/Supermercado': [
            'mercado', 'supermercado', 'extra', 'pao de acucar', 'carrefour', 'atacadao', 'assai',
            'hortifruti', 'sacolao', 'feira', 'acougue', 'hortifrutti', 'zona sul', 'mundial', 'prezunic',
            'superprix', 'guanabara', 'st marche', 'obahortifruti', 'supermercados', 'minimercado', 'mercantil',
            'bahamas', 'dia ', 'condor', 'muffato', 'angeloni', 'zaffari', 'supermkt',
        ],
        'Delivery': ['delivery', 'entrega', 'motoboy', 'taxa entrega', 'loggi'],
    },
    'TRANSPORTE': {
        'Aplicativos': ['uber', '99pop', 'cabify', 'taxi', 'ladydriver', 'indriver', '99app', 'uber trip'],
        'Combustivel': [
            'posto', 'combustivel', 'gasolina', 'etanol', 'shell', 'ipiranga',
            'br distribuidora', 'ale combustiveis', 'petrobras', 'texaco', 'dislub', 'posto ',
        ],
        'Estacionamento': ['estacionamento', 'parking', 'park', 'zona azul', 'sem parar', 'veloe', 'taggy', 'estac '],
        'Transporte Publico': [
            'metro', 'metrô', 'onibus', 'oônibus', 'bilhete', 'riocard', 'cartao bom', 'sptrans', 'trem', 'barcas',
        ],
    },
    'MORADIA': {
        'Aluguel': ['aluguel', 'locacao', 'imobiliaria', 'quinto andar', 'quintoandar', 'loft', 'zap imoveis'],
        'Condominio': ['condominio', 'taxa condominial', 'lume', 'boleto condominio', 'admin condominio'],
        'Energia': [
            'cemig', 'copel', 'light', 'enel', 'energisa', 'coelba', 'celesc',
            'elektro', 'cpfl', 'electropaulo', 'conta luz', 'aneel',
        ],
        'Agua': ['sabesp', 'cedae', 'copasa', 'embasa', 'saneago', 'caesb', 'corsan', 'cagece', 'conta agua'],
        'Gas': ['comgas', 'ceg', 'ultragaz', 'liquigas', 'fogas', 'supergasbras'],
    },
    'SAÚDE': {
        'Farmacia': [
            'farmacia', 'drogasil', 'drogaria', 'ultrafarma', 'panvel',
            'onofre', 'nissei', 'pacheco', 'venancio', 'raia', 'droga raia', 'drogarias', 'poupafarma',
        ],
        'Plano de Saude': [
            'plano saude', 'unimed', 'amil', 'bradesco saude', 'sulamerica saude',
            'hapvida', 'notredame', 'bradesco saude', 'saude bradesco', 'intermedica', 'porto saude',
        ],
        'Consultas': ['consulta medica', 'medico', 'clinica', 'hospital', 'pronto socorro', 'exame', 'laboratorio', 'odontologia', 'dentista', 'psicologo'],
    },
    'EDUCAÇÃO': {
        'Mensalidade': ['mensalidade', 'escola', 'faculdade', 'universidade', 'colegio', 'curso', 'udemy', 'alura', 'hotmart', 'coursera', 'edx', 'ingles', 'idiomas'],
        'Material': ['livraria', 'papelaria', 'saraiva', 'amazon livros', 'leitura', 'cultura', 'nobel'],
    },
    'VESTUÁRIO E BELEZA': {
        'Roupas e Calcados': [
            'zara', 'renner', 'cea', 'riachuelo', 'hering', 'marisa', 'calcados',
            'netshoes', 'centauro', 'lojas americanas', 'nike', 'adidas', 'arezzo', 'havainas', 'shoestock',
            'kanui', 'dafiti', 'hering', 'hope', 'intimissimi', 'puket', 'lojas americanas',
        ],
        'Beleza': ['salao', 'barbearia', 'estetica', 'manicure', 'spa', 'oboticario', 'natura', 'sephora', 'quem disse berenice', 'l occitane', 'ikesaki'],
    },
    'PET': {
        'Veterinario': ['veterinario', 'clinica veterinaria', 'petshop', 'pet shop', 'petz', 'cobasi', 'doghero', 'banho e tosa', 'petlove'],
    },
    'LAZER E ENTRETENIMENTO': {
        'Cinema/Teatro': ['cinema', 'teatro', 'show', 'ingresso', 'ticket', 'sympla', 'eventbrite', 'cinemark', 'kinoplex', 'uci', 'ingresso.com', 'bilheteria'],
        'Jogos': ['steam', 'psn', 'xbox', 'nintendo', 'nuuvem', 'playstation', 'razer', 'epic games', 'roblox', 'free fire', 'fortnite', 'league of legends'],
        'Viagem': [
            'hotel', 'pousada', 'airbnb', 'booking', 'decolar', 'latam', 'gol',
            'azul', 'ryanair', 'passagem', 'voegol', 'cvc', '123 milhas', 'hurb', 'trivago',
        ],
    },
    'FINANÇAS E INVESTIMENTOS': {
        'Salario': ['salario', 'pagamento folha', 'folha pagamento', 'vencimento', 'prolabore', 'holerite'],
        'Investimentos': [
            'cdb', 'lci', 'lca', 'tesouro', 'dividendo', 'rendimento', 'aporte', 'poupanca', 'resgate',
            'juros recebidos', 'fundo', 'xp investimentos', 'btg pactual', 'nu invest', 'avenue', 'inter dtvm',
        ],
        'Transferencia Recebida': ['transferencia recebida', 'pix recebido', 'ted recebido', 'ted recebida'],
    },
    'IMPOSTOS E TAXAS': {
        'Impostos': ['iptu', 'ipva', 'receita federal', 'sefaz', 'detran', 'multa', 'darf', 'irpf', 'das '],
    },
    'TRANSFERÊNCIAS': {
        'Enviada': ['pix enviado', 'ted enviado', 'doc enviado', 'transferencia enviada', 'ted enviada'],
        'Fatura': ['pagamento fatura', 'fatura cartao', 'pgto fatura', 'pagamento cartao', 'pagto fatura'],
    },
    'JUROS E ENCARGOS': {
        'Juros': ['juros', 'mora', 'encargo'],
        'IOF': ['iof'],
        'Anuidade': ['anuidade', 'taxa anuidade'],
        'Multas': ['multa', 'tarifa', 'cesta servicos'],
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
    'EMPRÉSTIMOS E FINANCIAMENTOS': 'Empréstimos e Financiamentos',
    'JUROS E ENCARGOS':          'JUROS E ENCARGOS',
}

# Fallbacks após regras — candidatos ao refinamento por LLM (híbrido)
NOME_CATEGORIA_OUTROS_DESPESA = "Outros"
NOME_CATEGORIA_OUTROS_RECEITA = "Receita / Outros"


# ---------------------------------------------------------------------------
# CAMADA 0 — CNAE (Classificação Nacional de Atividades Econômicas)
# ---------------------------------------------------------------------------
# Prioridade máxima: dados fiscais oficiais do estabelecimento.
MAPA_CNAE_CATEGORIA = {
    # ALIMENTAÇÃO
    "56": ("ALIMENTAÇÃO", "Restaurantes/Lanchonetes"),
    "47.1": ("ALIMENTAÇÃO", "Mercado/Supermercado"), 
    
    # TRANSPORTE
    "49": ("TRANSPORTE", "Transporte Publico"),
    "49.2": ("TRANSPORTE", "Aplicativos"),
    
    # SAÚDE
    "86": ("SAÚDE", "Consultas"),
    "47.7": ("SAÚDE", "Farmacia"),
    
    # EDUCAÇÃO
    "85": ("EDUCAÇÃO", "Mensalidade"),
    
    # SERVIÇOS E ASSINATURAS
    "64": ("SERVIÇOS E ASSINATURAS", "Financeiro"),
    "65": ("SERVIÇOS E ASSINATURAS", "Financeiro"),
    "61": ("SERVIÇOS E ASSINATURAS", "Assinaturas"),
    
    # LAZER E ENTRETENIMENTO
    "90": ("LAZER E ENTRETENIMENTO", "Cultura e Eventos"),
    "91": ("LAZER E ENTRETENIMENTO", "Cultura e Eventos"),
    "93": ("LAZER E ENTRETENIMENTO", "Esportes e Lazer"),
    
    # VESTUÁRIO E BELEZA
    "47.8": ("VESTUÁRIO E BELEZA", "Roupas e Calcados"),
    "96.0": ("VESTUÁRIO E BELEZA", "Beleza"),
    
    # MORADIA
    "41": ("MORADIA", "Aluguel"),
    "43": ("MORADIA", "Condominio"),
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

_TERMOS_TRANSFERENCIA_EXPLICTA = (
    "pix enviado", "ted enviado", "ted enviada", "doc enviado",
    "transferencia enviada", "transferência enviada",
    "transferencia recebida", "transferência recebida",
    "pagamento fatura", "fatura cartao", "fatura cartão",
)

_TERMOS_GENERICOS_TRANSFERENCIA = {
    "", "pix", "ted", "doc", "transferencia", "transferência", "pagamento",
    "pagamento pix", "mesma titularidade", "titularidade",
}

_INDICADORES_TRANSFERENCIA_REAL = {
    "nubank", "nu pagamentos", "inter", "itau", "itaú", "bradesco", "santander",
    "caixa", "bb", "banco do brasil", "mercado pago", "picpay", "pagbank",
    "c6", "next", "neon", "agencia", "agência", "conta", "poupanca", "poupança",
    "mesma titularidade", "cpf", "cnpj",
}


def _deve_classificar_como_transferencia(descricao_original: str, descricao_limpa: str) -> bool:
    desc_original_norm = remove_accents(descricao_original)
    desc_limpa_norm = remove_accents(descricao_limpa)

    if not any(term in desc_original_norm for term in _TERMOS_TRANSFERENCIA_EXPLICTA):
        return False

    if desc_limpa_norm in _TERMOS_GENERICOS_TRANSFERENCIA:
        return True

    if any(indicador in desc_limpa_norm for indicador in _INDICADORES_TRANSFERENCIA_REAL):
        return True

    if re.search(r"\b\d{11,14}\b", re.sub(r"\D", "", descricao_limpa)):
        return True

    # Se a descrição limpa ainda preserva um merchant ou serviço identificável,
    # preferimos cair em "Outros" a rotular incorretamente como transferência.
    return False


# ---------------------------------------------------------------------------
# Classificação por regras (sem I/O) + persistência
# ---------------------------------------------------------------------------

def classificar_nomes_por_regras(
    descricao: str, 
    tipo_raw: str, 
    cnae_codigo: str | None = None
) -> tuple[str, str]:
    """
    Aplica regras de CNAE, mapa de palavras-chave e fallbacks Outros.
    Retorna (nome_categoria_interna, nome_subcategoria).
    """
    tipo = normalizar_tipo(tipo_raw)

    # 1. Prioridade Máxima: CNAE (se disponível e mapeado)
    if cnae_codigo:
        cnae_limpo = "".join(filter(str.isdigit, str(cnae_codigo)))
        if len(cnae_limpo) >= 2:
            # Tenta match por prefixos formatados (ex: 47.1 ou 47)
            formatted_prefixes = [f"{cnae_limpo[:2]}.{cnae_limpo[2]}", cnae_limpo[:2]]
            for p in formatted_prefixes:
                if p in MAPA_CNAE_CATEGORIA:
                    return MAPA_CNAE_CATEGORIA[p]

    desc_limpa = limpar_descricao(descricao)
    desc_norm = remove_accents(desc_limpa)

    cat_nome: str | None = None
    subcat_nome: str | None = None

    for c_nome, subcategorias in MAPA_CATEGORIAS.items():
        if c_nome == 'FINANÇAS E INVESTIMENTOS' and tipo != 'Receita':
            continue
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

    if not cat_nome and _deve_classificar_como_transferencia(descricao, desc_limpa):
        c_nome = 'TRANSFERÊNCIAS'
        desc_original_norm = remove_accents(descricao)
        subcategorias = MAPA_CATEGORIAS[c_nome]
        for s_nome, keywords in subcategorias.items():
            for kw in keywords:
                pattern = _PADROES_COMPILADOS[(c_nome, s_nome, kw)]
                if pattern.search(desc_original_norm):
                    cat_nome = c_nome
                    subcat_nome = s_nome
                    break
            if cat_nome:
                break

    if not cat_nome:
        if tipo == 'Receita':
            cat_nome = 'Receita / Outros'
            subcat_nome = 'Outras Receitas'
        else:
            cat_nome = 'Outros'
            subcat_nome = 'Geral'

    cat_nome_db = _MAPA_NOME_CATEGORIA.get(cat_nome, cat_nome)
    return cat_nome_db, subcat_nome


def persistir_ids_categoria(
    db: Session,
    cat_nome_db: str,
    subcat_nome: str,
    cat_cache: dict | None = None,
    subcat_cache: dict | None = None,
) -> tuple[int | None, int | None]:
    """Resolve ou cria Categoria/Subcategoria e retorna os IDs."""
    if cat_cache is not None and cat_nome_db in cat_cache:
        cat_id = cat_cache[cat_nome_db]
    else:
        # Busca case-insensitive para evitar duplicatas (ex: ALIMENTACAO vs Alimentação)
        categoria_db = db.query(Categoria).filter(func.lower(Categoria.nome) == func.lower(cat_nome_db)).first()
        if not categoria_db:
            categoria_db = Categoria(nome=cat_nome_db)
            db.add(categoria_db)
            db.flush()
        cat_id = categoria_db.id
        if cat_cache is not None:
            cat_cache[cat_nome_db] = cat_id

    sub_key = (cat_id, subcat_nome)
    if subcat_cache is not None and sub_key in subcat_cache:
        subcat_id = subcat_cache[sub_key]
    else:
        # Busca case-insensitive para subcategorias
        subcat_db = db.query(Subcategoria).filter(
            func.lower(Subcategoria.nome) == func.lower(subcat_nome),
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


def aplicar_regras_lancamentos_open_finance(
    db: Session,
    usuario_id: int,
    escopo: str = "sem_categoria",
) -> int:
    """
    Reaplica regras locais aos lançamentos Open Finance, sem chamar a API Pierre.

    escopo:
        - sem_categoria: apenas id_categoria IS NULL (pós-ingestão).
        - tudo: todos os lançamentos open_finance (para /recategorizar_tudo).
    """
    q = db.query(Lancamento).filter(
        Lancamento.id_usuario == usuario_id,
        Lancamento.origem == "open_finance",
    )
    if escopo == "sem_categoria":
        q = q.filter(Lancamento.id_categoria.is_(None))
    elif escopo != "tudo":
        raise ValueError(f"escopo inválido: {escopo}")

    lancamentos = q.all()
    cat_cache: dict = {}
    subcat_cache: dict = {}
    atualizados = 0

    for lanc in lancamentos:
        try:
            cat_nome_db, subcat_nome = classificar_nomes_por_regras(
                lanc.descricao or "", lanc.tipo, cnae_codigo=lanc.cnae
            )
            with db.begin_nested():
                cid, sid = persistir_ids_categoria(
                    db, cat_nome_db, subcat_nome, cat_cache, subcat_cache
                )
            if cid and (lanc.id_categoria != cid or lanc.id_subcategoria != sid):
                lanc.id_categoria = cid
                lanc.id_subcategoria = sid
                atualizados += 1
        except Exception as e:
            logger.warning("Falha ao aplicar regras ao lançamento %s: %s", lanc.id, e)

    if atualizados:
        db.commit()
    return atualizados


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
    cat_nome_db, subcat_nome = classificar_nomes_por_regras(descricao, tipo_raw)

    try:
        with db.begin_nested():
            return persistir_ids_categoria(
                db, cat_nome_db, subcat_nome, cat_cache, subcat_cache
            )
    except Exception as e:
        logger.error(f"Erro ao persistir categoria/subcategoria para '{descricao}': {e}")
        return None, None
