# gerente_financeiro/pdf_generator.py

import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, PageBreak, NextPageTemplate, Flowable, Image
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.piecharts import Pie
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

# --- CONFIGURAÇÃO DE CORES (Paleta Private Bank) ---
COLOR_PRIMARY = HexColor('#0B1220')    # Azul profundo
COLOR_ACCENT = HexColor('#00F0FF')     # Ciano neon
COLOR_ACCENT_2 = HexColor('#6366F1')   # Indigo
COLOR_BG_LIGHT = HexColor('#F8FAFC')   # Cinza muito claro
COLOR_TEXT_MAIN = HexColor('#0F172A')  # Cinza escuro
COLOR_TEXT_LIGHT = HexColor('#64748B') # Cinza médio
COLOR_SUCCESS = HexColor('#10B981')    # Verde esmeralda
COLOR_DANGER = HexColor('#EF4444')     # Vermelho
COLOR_WHITE = colors.white

# --- REGISTRO DE FONTES ---
def register_fonts():
    """Tenta registrar fontes Inter, fallback para Helvetica se não encontrar"""
    font_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts')
    try:
        pdfmetrics.registerFont(TTFont('Inter-Bold', os.path.join(font_dir, 'Inter-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('Inter-Regular', os.path.join(font_dir, 'Inter-Regular.ttf')))
        return 'Inter-Regular', 'Inter-Bold'
    except Exception:
        return 'Helvetica', 'Helvetica-Bold'

FONT_REG, FONT_BOLD = register_fonts()

class GradientCover(Flowable):
    """
    Desenha a capa ocupando 100% da página (sem margens).
    """
    def __init__(self, width, height, user_name, period_str):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.user_name = user_name
        self.period_str = period_str

    def draw(self):
        c = self.canv
        
        # 1. Fundo Azul Profundo (Ocupa tudo)
        c.setFillColor(COLOR_PRIMARY)
        c.rect(0, 0, self.width, self.height, fill=True, stroke=False)
        
        # 2. Elementos decorativos (tech glow)
        c.setFillColor(COLOR_ACCENT)
        c.setFillAlpha(0.08)
        c.circle(self.width - 40*mm, self.height - 10*mm, 220, fill=True, stroke=False)
        c.setFillColor(COLOR_ACCENT_2)
        c.setFillAlpha(0.08)
        c.circle(20*mm, 20*mm, 180, fill=True, stroke=False)
        c.setFillAlpha(1)

        # 3. Cabeçalho da Capa
        c.setFillColor(COLOR_WHITE)
        c.setFont(FONT_BOLD, 12)
        c.drawString(20*mm, self.height - 28*mm, "CONTACOMIGO // CRISIS SENSOR")
        
        # 4. Título Gigante
        c.setFont(FONT_BOLD, 40)
        c.drawString(20*mm, self.height - 80*mm, "Relatório")
        c.drawString(20*mm, self.height - 95*mm, "Financeiro")
        
        # 5. Linha de destaque
        c.setStrokeColor(COLOR_ACCENT)
        c.setLineWidth(2)
        c.line(20*mm, self.height - 110*mm, 60*mm, self.height - 110*mm)
        
        # 6. Período
        c.setFont(FONT_REG, 14)
        c.drawString(20*mm, self.height - 125*mm, self.period_str)
        
        # 7. Badge do Usuário (Retângulo arredondado simulado)
        c.setFillColor(HexColor('#111827'))
        c.roundRect(20*mm, self.height - 160*mm, 140*mm, 16*mm, 4*mm, fill=True, stroke=False)
        
        c.setFillColor(COLOR_ACCENT)
        c.setFont(FONT_BOLD, 9)
        c.drawString(25*mm, self.height - 150*mm, "PREPARADO EXCLUSIVAMENTE PARA")
        
        c.setFillColor(COLOR_WHITE)
        c.setFont(FONT_BOLD, 14)
        c.drawString(25*mm, self.height - 156*mm, self.user_name.upper())

class KPICard(Flowable):
    """Card de KPI com sombra simulada e borda fina"""
    def __init__(self, title, value, subtitle, trend="neutral", width=80*mm, height=35*mm):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.title = title
        self.value = value
        self.subtitle = subtitle
        self.trend = trend

    def draw(self):
        c = self.canv
        x, y = 0, 0
        
        # Sombra (Retângulo cinza deslocado)
        c.setFillColor(colors.Color(0,0,0,0.06))
        c.roundRect(x+2, y-2, self.width, self.height, 6, fill=True, stroke=False)
        
        # Fundo do Card
        c.setFillColor(COLOR_WHITE)
        c.setStrokeColor(HexColor('#E2E8F0'))
        c.roundRect(x, y, self.width, self.height, 6, fill=True, stroke=True)
        
        # Título (Label)
        c.setFillColor(COLOR_TEXT_LIGHT)
        c.setFont(FONT_REG, 9)
        c.drawString(x + 5*mm, y + self.height - 8*mm, self.title.upper())
        
        # Valor Principal
        c.setFillColor(COLOR_PRIMARY)
        c.setFont(FONT_BOLD, 16)
        # Ajusta tamanho da fonte se o valor for muito longo
        if len(str(self.value)) > 15:
             c.setFont(FONT_BOLD, 12)
        c.drawString(x + 5*mm, y + self.height - 18*mm, str(self.value))
        
        # Ícone e Subtítulo
        c.setFont(FONT_REG, 8)
        if self.trend == "up":
            c.setFillColor(COLOR_SUCCESS)
            icon = "▲"
        elif self.trend == "down":
            c.setFillColor(COLOR_DANGER)
            icon = "▼"
        else:
            c.setFillColor(COLOR_TEXT_LIGHT)
            icon = "•"
            
        c.drawString(x + 5*mm, y + 5*mm, f"{icon} {self.subtitle}")

def footer_canvas(canvas, doc):
    """Desenha rodapé nas páginas de conteúdo (não na capa)"""
    canvas.saveState()
    canvas.setFont(FONT_REG, 8)
    canvas.setFillColor(COLOR_TEXT_LIGHT)
    
    # Texto Esquerda
    canvas.drawString(20*mm, 10*mm, "ContaComigo • Relatório Confidencial")
    
    # Texto Direita (Número da página)
    canvas.drawRightString(A4[0] - 20*mm, 10*mm, f"Página {doc.page}")
    
    # Linha decorativa
    canvas.setStrokeColor(COLOR_ACCENT)
    canvas.setLineWidth(1)
    canvas.line(20*mm, 14*mm, A4[0]-20*mm, 14*mm)
    
    canvas.restoreState()

def validate_flowable_size(flowable, max_width, max_height):
    """
    Valida se o tamanho do Flowable está dentro dos limites permitidos.
    Se exceder, ajusta o tamanho proporcionalmente.
    """
    if flowable.width > max_width or flowable.height > max_height:
        scale_factor = min(max_width / flowable.width, max_height / flowable.height)
        flowable.width *= scale_factor
        flowable.height *= scale_factor
        if hasattr(flowable, 'x') and hasattr(flowable, 'y'):
            flowable.x *= scale_factor
            flowable.y *= scale_factor

def generate_financial_pdf(context):
    """
    Gera o PDF usando BaseDocTemplate para permitir layouts diferentes (Capa vs Conteúdo).
    """
    buffer = io.BytesIO()
    
    # 1. DEFINIÇÃO DOS FRAMES E TEMPLATES
    
    # Frame da Capa: Margem Zero, ocupa a folha toda
    frame_cover = Frame(
        0, 0, A4[0], A4[1], 
        id='cover', 
        leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0
    )
    template_cover = PageTemplate(id='Cover', frames=[frame_cover])
    
    # Frame do Conteúdo: Margens de 20mm
    frame_content = Frame(
        20*mm, 20*mm, A4[0]-40*mm, A4[1]-40*mm, 
        id='content'
    )
    template_content = PageTemplate(id='Normal', frames=[frame_content], onPage=footer_canvas)
    
    # Inicializa o Documento Base
    doc = BaseDocTemplate(buffer, pagesize=A4)
    doc.addPageTemplates([template_cover, template_content])
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos Personalizados
    style_h2 = ParagraphStyle(
        'H2', parent=styles['Heading2'], 
        fontName=FONT_BOLD, fontSize=16, 
        textColor=COLOR_PRIMARY, 
        spaceAfter=10, spaceBefore=20
    )
    style_h3 = ParagraphStyle(
        'H3', parent=styles['Heading3'],
        fontName=FONT_BOLD, fontSize=12,
        textColor=COLOR_PRIMARY,
        spaceAfter=6, spaceBefore=10
    )
    style_normal = ParagraphStyle(
        'Normal', parent=styles['Normal'], 
        fontName=FONT_REG, fontSize=10, 
        textColor=COLOR_TEXT_MAIN, leading=14
    )
    style_insight = ParagraphStyle(
        'Insight', parent=styles['Normal'], 
        fontName=FONT_REG, fontSize=10, 
        textColor=HexColor('#0B3B47'), 
        backColor=HexColor('#E6FAFF'), 
        padding=10, 
        borderColor=COLOR_ACCENT, 
        borderWidth=0.5, 
        borderRadius=5, 
        spaceAfter=5
    )

    # --- CONSTRUÇÃO DO CONTEÚDO ---

    def format_currency(value):
        try:
            return f"R$ {float(value):,.2f}"
        except (TypeError, ValueError):
            return "R$ 0,00"

    def format_percent(value):
        try:
            return f"{float(value):.1f}%"
        except (TypeError, ValueError):
            return "0.0%"

    # 1. CAPA (Usa o template 'Cover' implicitamente por ser o primeiro)
    elements.append(GradientCover(
        A4[0], A4[1], 
        context.get('usuario_nome', 'Investidor'), 
        context.get('periodo_extenso', 'Mês Atual')
    ))
    
    # Comando para mudar para o template 'Normal' na próxima página
    elements.append(NextPageTemplate('Normal'))
    elements.append(PageBreak())

    # 2. RESUMO EXECUTIVO (KPIs)
    elements.append(Paragraph("Resumo Executivo", style_h2))
    elements.append(Spacer(1, 5*mm))
    
    # Dados
    rec = context.get('total_receitas', 0)
    desp = context.get('total_gastos', 0)
    saldo = context.get('saldo_periodo', 0)
    poup = context.get('taxa_poupanca', 0)
    
    # Grid de Cards
    card_w = 82*mm
    card_h = 35*mm
    
    kpi_data = [
        [
            KPICard("Receitas", format_currency(rec), "Entradas", "up", card_w, card_h),
            KPICard("Despesas", format_currency(desp), "Saídas", "down", card_w, card_h)
        ],
        [
            KPICard("Saldo Líquido", format_currency(saldo), "Caixa", "neutral", card_w, card_h),
            KPICard("Taxa Poupança", format_percent(poup), "Meta: 20%", "up" if poup > 20 else "down", card_w, card_h)
        ]
    ]
    
    t_kpi = Table(kpi_data, colWidths=[85*mm, 85*mm], rowHeights=[40*mm, 40*mm])
    t_kpi.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(t_kpi)
    
    # 3. TENDÊNCIAS E MÉDIAS
    elements.append(Spacer(1, 6*mm))
    elements.append(Paragraph("Tendências e Médias", style_h2))

    tendencia_receita = context.get('tendencia_receita_percent', 0)
    tendencia_despesa = context.get('tendencia_despesa_percent', 0)
    media_receitas_3m = context.get('media_receitas_3m', 0)
    media_despesas_3m = context.get('media_despesas_3m', 0)
    media_saldo_3m = context.get('media_saldo_3m', 0)

    tendencia_table = [
        ["Receitas (mês vs anterior)", format_percent(tendencia_receita)],
        ["Despesas (mês vs anterior)", format_percent(tendencia_despesa)],
        ["Média receitas 3m", format_currency(media_receitas_3m)],
        ["Média despesas 3m", format_currency(media_despesas_3m)],
        ["Média saldo 3m", format_currency(media_saldo_3m)],
    ]
    t_tend = Table(tendencia_table, colWidths=[95*mm, 60*mm])
    t_tend.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_REG),
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('TEXTCOLOR', (0,0), (-1,-1), COLOR_TEXT_MAIN),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#E2E8F0')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_tend)

    # 4. GRÁFICO E TABELA
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("Distribuição de Gastos", style_h2))

    raw_cats = context.get('gastos_agrupados', [])
    cats = raw_cats[:6]

    grafico_pizza_png = context.get('grafico_pizza_png')
    if grafico_pizza_png:
        img = Image(io.BytesIO(grafico_pizza_png))
        img.drawWidth = 160*mm
        img.drawHeight = 90*mm
        elements.append(img)
    else:
        d = Drawing(400, 170)
        pc = Pie()
        pc.x = 125
        pc.y = 10
        pc.width = 150
        pc.height = 150

        if cats:
            pc.data = [float(x[1]) for x in cats]
            pc.labels = [f"{x[0]}" for x in cats]

            colors_list = [COLOR_PRIMARY, COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER, HexColor('#6366F1'), HexColor('#8B5CF6')]
            for i, color in enumerate(colors_list):
                if i < len(pc.data):
                    pc.slices[i].fillColor = color
                    pc.slices[i].strokeColor = COLOR_WHITE
                    pc.slices[i].strokeWidth = 1
        else:
            pc.data = [1]
            pc.labels = ["Sem dados"]
            pc.slices[0].fillColor = HexColor('#E2E8F0')

        d.add(pc)
        elements.append(d)
    
    # Tabela de Categorias
    elements.append(Spacer(1, 5*mm))
    
    if cats:
        table_data = [['Categoria', 'Valor', '%']]
        for cat, val in cats:
            val_float = float(val)
            perc = (val_float / float(desp) * 100) if desp > 0 else 0
            table_data.append([cat, f"R$ {val_float:,.2f}", f"{perc:.1f}%"])
            
        t_cat = Table(table_data, colWidths=[90*mm, 40*mm, 30*mm])
        t_cat.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), FONT_BOLD),
            ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,1), (-1,-1), FONT_REG),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [COLOR_BG_LIGHT, COLOR_WHITE]),
            ('GRID', (0,0), (-1,-1), 0.5, HexColor('#E2E8F0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_cat)
    else:
        elements.append(Paragraph("Nenhum gasto registrado neste período.", style_normal))

    # 5. EVOLUCAO 6 MESES
    elements.append(PageBreak())
    elements.append(Paragraph("Evolução 6 Meses", style_h2))

    grafico_evolucao_png = context.get('grafico_evolucao_png')
    if grafico_evolucao_png:
        img = Image(io.BytesIO(grafico_evolucao_png))
        img.drawWidth = 170*mm
        img.drawHeight = 85*mm
        elements.append(img)
    else:
        elements.append(Paragraph("Gráfico de evolução indisponível.", style_normal))

    # 6. TOP GASTOS
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph("Top Gastos", style_h2))
    top_gastos = context.get('top_gastos', [])
    if top_gastos:
        table_gastos = [["Descrição", "Categoria", "Valor", "Data"]]
        for g in top_gastos[:8]:
            table_gastos.append([
                str(getattr(g, 'descricao', '')),
                str(getattr(getattr(g, 'categoria', None), 'nome', '')),
                format_currency(getattr(g, 'valor', 0)),
                getattr(g, 'data_transacao', None).strftime('%d/%m/%Y') if getattr(g, 'data_transacao', None) else ''
            ])
        t_gastos = Table(table_gastos, colWidths=[70*mm, 45*mm, 30*mm, 25*mm])
        t_gastos.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), FONT_BOLD),
            ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('FONTNAME', (0,1), (-1,-1), FONT_REG),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [COLOR_BG_LIGHT, COLOR_WHITE]),
            ('GRID', (0,0), (-1,-1), 0.5, HexColor('#E2E8F0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_gastos)
    else:
        elements.append(Paragraph("Sem gastos registrados para o período.", style_normal))

    # 7. METAS
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph("Metas", style_h2))
    metas = context.get('metas', [])
    if metas:
        table_metas = [["Meta", "Atual", "Objetivo", "Progresso"]]
        for meta in metas[:6]:
            table_metas.append([
                meta.get('descricao', 'Meta'),
                format_currency(meta.get('valor_atual', 0)),
                format_currency(meta.get('valor_meta', 0)),
                format_percent(meta.get('progresso_percent', 0)),
            ])
        t_metas = Table(table_metas, colWidths=[80*mm, 35*mm, 35*mm, 25*mm])
        t_metas.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), FONT_BOLD),
            ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0,0), (-1,0), COLOR_WHITE),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,1), (-1,-1), FONT_REG),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [COLOR_BG_LIGHT, COLOR_WHITE]),
            ('GRID', (0,0), (-1,-1), 0.5, HexColor('#E2E8F0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_metas)
    else:
        elements.append(Paragraph("Nenhuma meta registrada.", style_normal))

    # 8. INSIGHTS
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph("Insights do Alfredo", style_h2))

    insights = context.get('insights', [])
    analise_ia = context.get('analise_ia')
    if analise_ia:
        elements.append(Paragraph(f"💡 {analise_ia}", style_insight))
        elements.append(Spacer(1, 2*mm))

    if not insights and not analise_ia:
        insights = ["Continue registrando seus gastos para receber análises personalizadas."]

    for insight in insights:
        elements.append(Paragraph(f"💡 {insight}", style_insight))
        elements.append(Spacer(1, 2*mm))

    # 6. GERAR PDF
    try:
        # Adiciona validação antes de incluir elementos no PDF
        for element in elements:
            if isinstance(element, GradientCover):
                validate_flowable_size(element, frame_content._width, frame_content._height)
            elif isinstance(element, Drawing):
                for sub_element in element.contents:
                    if hasattr(sub_element, 'width') and hasattr(sub_element, 'height'):
                        validate_flowable_size(sub_element, frame_content._width, frame_content._height)
        
        doc.build(elements)
    except Exception as e:
        print(f"Erro crítico ao construir PDF: {e}")
        # Retorna um PDF vazio ou lança erro dependendo da necessidade
        raise e
    
    buffer.seek(0)
    return buffer.getvalue()