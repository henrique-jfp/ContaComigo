import logging
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, extract
from models import Usuario, CarteiraFII, HistoricoAlertaFII
from fiis.brapi_client import BrapiClient

logger = logging.getLogger(__name__)

async def verificar_alertas_carteira(usuario: Usuario, db: Session) -> list[dict]:
    """
    Verifica alertas para todos os FIIs da carteira de um usuário.
    """
    posicoes = db.query(CarteiraFII).filter(
        CarteiraFII.id_usuario == usuario.id,
        CarteiraFII.ativo == True
    ).all()
    
    if not posicoes:
        return []

    client = BrapiClient()
    tickers = [p.ticker for p in posicoes]
    dados_mercado = client.get_fiis_em_lote(tickers)
    
    alertas_a_enviar = []
    hoje = datetime.now(timezone.utc)

    for pos in posicoes:
        ticker = pos.ticker
        dados = dados_mercado.get(ticker)
        if not dados:
            continue

        pvp = dados.get("pvp", 0)
        dy = (dados.get("dividendYield", 0) or 0) / 100.0
        
        # 1. RENDIMENTO_PAGO
        div_data = dados.get("dividendsData", {})
        if div_data and div_data.get("cashDividends"):
            last_div = div_data["cashDividends"][-1]
            # rate = valor, paymentDate = data pagamento, exDate = data ex
            valor_rend = last_div.get("rate", 0)
            ex_date_str = last_div.get("exDate", "") # ISO format
            
            if ex_date_str:
                try:
                    ex_date = datetime.fromisoformat(ex_date_str.replace("Z", "+00:00"))
                    # Se a data ex foi nos últimos 7 dias, avisar (se não avisou ainda este mês)
                    if hoje - ex_date < timedelta(days=7):
                        ja_enviado = db.query(HistoricoAlertaFII).filter(
                            HistoricoAlertaFII.id_usuario == usuario.id,
                            HistoricoAlertaFII.ticker == ticker,
                            HistoricoAlertaFII.tipo_alerta == 'rendimento_pago',
                            extract('month', HistoricoAlertaFII.enviado_em) == hoje.month,
                            extract('year', HistoricoAlertaFII.enviado_em) == hoje.year
                        ).first()
                        
                        if not ja_enviado:
                            total_receber = valor_rend * float(pos.quantidade_cotas)
                            alertas_a_enviar.append({
                                "ticker": ticker,
                                "tipo": "rendimento_pago",
                                "mensagem": f"💰 <b>{ticker}</b> declarou rendimento de R${valor_rend:.2f}/cota. Com suas {pos.quantidade_cotas:.0f} cotas, você vai receber aproximadamente <b>R${total_receber:.2f}</b>.",
                                "valor": valor_rend
                            })
                except Exception as e:
                    logger.error(f"Erro ao processar data ex de {ticker}: {e}")

        # 2. PVP_ALTO
        if pvp > 1.20:
            ja_enviado = db.query(HistoricoAlertaFII).filter(
                HistoricoAlertaFII.id_usuario == usuario.id,
                HistoricoAlertaFII.ticker == ticker,
                HistoricoAlertaFII.tipo_alerta == 'pvp_alto',
                HistoricoAlertaFII.enviado_em > hoje - timedelta(days=7)
            ).first()
            
            if not ja_enviado:
                pct_acima = (pvp - 1.0) * 100
                alertas_a_enviar.append({
                    "ticker": ticker,
                    "tipo": "pvp_alto",
                    "mensagem": f"⚠️ <b>{ticker}</b> está sendo negociado com P/VP de <b>{pvp:.2f}</b>. Isso significa que você está pagando {pct_acima:.0f}% acima do valor patrimonial. Considere aguardar uma correção antes de aportar mais.",
                    "valor": pvp
                })

        # 3. PVP_DESCONTO
        if 0.1 < pvp < 0.85:
            ja_enviado = db.query(HistoricoAlertaFII).filter(
                HistoricoAlertaFII.id_usuario == usuario.id,
                HistoricoAlertaFII.ticker == ticker,
                HistoricoAlertaFII.tipo_alerta == 'pvp_desconto',
                HistoricoAlertaFII.enviado_em > hoje - timedelta(days=7)
            ).first()
            
            if not ja_enviado:
                desc = (1.0 - pvp) * 100
                alertas_a_enviar.append({
                    "ticker": ticker,
                    "tipo": "pvp_desconto",
                    "mensagem": f"🟢 <b>{ticker}</b> está com desconto! P/VP de <b>{pvp:.2f}</b> significa que você está comprando imóveis por {desc:.0f}% abaixo do valor patrimonial. Pode ser uma boa oportunidade de aporte.",
                    "valor": pvp
                })

    return alertas_a_enviar

async def enviar_alertas_fii(application, db_factory):
    """
    Job agendado para enviar alertas de FII.
    """
    logger.info("🏢 Iniciando processamento de alertas de FII...")
    db: Session = db_factory()
    try:
        # Busca usuários que possuem FIIs ativos
        usuarios_com_fii = db.query(Usuario).join(CarteiraFII).filter(CarteiraFII.ativo == True).distinct().all()
        
        for usuario in usuarios_com_fii:
            try:
                alertas = await verificar_alertas_carteira(usuario, db)
                if not alertas:
                    continue
                
                for alerta in alertas:
                    try:
                        await application.bot.send_message(
                            chat_id=usuario.telegram_id,
                            text=alerta["mensagem"],
                            parse_mode='HTML'
                        )
                        
                        # Registra no histórico
                        novo_hist = HistoricoAlertaFII(
                            id_usuario=usuario.id,
                            ticker=alerta["ticker"],
                            tipo_alerta=alerta["tipo"],
                            valor_referencia=alerta["valor"]
                        )
                        db.add(novo_hist)
                        db.commit()
                        logger.info(f"✅ Alerta {alerta['tipo']} enviado para {usuario.id} sobre {alerta['ticker']}")
                        
                        # Pequeno delay entre mensagens para o mesmo usuário
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Erro ao enviar alerta individual para {usuario.id}: {e}")
                        db.rollback()
                        
            except Exception as e:
                logger.error(f"Erro ao processar alertas do usuário {usuario.id}: {e}")
                
    finally:
        db.close()
    logger.info("🏢 Fim do processamento de alertas de FII.")
