import logging
import httpx
import asyncio
from sqlalchemy.orm import Session
from models import Lancamento, Categoria, Subcategoria
from .categorizador import MAPA_CNAE_CATEGORIA

logger = logging.getLogger(__name__)

async def buscar_dados_cnpj(cnpj: str):
    """Consulta a BrasilAPI para obter dados do CNPJ."""
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {"error": "not_found"}
            return None
        except Exception as e:
            logger.error(f"Erro ao consultar CNPJ {cnpj}: {e}")
            return None

def obter_categoria_por_cnae(cnae_codigo: str) -> tuple[str, str] | None:
    """Retorna (categoria, subcategoria) com base no código CNAE."""
    if not cnae_codigo:
        return None
        
    cnae_limpo = "".join(filter(str.isdigit, str(cnae_codigo)))
    if len(cnae_limpo) < 2:
        return None
    
    # Tenta match por prefixos formatados (2.1 ou 2)
    formatted_prefixes = [f"{cnae_limpo[:2]}.{cnae_limpo[2]}", cnae_limpo[:2]]
    
    for p in formatted_prefixes:
        if p in MAPA_CNAE_CATEGORIA:
            return MAPA_CNAE_CATEGORIA[p]
            
    return None

def categorizar_por_nome(nome: str, descricao: str = "") -> tuple[str, str] | None:
    """Fallback: Tenta categorizar pelo nome da contraparte ou descrição usando palavras-chave."""
    nome_norm = (nome or "").lower()
    desc_norm = (descricao or "").lower()
    
    # Texto combinado para busca
    full_text = f"{nome_norm} {desc_norm}"
    
    # Regras de fallback por nome de empresa (Ordem de prioridade)
    regras = [
        # JUROS E ENCARGOS (Prioridade Máxima conforme pedido)
        (["juros", "mora", "multa", "encargo"], ("JUROS E ENCARGOS", "Juros")),
        (["iof"], ("JUROS E ENCARGOS", "IOF")),
        (["anuidade", "taxa anuidade"], ("JUROS E ENCARGOS", "Anuidade")),
        (["tarifa", "cesta servicos", "mensalidade banco"], ("JUROS E ENCARGOS", "Multas")), # Usando Multas como fallback para taxas
        
        # ASSINATURAS
        (["netflix", "spotify", "amazon prime", "disney", "hbo", "gympass", "wellhub", "icloud", "google one", "assinatura", "subscription", "plano mensal"], ("SERVIÇOS E ASSINATURAS", "Assinaturas")),
        
        # PARCELAMENTOS (Detecta via descrição se tiver 'parc' ou 'parcela')
        (["parc ", "parc.", "parcela"], ("EMPRÉSTIMOS E FINANCIAMENTOS", "Empréstimo Pessoal")),
        
        # ALIMENTAÇÃO
        (["alimentos", "bebidas", "distribuidora", "mercado", "supermercado", "formiguinha", "hortifruti", "sacolao", "sacolão", "pao de acucar", "pão de açúcar", "carrefour", "extra"], ("ALIMENTAÇÃO", "Mercado/Supermercado")),
        (["restaurante", "lanchonete", "cafe", "café", "pizzaria", "doceria", "acai", "açaí", "bar e pet", "churrascaria", "burguer", "burger", "mcdonald", "outback", "starbucks", "bk ", "bk*"], ("ALIMENTAÇÃO", "Restaurantes/Lanchonetes")),
        (["ifood", "rappi", "delivery"], ("ALIMENTAÇÃO", "Delivery")),
        
        # TRANSPORTE
        (["transporte", "taxi", "táxi", "uber", "99pop", "99*", "99app", "zapay", "detran"], ("TRANSPORTE", "Aplicativos")),
        (["posto", "combustivel", "combustível", "gasolina", "petroleo", "petróleo", "shell", "ipiranga", "br distribuidora"], ("TRANSPORTE", "Combustivel")),
        
        # SAÚDE
        (["drogaria", "farmacia", "farmácia", "saude", "saúde", "medica", "médica", "clinica", "clínica", "drogasil", "pacheco", "laboratorio", "laboratório", "exame"], ("SAÚDE", "Farmacia")),
        
        # PET
        (["petshop", "pet shop", "veterinario", "veterinário", "cobasi", "petz"], ("PET", "Veterinario")),
        
        # EDUCAÇÃO
        (["escola", "colegio", "colégio", "faculdade", "ensino", "educacao", "educação", "universidade", "curso", "alura"], ("EDUCAÇÃO", "Mensalidade")),
    ]
    
    for keywords, category in regras:
        if any(kw in full_text for kw in keywords):
            return category
            
    return None

