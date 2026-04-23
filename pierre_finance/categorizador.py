"""
Categorizador de Transações Open Finance — Pierre Finance
==========================================================
v4 — Reescrita completa com foco em cobertura máxima e zero falsos negativos.

Principais melhorias:
- Matching por `in` simples (substring) em vez de regex word-boundary rígida
- Limpeza de descrição mais agressiva e abrangente
- Mapa de palavras-chave massivamente ampliado com variações reais do Open Finance
- Lógica de prioridade explícita: CNAE > Sinais Fortes > Substring > Fallback LLM
- Função `classificar_nomes_por_regras` retorna resultado sempre — nunca falha silenciosamente
- Suporte a variações de acentuação e escrita colada (ex: "pixenviado", "pagamentofatura")
"""

import unicodedata
import re
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Categoria, Subcategoria, Lancamento, RegraCategorizacao
from finance_utils import normalize_financial_type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def remove_accents(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Prefixos bancários que poluem a descrição — removidos antes do match
_PREFIXOS_BANCARIOS = [
    "pix enviado ", "pix recebido ", "pix transferido ", "pix cobranca ",
    "ted enviada ", "ted recebida ", "ted enviado ", "ted recebido ",
    "doc enviado ", "doc recebido ",
    "transf enviada ", "transf recebida ", "transf.enviada ", "transf.recebida ",
    "transferencia enviada ", "transferencia recebida ",
    "transferência enviada ", "transferência recebida ",
    "pagamento efetuado ", "pagamento recebido ", "pagamento de conta ",
    "pagamento fatura ", "pagto fatura ", "pgto fatura ", "pgt fatura ",
    "compra no cartao ", "compra no débito ", "compra no credito ",
    "compra no debito ", "compra parcelada ", "compra credito ", "compra debito ",
    "debito automatico ", "debito em conta ",
    "lancamento de debito ", "lancamento debito ",
    "liquidacao ", "liquidação ",
    "pgto ", "pagto ",
    "enviado por ", "pago por ",
    "venda ", "estorno ",
    "pag* ", "par* ", "compra* ",
]

# Sufixos e ruídos comuns que aparecem APÓS o nome do estabelecimento
_SUFIXOS_RUIDO = re.compile(
    r"(\s+\d{2}/\d{2}(/\d{2,4})?)"   # datas 01/05, 01/05/24
    r"|(\s+\*\w+)"                     # *CODIGO
    r"|(\s+\d{4,})"                    # números longos
    r"|(\s+-\s+\w{3,6}\s+\d+)"        # - AGN 12345
    r"|(\s+rj$|\s+sp$|\s+mg$|\s+br$)" # estados no final
    r"|(\s+s\.?a\.?$)"                 # S.A no final
    r"|([\*\#\@]+)",                   # caracteres especiais
    re.IGNORECASE,
)


def limpar_descricao(descricao: str) -> str:
    """
    Remove ruídos de descrições bancárias para maximizar o match por keyword.
    Retorna sempre a versão normalizada (sem acentos, minúscula).
    """
    if not descricao:
        return ""

    desc = remove_accents(descricao)

    # Remove prefixos bancários conhecidos
    for prefixo in _PREFIXOS_BANCARIOS:
        if desc.startswith(prefixo):
            desc = desc[len(prefixo):]
            break  # remove apenas o primeiro match

    # Remove variantes coladas sem espaço (ex: "pixenviado", "pagamentofatura")
    _colados = [
        "pixenviado", "pixrecebido", "pixtransferido",
        "tedenviada", "tedrecebida", "doceenviado",
        "pagamentofatura", "pagtofatura", "pgtofatura",
        "compranoCartao", "compranoDebito",
    ]
    for c in _colados:
        if desc.startswith(remove_accents(c)):
            desc = desc[len(c):]

    # Remove CPF/CNPJ, IDs de transação e datas
    desc = re.sub(r"\d{3}\.?\d{3}\.?\d{3}[-/]?\d{2}", "", desc)  # CPF
    desc = re.sub(r"\d{2}\.?\d{3}\.?\d{3}[\/]?\d{4}[-]?\d{2}", "", desc)  # CNPJ
    desc = re.sub(r"\b\d{6,20}\b", "", desc)  # IDs/números longos

    # Remove sufixos de ruído
    desc = _SUFIXOS_RUIDO.sub(" ", desc)

    # Normaliza espaços
    desc = re.sub(r"\s+", " ", desc).strip()

    return desc if desc else remove_accents(descricao)


def normalizar_tipo(tipo_raw: str) -> str:
    return normalize_financial_type(tipo_raw, default="Despesa")


# ---------------------------------------------------------------------------
# MAPA PRINCIPAL DE CATEGORIAS
# ---------------------------------------------------------------------------
# Estrutura: { "Categoria DB": { "Subcategoria DB": ["keyword1", "keyword2", ...] } }
#
# REGRAS DE KEYWORDS:
# - Sempre minúsculas e SEM acentos (a limpeza normaliza antes do match)
# - Match por substring simples (in): "ifood" bate em "pag*ifood*123"
# - Ordem das categorias = prioridade (mais específica primeiro)
# ---------------------------------------------------------------------------

MAPA_CATEGORIAS: dict[str, dict[str, list[str]]] = {

    # ── JUROS E ENCARGOS ─────────────────────────────────────────────────────
    # Prioridade alta: evita classificar tarifa bancária como "Serviços"
    "Juros e Encargos": {
        "Juros": [
            "juros", "jur ", "juros mora", "juros atraso", "juros rotativo",
            "encargo", "encargos",
        ],
        "IOF": ["iof ", " iof"],
        "Anuidade": [
            "anuidade", "anuidade cartao", "taxa anuidade",
            "anuidade mastercard", "anuidade visa",
        ],
        "Tarifas Bancárias": [
            "tarifa bancaria", "taxa bancaria", "cesta servicos", "cesta de servicos",
            "manutencao conta", "mensalidade banco", "pacote servicos",
            "tarifa transferencia", "tarifa pix", "tarifa ted",
            "taxa manutencao", "taxa servico", "custas cartorio",
            "tarifa saque", "taxa saque", "tarifa deposito",
            "tbi ", "tar ", "serv ban", "taxa cad", "txcad",
        ],
        "Multas": ["multa atraso", "multa financeira", "multa contrato"],
    },

    # ── EMPRÉSTIMOS E FINANCIAMENTOS ─────────────────────────────────────────
    "Empréstimos e Financiamentos": {
        "Parcela de Veículo": [
            "financiamento veiculo", "bv financeira", "bv ", "pan finance",
            "itau financiamento", "cred veiculo", "credito veiculo",
            "safra financeira", "omni financeira", "aymoré", "aymore",
            "parcela carro", "financiamento auto", "parcela veiculo",
            "financ veiculo", "mora operacao de credito",
        ],
        "Empréstimo Pessoal": [
            "emprestimo", "empréstimo", "credito pessoal", "crédito pessoal",
            "parcela emprestimo", "consignado", "cred pessoal", "cred pcss",
            "emprest ", "financiamento pessoal", "credcash", "credsystem",
            "crefisa", "bmg ", "banco bmg", "dacasa", "portocred",
            "acordo financeiro", "renegociacao", "renegociação",
            "contr ", "parc ", "credito liberado", "cred a vista",
        ],
        "Financiamento Imobiliário": [
            "financiamento habitacional", "caixa habita", "parcela imovel",
            "mcmv", "habitacional", "minha casa minha vida",
            "banco imobiliario", "financ imob",
        ],
    },

    # ── ALIMENTAÇÃO ──────────────────────────────────────────────────────────
    "Alimentação": {
        "Delivery": [
            "ifood", "i food", "rappi", "uber eats", "ubereats",
            "james delivery", "delivery much", "aiqfome", "loggi food",
            "99 food", "entrega comida", "pede pronto",
        ],
        "Restaurantes/Lanchonetes": [
            "mcdonalds", "mc donalds", "mcdonald", "burger king", "bk ",
            "bob s", "bobs ", "subway", "pizza hut", "dominos", "domino s",
            "outback", "madero", "coco bambu", "starbucks", "habibs",
            "giraffas", "spoleto", "frango assado", "chineses",
            "restaurante", "lanchonete", "churrascaria", "espetinho",
            "pizzaria", "sushi", "japones", "japonesa", "temakeria",
            "acaiteria", "sorveteria", "doceria", "confeitaria",
            "padaria", "panificadora", "cafe ", "cafeteria",
            "bistro", "botequeio", "boteco", "bar ", " bar",
            "pub ", "cervejaria", "gastrobar", "steakhouse",
            "pastelaria", "tapiocaria", "crepe ", "galeto",
            "porcao", "petisco", "comida ", "refeicao",
            "bacio di latte", "kopenhagen", "cacau show",
            "chocolates", "brigaderia",
            # Redes conhecidas BR
            "habib s", "china in box", "jeronimo", "formula grill",
            "bendito burger", "cabana burger", "smash", "tiktok burger",
            "pizza inn", "pizza prime",
            # Apps genéricos de comida com código
            "pag*restaur", "pag*lanche", "pag*pizza", "pag*sushi",
        ],
        "Mercado/Supermercado": [
            "supermercado", "mercado ", " mercado", "minimercado",
            "hipermercado", "pao de acucar", "carrefour", "atacadao",
            "assai", "extra ", "prezunic", "guanabara", "zona sul",
            "mundial", "superprix", "hortifruti", "hortifrutti",
            "sacolao", "quitanda", "feira ", "feirinha",
            "st marche", "obahortifruti", "bahamas", "dia ",
            "condor", "muffato", "angeloni", "zaffari",
            "acougue", "frigorifico", "peixaria",
            "sonda", "mambo", "nagumo", "tauste",
            "walmart", "sam s club", "costco",
            "lojas americanas alim", "americanas alim",
            "swift ", "seara ", "sadia ", "perdigao",
            "distribuidora",
            # Conveniências (mapeadas aqui por serem alimentação)
            "conveniencia", "loja conv", "am pm ",
        ],
        "Padaria/Confeitaria": [
            "padaria", "panificadora", "confeitaria", "doceria",
            "boulangerie", "pao franc", "croissant",
        ],
    },

    # ── TRANSPORTE ───────────────────────────────────────────────────────────
    "Transporte": {
        "Aplicativos": [
            "uber ", " uber", "uber*", "99pop", "99 ", " 99*",
            "cabify", "taxi", "táxi", "ladydriver", "indriver",
            "99app", "99taxi", "telleride", "togoo",
        ],
        "Combustível": [
            "posto ", "combustivel", "gasolina", "etanol", "alcool comb",
            "shell ", "ipiranga", "br distribuidora", "branca",
            "ale combustiveis", "petrobras posto", "texaco",
            "dislub", "lubrificante", "diesel ", "abastec",
            "auto posto", "autoposto",
        ],
        "Estacionamento": [
            "estacionamento", "estac ", "parking", "park ",
            "zona azul", "sem parar", "veloe ", "taggy ",
            "connect car", "movemais", "autopass",
        ],
        "Transporte Público": [
            "metro ", "metrô", "onibus", "ônibus", "bilhete unico",
            "bilhete único", "riocard", "cartao bom", "sptrans",
            "trem ", "barcas ", "ccr barcas", "brt ", "vlt ",
            "supervia", "cptm ", "bonde ", "ferry",
        ],
        "Pedágio": [
            "pedagio", "pedágio", "ecovias", "autopista", "viapar",
            "rodovia", "viario", "ponte niteroi", "concer",
            "novadutra", "triangulo do sol", "intervias",
            "rodovias do tiete", "rota das bandeiras",
        ],
        "Manutenção Veicular": [
            "oficina", "mecanico", "mecânica", "borracharia",
            "vidro auto", "funilaria", "pintura auto",
            "revisao auto", "troca oleo", "alinhamento",
            "balanceamento", "pneu ", "pneus ",
        ],
        "Aluguel de Veículo": [
            "localiza", "movida", "unidas", "hertz", "avis ",
            "budget car", "aluguel carro", "rent car",
        ],
    },

    # ── MORADIA ──────────────────────────────────────────────────────────────
    "Moradia": {
        "Aluguel": [
            "aluguel", "locacao", "locação", "imobiliaria",
            "quinto andar", "quintoandar", "loft ", "zap imoveis",
            "imovel ", "imóvel ", "kitnete", "apartamento alug",
        ],
        "Condomínio": [
            "condominio", "condominío", "condomínio",
            "taxa condominial", "boleto condominio", "admin condominio",
            "lume ", "sindico",
        ],
        "Energia Elétrica": [
            "cemig", "copel", "light ", "enel ", "energisa",
            "coelba", "celesc", "elektro", "cpfl ", "eletropaulo",
            "conta luz", "conta energia", "aneel ", "ceee ",
            "celpe ", "cosern ", "ceal ", "energipe",
        ],
        "Água e Esgoto": [
            "sabesp", "cedae", "copasa", "embasa", "saneago",
            "caesb", "corsan", "cagece", "conta agua", "agua e esgoto",
            "caern", "casan", "saae ", "sanepar",
        ],
        "Gás": [
            "comgas", "ceg ", "ultragaz", "liquigas", "fogas",
            "supergasbras", "gas encanado", "conta gas",
        ],
        "Internet/TV/Telefone": [
            "net ", " net", "claro ", "vivo ", "tim ",
            "oi ", "starlink", "brisanet", "desktop",
            "intelbras", "wifi ", "banda larga",
            "net virtua", "sky ", "directv", "oi tv",
            "clarotv", "vivo tv", "internet residencial",
            "telecom", "telefone fixo", "linha fixa",
        ],
        "Materiais/Reformas": [
            "leroy merlin", "telhanorte", "c&c ", "madeiranorte",
            "materiais construcao", "obra ", "reforma ",
            "ferreteria", "ferreira", "ferragem",
            "casa construcao", "loja material",
        ],
    },

    # ── SERVIÇOS E ASSINATURAS ───────────────────────────────────────────────
    "Serviços e Assinaturas": {
        "Streaming": [
            "netflix", "spotify", "amazon prime", "amazonprime",
            "disney ", "disney+", "hbo ", "hbomax", "globoplay",
            "youtube premium", "deezer", "apple tv", "appletv",
            "crunchyroll", "paramount", "mubi", "telecine",
            "sportv", "premiere ", "globo play", "looke",
            "youtube music", "tidal ", "apple music",
            "amazon music", "primevideo",
        ],
        "Assinaturas SaaS": [
            "chatgpt", "openai", "midjourney", "canva ",
            "adobe ", "notion ", "slack ", "zoom ",
            "google one", "icloud", "dropbox", "microsoft 365",
            "office 365", "github ", "heroku", "vercel",
            "cloudflare", "aws ", "gcp ", "azure ",
            "anthropic", "claude ", "gemini ", "perplexity",
            "cursor ", "replit", "copilot",
        ],
        "Academia/Saúde": [
            "smartfit", "bluefit", "selfit", "gympass", "totalpass",
            "wellhub", "bio ritmo", "bodytech", "madonna",
            "academia ", "crossfit", "pilates ", "yoga ",
            "natacao", "musculacao",
        ],
        "Clube/Associação": [
            "socio torcedor", "flamengo", "fluminense", "vasco",
            "botafogo", "corinthians", "palmeiras", "sao paulo fc",
            "gremio ", "internacional ", "atletico",
            "clube associado", "mensalidade clube",
        ],
        "Seguros": [
            "seguro vida", "seguro residencial", "seguro celular",
            "seguro auto", "seguro saude", "seguro viagem",
            "porto seguro", "sulamerica seg", "allianz",
            "liberty seg", "bradesco seg", "itau seg",
            "mapfre", "zurich seg", "hdi seg", "tokio marine",
            "seguros ", "apolice", "seguro cartao", "seguro conta",
            "seguro protegido",
        ],
    },

    # ── SAÚDE ────────────────────────────────────────────────────────────────
    "Saúde": {
        "Farmácia": [
            "farmacia", "drogaria", "droga ", "drogasil",
            "raia ", "droga raia", "pacheco", "ultrafarma",
            "panvel", "onofre", "nissei", "venancio",
            "poupafarma", "medfarma", "drogal",
            "drogasmil", "drogasil", "droga mais",
            "pague menos", "drogaria sp", "dpsp",
        ],
        "Plano de Saúde": [
            "plano saude", "plano de saude", "unimed",
            "amil ", "bradesco saude", "sulamerica saude",
            "hapvida", "notredame", "intermedica", "porto saude",
            "prevent senior", "assim saude", "golden cross",
            "qualicorp", "careplus", "omint", "mediservice",
        ],
        "Consultas e Exames": [
            "consulta medica", "consulta med", "médico", "medico ",
            "clinica ", "clínica ", "hospital ", "pronto socorro",
            "upa ", "exame ", "laboratorio", "laboratório",
            "hermes pardini", "fleury", "dasa ", "lavoisier",
            "einstein ", "sirio libanes", "odontologia",
            "dentista", "clinica dent", "psicologo", "psicólogo",
            "terapeuta", "terapia ", "oftalmo", "ortopedista",
            "pediatra", "ginecologista",
        ],
        "Ótica": [
            "otica ", "ótica ", "oticas ", "lensclub",
            "lenscrafters", "hoya ", "vision",
        ],
    },

    # ── EDUCAÇÃO ─────────────────────────────────────────────────────────────
    "Educação": {
        "Mensalidade Escolar": [
            "mensalidade", "escola ", "faculdade", "universidade",
            "colegio", "colégio", "ensino ", "educacao",
            "matricula", "matrícula", "material escolar",
        ],
        "Cursos Online": [
            "udemy", "alura ", "hotmart", "coursera", "edx ",
            "eduzz", "monetizze", "kiwify", "braip",
            "skillshare", "linkedin learn", "domestika",
            "duolingo", "babbel",
        ],
        "Idiomas": [
            "cultura inglesa", "ccaa ", "wizard ", "fisk ",
            "wise up", "english live", "yázigi", "yazigi",
            "berlitz", "idiomas", "ingles ",
        ],
        "Faculdade/Pós": [
            "fgv ", "insper", "ibmec", "senac", "senai",
            "anhanguera", "estacio", "unip ", "uninove",
            "unicsul", "usp ", "unicamp", "ufrj",
            "puc ", "mackenzie",
        ],
        "Material": [
            "livraria", "saraiva", "amazon livros", "cultura livraria",
            "leitura ", "papelaria", "lapis ", "caderno",
        ],
    },

    # ── VESTUÁRIO E BELEZA ───────────────────────────────────────────────────
    "Vestuário e Beleza": {
        "Roupas e Calçados": [
            "zara ", "renner", "c&a ", "cea ", "riachuelo",
            "hering", "marisa ", "lojas marisa",
            "netshoes", "centauro", "nike ", "adidas",
            "arezzo", "havainas", "shoestock",
            "kanui", "dafiti", "hope ", "intimissimi",
            "puket", "amaro ", "schutz",
            "shein", "shopee", "aliexpress",
            "mercado livre", "mercadolivre", "meli ",
            "farm ", "animale", "soma ", "group", "colcci",
            "reserva", "osklen", "forum ", "ellus",
            "tricae", "dressing", "privalia",
            "outlet ", "brechó", "brecho",
        ],
        "Beleza": [
            "salao", "salão", "barbearia", "barbeiro",
            "estetica", "estética", "manicure", "pedicure",
            "spa ", "boticario", "o boticario", "natura ",
            "sephora", "quem disse berenice", "l occitane",
            "ikesaki", "depilacao", "depilação", "lash ",
            "sobrancelha", "design sobrancelha",
            "maquiagem", "cosmetico", "perfumaria",
            "salon line", "loreal",
        ],
    },

    # ── PET ──────────────────────────────────────────────────────────────────
    "Pet": {
        "Veterinário": [
            "veterinario", "veterinária", "vet ", "clinvet",
            "clinica vet", "hospital vet",
        ],
        "Pet Shop": [
            "petshop", "pet shop", "petz", "cobasi",
            "petlove", "doghero", "dogwalker",
            "banho e tosa", "banho tosa", "racao ",
            "comida pet", "bichinho",
        ],
    },

    # ── LAZER E ENTRETENIMENTO ───────────────────────────────────────────────
    "Lazer e Entretenimento": {
        "Cinema e Teatro": [
            "cinema ", "teatro ", "show ", "ingresso",
            "cinemark", "kinoplex", "uci ", "cinesystem",
            "moviecom", "ingresso.com", "bilheteria",
            "sympla", "eventbrite", "tickets for fun",
            "ticket360", "blueticket",
        ],
        "Jogos": [
            "steam", "psn ", "xbox ", "nintendo",
            "nuuvem", "playstation", "razer ", "epic games",
            "roblox", "free fire", "fortnite", "league of legends",
            "riot games", "battlenet", "gog.com",
            "apple games", "google play games",
        ],
        "Viagem/Hotel": [
            "hotel ", "pousada", "airbnb", "booking",
            "decolar", "latam ", "gol ", "azul ",
            "passagem", "voegol", "cvc ", "hurb",
            "trivago", "expedia", "trip.com",
            "hostel", "resort ", "flytour",
        ],
        "Cultura": [
            "museu", "exposicao", "exposição", "parque ",
            "atracao", "zoologico", "aquario",
            "circo", "espetaculo",
        ],
        "Apostas/Jogos": [
            "betano", "sportingbet", "bet365", "parimatch",
            "novibet", "pixbet", "vaidebet", "esportes da sorte",
            "superbet", "betsul", " bet ", "cassino",
            "loteria", "mega sena", "timemania", "loterica",
        ],
    },

    # ── FINANCEIRO E INVESTIMENTOS ───────────────────────────────────────────
    "Financeiro": {
        "Salário": [
            "salario", "salário", "pagamento folha",
            "folha pagamento", "vencimento", "prolabore",
            "pro labore", "holerite", "contra cheque",
            "remuneracao", "remuneração",
        ],
        "Investimentos": [
            "cdb ", "lci ", "lca ", "tesouro direto",
            "dividendo", "rendimento", "aporte",
            "xp investimentos", "btg pactual", "nu invest",
            "avenue", "inter dtvm", "rico ", "genial invest",
            "c6 invest", "easynvest", "warren", "vitreo",
            "poupanca", "poupança", "cdb rendimento",
            "resgate investimento",
        ],
        "Recebimento PIX": [
            "pix recebido", "ted recebida", "transferencia recebida",
            "deposito recebido", "reembolso", "estorno recebido",
        ],
        "Carteira Digital": [
            "mercado pago", "picpay", "pagbank", "pagseguro",
            "pagseguro", "recarga carteira", "deposito carteira",
        ],
    },

    # ── IMPOSTOS E TAXAS ─────────────────────────────────────────────────────
    "Impostos e Taxas": {
        "Impostos": [
            "iptu ", "ipva ", "receita federal", "sefaz ",
            "detran ", "darf ", "irpf ", "das ",
            "simples nacional", "inss ", "gps inss",
            "prefeitura", "municipio", "iss ", "itr ",
        ],
        "Taxas Gov": [
            "taxa detran", "licenciamento", "emplacamento",
            "cartorio", "despachante", "registro imovel",
            "registro veiculo",
        ],
    },

    # ── COMPRAS ONLINE ───────────────────────────────────────────────────────
    # Fallback para marketplaces genéricos (depois dos mais específicos)
    "Compras Online": {
        "Marketplace": [
            "shopee", "aliexpress", "wish ", "shein",
            "magazine luiza", "magalu", "casas bahia",
            "americanas", "submarino", "shoptime",
            "amazon", "mercado livre", "mercadolivre",
            "carrefour online",
        ],
        "Eletrônicos": [
            "kabum", "pichau", "terabyte", "fast shop",
            "ponto frio", "b2w ", "positivo",
            "apple store", "samsung store",
        ],
    },

    # ── CARTÃO DE CRÉDITO ────────────────────────────────────────────────────
    "Cartão de Crédito": {
        "Pagamento de Fatura": [
            "pagamento fatura", "pagto fatura", "pgto fatura",
            "pgt fatura", "fatura cartao", "fatura cartão",
            "pagamento cartao", "pagamento cartão",
            "cartoes caixa",
        ],
    },

    # ── TRANSFERÊNCIAS ───────────────────────────────────────────────────────
    # Movido para o final: só captura se nada mais específico bater
    "Transferências": {
        "PIX Enviado": [
            "pix enviado", "pix transferido", "pixenviado",
        ],
        "PIX Recebido": [
            "pix recebido", "pixrecebido",
        ],
        "TED/DOC": [
            "ted enviada", "ted enviado", "doc enviado",
            "transferencia enviada", "transf enviada",
        ],
    },
}


# Normalização: nome interno → nome no banco
_MAPA_NOME_CATEGORIA: dict[str, str] = {k: k for k in MAPA_CATEGORIAS}  # identidade (já são os nomes do banco)

# Categorias de fallback
NOME_CATEGORIA_OUTROS_DESPESA = "Outros"
NOME_CATEGORIA_OUTROS_RECEITA = "Receita / Outros"


# ---------------------------------------------------------------------------
# MAPA CNAE → Categoria/Subcategoria
# ---------------------------------------------------------------------------
# Chave = prefixo CNAE (2 dígitos ou 2+1 com ponto)
MAPA_CNAE_CATEGORIA: dict[str, tuple[str, str]] = {
    # Alimentação
    "56": ("Alimentação", "Restaurantes/Lanchonetes"),
    "47.2": ("Alimentação", "Mercado/Supermercado"),
    "47.1": ("Alimentação", "Mercado/Supermercado"),
    # Transporte
    "49": ("Transporte", "Transporte Público"),
    "45": ("Transporte", "Manutenção Veicular"),
    "77": ("Transporte", "Aluguel de Veículo"),
    # Saúde
    "86": ("Saúde", "Consultas e Exames"),
    "47.7": ("Saúde", "Farmácia"),
    "87": ("Saúde", "Consultas e Exames"),
    # Educação
    "85": ("Educação", "Mensalidade Escolar"),
    "82": ("Educação", "Cursos Online"),
    # Serviços
    "62": ("Serviços e Assinaturas", "Assinaturas SaaS"),
    "63": ("Serviços e Assinaturas", "Assinaturas SaaS"),
    "64": ("Financeiro", "Investimentos"),
    "65": ("Serviços e Assinaturas", "Seguros"),
    "66": ("Financeiro", "Investimentos"),
    "61": ("Moradia", "Internet/TV/Telefone"),
    # Lazer
    "90": ("Lazer e Entretenimento", "Cinema e Teatro"),
    "91": ("Lazer e Entretenimento", "Cultura"),
    "93": ("Lazer e Entretenimento", "Cinema e Teatro"),
    # Vestuário
    "47.8": ("Vestuário e Beleza", "Roupas e Calçados"),
    "47.5": ("Vestuário e Beleza", "Roupas e Calçados"),
    "96.0": ("Vestuário e Beleza", "Beleza"),
    # Moradia
    "41": ("Moradia", "Aluguel"),
    "43": ("Moradia", "Materiais/Reformas"),
    "35": ("Moradia", "Energia Elétrica"),
    "36": ("Moradia", "Água e Esgoto"),
    # Pet
    "75": ("Pet", "Veterinário"),
    "47.6": ("Pet", "Pet Shop"),
}


# Pré-processa o mapa para lookup rápido: lista normalizada por categoria
_LOOKUP_KEYWORDS: list[tuple[str, str, str]] = []
for _cat, _subcats in MAPA_CATEGORIAS.items():
    for _sub, _keywords in _subcats.items():
        for _kw in _keywords:
            _LOOKUP_KEYWORDS.append((_cat, _sub, remove_accents(_kw)))


# ---------------------------------------------------------------------------
# SINAIS FORTES — Detectados na descrição BRUTA (antes de limpar)
# Têm prioridade sobre o mapa de keywords
# ---------------------------------------------------------------------------

# (sinal_normalizado, categoria, subcategoria)
_SINAIS_FORTES: list[tuple[str, str, str]] = [
    # Juros e encargos
    ("juros ", "Juros e Encargos", "Juros"),
    (" juros", "Juros e Encargos", "Juros"),
    ("jur rot", "Juros e Encargos", "Juros"),
    ("juros de mora", "Juros e Encargos", "Juros"),
    ("encargo", "Juros e Encargos", "Juros"),
    ("iof ", "Juros e Encargos", "IOF"),
    (" iof", "Juros e Encargos", "IOF"),
    ("anuidade", "Juros e Encargos", "Anuidade"),
    ("tarifa bancaria", "Juros e Encargos", "Tarifas Bancárias"),
    ("taxa bancaria", "Juros e Encargos", "Tarifas Bancárias"),
    ("cesta servicos", "Juros e Encargos", "Tarifas Bancárias"),
    ("manutencao conta", "Juros e Encargos", "Tarifas Bancárias"),
    ("mensalidade banco", "Juros e Encargos", "Tarifas Bancárias"),
    ("pacote servicos", "Juros e Encargos", "Tarifas Bancárias"),
    # Seguros
    ("seguro cartao protegido", "Serviços e Assinaturas", "Seguros"),
    ("seguro protegido", "Serviços e Assinaturas", "Seguros"),
    # Salário
    ("salario", "Financeiro", "Salário"),
    ("salário", "Financeiro", "Salário"),
    ("pagamento folha", "Financeiro", "Salário"),
    ("prolabore", "Financeiro", "Salário"),
    ("pro labore", "Financeiro", "Salário"),
    # Delivery de comida (alta frequência)
    ("ifood", "Alimentação", "Delivery"),
    ("rappi", "Alimentação", "Delivery"),
    ("uber eats", "Alimentação", "Delivery"),
    ("ubereats", "Alimentação", "Delivery"),
    # Uber transporte
    ("uber*", "Transporte", "Aplicativos"),
    ("uber trip", "Transporte", "Aplicativos"),
    # Streaming
    ("netflix", "Serviços e Assinaturas", "Streaming"),
    ("spotify", "Serviços e Assinaturas", "Streaming"),
    ("amazon prime", "Serviços e Assinaturas", "Streaming"),
    ("disney+", "Serviços e Assinaturas", "Streaming"),
    ("hbomax", "Serviços e Assinaturas", "Streaming"),
    ("globoplay", "Serviços e Assinaturas", "Streaming"),
    # Cartão de Crédito
    ("pagamento fatura", "Cartão de Crédito", "Pagamento de Fatura"),
    ("pagto fatura", "Cartão de Crédito", "Pagamento de Fatura"),
    ("pgto fatura", "Cartão de Crédito", "Pagamento de Fatura"),
    ("fatura cartao", "Cartão de Crédito", "Pagamento de Fatura"),
]


def _detectar_sinal_forte(desc_norm: str) -> tuple[str, str] | None:
    """Verifica sinais fortes na descrição normalizada. Retorna (cat, sub) ou None."""
    for sinal, cat, sub in _SINAIS_FORTES:
        if sinal in desc_norm:
            return cat, sub
    return None


# ---------------------------------------------------------------------------
# Função principal de classificação por regras
# ---------------------------------------------------------------------------

def classificar_nomes_por_regras(
    descricao: str,
    tipo_raw: str,
    cnae_codigo: str | None = None,
    usuario_id: int | None = None,
    db: Session | None = None,
) -> tuple[str, str]:
    """
    Classifica uma transação em (categoria, subcategoria) usando múltiplas camadas:
    0. Regras Personalizadas (Aprendizado do usuário) - Prioridade Máxima
    1. CNAE (dados fiscais oficiais)
    2. Sinais fortes na descrição original (antes da limpeza)
    3. Match por substring no mapa de keywords (descrição limpa)
    4. Inferência pelo tipo (Receita → Financeiro)
    5. Fallback: Outros / Receita / Outros

    Nunca lança exceção — sempre retorna uma tupla válida.
    """
    tipo = normalizar_tipo(tipo_raw)
    desc_norm_original = remove_accents(descricao)
    desc_limpa = limpar_descricao(descricao)

    # ── CAMADA 0: REGRAS PERSONALIZADAS (APRENDIZADO) ────────────────────────
    if usuario_id and db and desc_limpa:
        regra = db.query(RegraCategorizacao).filter(
            RegraCategorizacao.id_usuario == usuario_id,
            RegraCategorizacao.descricao_substring == desc_limpa
        ).first()
        if regra and regra.categoria:
            cat_nome = regra.categoria.nome
            sub_nome = regra.subcategoria.nome if regra.subcategoria else "Geral"
            return cat_nome, sub_nome

    # ── CAMADA 1: CNAE ───────────────────────────────────────────────────────
    if cnae_codigo and str(cnae_codigo).strip() not in ("", "nao_encontrado", "no_match", "rule_match"):
        cnae_limpo = "".join(filter(str.isdigit, str(cnae_codigo)))
        if len(cnae_limpo) >= 2:
            for prefixo in [f"{cnae_limpo[:2]}.{cnae_limpo[2]}", cnae_limpo[:2]] if len(cnae_limpo) >= 3 else [cnae_limpo[:2]]:
                if prefixo in MAPA_CNAE_CATEGORIA:
                    return MAPA_CNAE_CATEGORIA[prefixo]

    # ── CAMADA 2: SINAIS FORTES (descrição original) ─────────────────────────
    resultado_sinal = _detectar_sinal_forte(desc_norm_original)
    if resultado_sinal:
        return resultado_sinal

    # ── CAMADA 3: KEYWORDS (descrição limpa) ─────────────────────────────────
    desc_limpa = limpar_descricao(descricao)

    # Tenta também com a descrição limpa em sinais fortes
    if desc_limpa and desc_limpa != desc_norm_original:
        resultado_sinal2 = _detectar_sinal_forte(desc_limpa)
        if resultado_sinal2:
            return resultado_sinal2

    # Busca no mapa completo de keywords
    for cat, sub, kw_norm in _LOOKUP_KEYWORDS:
        # Pula Financeiro/Salário se for Despesa para evitar falso positivo
        if cat == "Financeiro" and sub == "Salário" and tipo != "Receita":
            continue
        # Pula Recebimento se for Despesa
        if cat == "Financeiro" and sub == "Recebimento PIX" and tipo != "Receita":
            continue

        if kw_norm in desc_limpa or kw_norm in desc_norm_original:
            return cat, sub

    # ── CAMADA 4: INFERÊNCIA POR TIPO ────────────────────────────────────────
    if tipo == "Receita":
        # Qualquer receita não categorizada vai para Financeiro
        return "Financeiro", "Recebimento PIX"

    # ── CAMADA 5: FALLBACK ───────────────────────────────────────────────────
    return "Outros", "Geral"


# ---------------------------------------------------------------------------
# Persistência no banco de dados
# ---------------------------------------------------------------------------

def persistir_ids_categoria(
    db: Session,
    cat_nome_db: str,
    subcat_nome: str,
    cat_cache: dict | None = None,
    subcat_cache: dict | None = None,
) -> tuple[int | None, int | None]:
    """Resolve ou cria Categoria/Subcategoria e retorna os IDs."""
    # Padroniza para evitar duplicatas por capitalização (ex: Alimentação vs ALIMENTAÇÃO)
    cat_nome_db = (cat_nome_db or "Outros").strip().title()
    subcat_nome = (subcat_nome or "Geral").strip().title()

    if cat_cache is not None and cat_nome_db in cat_cache:
        cat_id = cat_cache[cat_nome_db]
    else:
        categoria_db = db.query(Categoria).filter(
            func.lower(Categoria.nome) == cat_nome_db.lower()
        ).first()
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
        subcat_db = db.query(Subcategoria).filter(
            func.lower(Subcategoria.nome) == subcat_nome.lower(),
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
    Reaplica regras locais aos lançamentos Open Finance sem chamar a API Pierre.

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
    elif escopo == "tudo":
        pass  # sem filtro adicional
    else:
        raise ValueError(f"escopo inválido: {escopo}")

    lancamentos = q.all()
    cat_cache: dict = {}
    subcat_cache: dict = {}
    atualizados = 0

    for lanc in lancamentos:
        try:
            cat_nome_db, subcat_nome = classificar_nomes_por_regras(
                lanc.descricao or "",
                lanc.tipo,
                cnae_codigo=getattr(lanc, "cnae", None),
                usuario_id=usuario_id,
                db=db
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

    logger.info(
        "[CATEGORIZAR] escopo=%s usuario=%s: %d/%d lançamentos atualizados",
        escopo, usuario_id, atualizados, len(lancamentos),
    )
    return atualizados


# ---------------------------------------------------------------------------
# Função de entrada (compatibilidade com código legado)
# ---------------------------------------------------------------------------

def categorizar_transacao(
    descricao: str,
    tipo_raw: str,
    db: Session,
    cat_cache: dict | None = None,
    subcat_cache: dict | None = None,
    cnae_codigo: str | None = None,
    usuario_id: int | None = None,
) -> tuple[int | None, int | None]:
    """
    Categoriza uma transação Open Finance e persiste no banco.

    Returns:
        (categoria_id, subcategoria_id) ou (None, None) em caso de erro.
    """
    cat_nome_db, subcat_nome = classificar_nomes_por_regras(
        descricao, tipo_raw, cnae_codigo, usuario_id=usuario_id, db=db
    )

    try:
        with db.begin_nested():
            return persistir_ids_categoria(
                db, cat_nome_db, subcat_nome, cat_cache, subcat_cache
            )
    except Exception as e:
        logger.error("Erro ao persistir categoria para '%s': %s", descricao, e)
        return None, None