async def enriquecer_um_lancamento(db: Session, lanc: Lancamento) -> bool:
    """
    Enriquece um único lançamento usando CNPJ (API) ou Regras de Nome/Descrição.
    Retorna True se houve alguma alteração (mesmo que apenas marcar como no_match).
    """
    cat_info = None
    alterado = False
    
    # 0. Detecção de Parcelamento via Descrição (Modo Deus)
    if "parc" in (lanc.descricao or "").lower() or "parcela" in (lanc.descricao or "").lower():
        # Se for parcelamento, podemos forçar uma tag ou subcategoria
        # Por enquanto vamos deixar seguir a regra de nome, mas marcamos internamente
        pass

    # 1. Tenta Enriquecimento via CNPJ (BrasilAPI -> CNAE)
    cnpj = lanc.cnpj_contraparte
    if cnpj and len(cnpj) == 14:
        dados = await buscar_dados_cnpj(cnpj)
        if dados and isinstance(dados, dict) and "error" not in dados:
            lanc.nome_contraparte = dados.get("nome_fantasia") or dados.get("razao_social")
            lanc.cnae = str(dados.get("cnae_fiscal") or "")
            logger.info(f"✨ [ENRICH] Dados obtidos para CNPJ {cnpj}: {lanc.nome_contraparte} (CNAE: {lanc.cnae})")
            cat_info = obter_categoria_por_cnae(lanc.cnae)
            alterado = True
        elif dados and dados.get("error") == "not_found":
            lanc.cnae = "nao_encontrado"
            alterado = True
        await asyncio.sleep(0.5) # Throttling para API externa

    # 2. Fallback: Tenta Categorização via Nome ou Descrição (Regras locais robustas)
    if not cat_info:
        cat_info = categorizar_por_nome(lanc.nome_contraparte, lanc.descricao)
        if cat_info:
            logger.info(f"🏷️ [ENRICH] Categoria sugerida para '{lanc.descricao}': {cat_info[0]}")
            if not lanc.cnae: 
                lanc.cnae = "rule_match"
                alterado = True

    # 3. Aplica a categorização se encontrada
    if cat_info:
        cat_nome, subcat_nome = cat_info
        cat = db.query(Categoria).filter(Categoria.nome == cat_nome).first()
        if cat:
            lanc.id_categoria = cat.id
            subcat = db.query(Subcategoria).filter(
                Subcategoria.nome == subcat_nome, 
                Subcategoria.id_categoria == cat.id
            ).first()
            if subcat:
                lanc.id_subcategoria = subcat.id
            
            logger.info(f"✅ [ENRICH] Lançamento '{lanc.descricao}' -> '{cat_nome}/{subcat_nome}'")
            alterado = True
    else:
        # Se não casou com nada, marcamos para não tentar de novo
        if not lanc.cnae:
            lanc.cnae = "no_match"
            alterado = True
            
    return alterado

async def enriquecer_lancamentos_pendentes(db: Session):
    """
    Busca lançamentos pendentes de enriquecimento (com CNPJ ou Nome de Contraparte)
    e tenta categorizá-los via CNAE ou Regras de Nome.
    """
    # Busca lançamentos que ainda não foram processados pelo enriquecimento
    lancamentos = db.query(Lancamento).filter(
        Lancamento.cnae.is_(None),
        Lancamento.origem == "open_finance"
    ).limit(50).all()
    
    if not lancamentos:
        return 0
        
    logger.info(f"🔍 [ENRICH] Analisando {len(lancamentos)} lançamentos pendentes...")
    
    atualizados = 0
    for lanc in lancamentos:
        if await enriquecer_um_lancamento(db, lanc):
            atualizados += 1
        
    db.commit()
    return atualizados
