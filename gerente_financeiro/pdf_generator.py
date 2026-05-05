"""
Gerador de relatório financeiro premium — ContaComigo
Layout: Capa escura | Resumo KPI | Score Financeiro | Distribuição |
        Evolução 6m | Heatmap | Top Despesas | Metas | Insights Alfredo
"""

import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, PageBreak, NextPageTemplate, Flowable, Image,
    HRFlowable, KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color
from reportlab.lib import colors

# ── Paleta de Cores ─────────────────────────────────────────
C_NAVY      = HexColor('#0B1220')
C_CYAN      = HexColor('#00C2CB')
C_INDIGO    = HexColor('#6366F1')
C_EMERALD   = HexColor('#10B981')
C_RED       = HexColor('#EF4444')
C_AMBER     = HexColor('#F59E0B')
C_BG        = HexColor('#F8FAFC')
C_BORDER    = HexColor('#E2E8F0')
C_TEXT      = HexColor('#0F172A')
C_MUTED     = HexColor('#64748B')
C_WHITE     = colors.white
C_CARD_BG   = HexColor('#FFFFFF')
C_SECTION   = HexColor('#F1F5F9')

# Escala de score (verde → amarelo → vermelho)
def score_color(score: float) -> HexColor:
    if score >= 75:
        return C_EMERALD
    if score >= 50:
        return C_AMBER
    return C_RED


# ── Fontes ──────────────────────────────────────────────────
def register_fonts():
    font_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts')
    try:
        pdfmetrics.registerFont(TTFont('Inter-Bold',    os.path.join(font_dir, 'Inter-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('Inter-Regular', os.path.join(font_dir, 'Inter-Regular.ttf')))
        pdfmetrics.registerFont(TTFont('Inter-Light',   os.path.join(font_dir, 'Inter-Light.ttf')))
        return 'Inter-Regular', 'Inter-Bold', 'Inter-Light'
    except Exception:
        return 'Helvetica', 'Helvetica-Bold', 'Helvetica'

FONT_REG, FONT_BOLD, FONT_LIGHT = register_fonts()


from finance_utils import is_expense_type

# ── Utilitários de formatação ────────────────────────────────
def fmt_brl(value) -> str:
    try:
        v = float(value)
        return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return "R$ 0,00"

def fmt_pct(value) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0,0%"

def trend_arrow(value) -> tuple[str, HexColor]:
    """Retorna (símbolo, cor) baseado na direção da tendência."""
    try:
        v = float(value)
        if v > 1:
            return "▲", C_EMERALD
        if v < -1:
            return "▼", C_RED
        return "→", C_MUTED
    except (TypeError, ValueError):
        return "→", C_MUTED


# ── Flowables Personalizados ─────────────────────────────────

class GradientCover(Flowable):
    """Capa com fundo escuro, elementos decorativos e badge do usuário."""

    def __init__(self, width, height, user_name, period_str, mes_ano):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.user_name = user_name
        self.period_str = period_str
        self.mes_ano = mes_ano

    def wrap(self, availWidth, availHeight):
        """Informa ao ReportLab o tamanho que este elemento ocupa."""
        return self.width, self.height

    def draw(self):
        c = self.canv
        W, H = self.width, self.height

        # Fundo principal
        c.setFillColor(C_NAVY)
        c.rect(0, 0, W, H, fill=True, stroke=False)

        # Círculos decorativos com opacidade
        for col, x, y, r, alpha in [
            (C_CYAN,   W - 35*mm, H - 8*mm,  220, 0.06),
            (C_INDIGO, 15*mm,     18*mm,      180, 0.07),
            (C_EMERALD, W*0.5,    H*0.3,      130, 0.04),
        ]:
            c.setFillColor(col)
            c.setFillAlpha(alpha)
            c.circle(x, y, r, fill=True, stroke=False)
        c.setFillAlpha(1)

        # Linha decorativa superior (cyan)
        c.setStrokeColor(C_CYAN)
        c.setLineWidth(3)
        c.line(0, H - 2*mm, W, H - 2*mm)

        # Tag do produto
        c.setFillColor(C_CYAN)
        c.setFont(FONT_BOLD, 9)
        c.drawString(20*mm, H - 22*mm, "CONTACOMIGO  //  RELATÓRIO FINANCEIRO")

        # Título central
        c.setFillColor(C_WHITE)
        c.setFont(FONT_BOLD, 52)
        c.drawString(20*mm, H - 72*mm, "Relatório")
        c.setFont(FONT_BOLD, 38)
        c.drawString(20*mm, H - 92*mm, "Financeiro")

        # Sublinhado ciano
        c.setStrokeColor(C_CYAN)
        c.setLineWidth(2.5)
        c.line(20*mm, H - 97*mm, 72*mm, H - 97*mm)

        # Período
        c.setFillColor(HexColor('#94A3B8'))
        c.setFont(FONT_REG, 16)
        c.drawString(20*mm, H - 112*mm, self.period_str)

        # Separador pontilhado
        c.setStrokeColor(HexColor('#1E293B'))
        c.setLineWidth(1)
        c.setDash(2, 4)
        c.line(20*mm, H - 130*mm, W - 20*mm, H - 130*mm)
        c.setDash()

        # Badge do usuário
        bx, by, bw, bh = 20*mm, H - 166*mm, 155*mm, 24*mm
        c.setFillColor(HexColor('#111827'))
        c.roundRect(bx, by, bw, bh, 5*mm, fill=True, stroke=False)
        c.setStrokeColor(C_CYAN)
        c.setLineWidth(1)
        c.roundRect(bx, by, bw, bh, 5*mm, fill=False, stroke=True)

        c.setFillColor(C_CYAN)
        c.setFont(FONT_BOLD, 7.5)
        c.drawString(bx + 5*mm, by + bh - 8*mm, "PREPARADO EXCLUSIVAMENTE PARA")

        c.setFillColor(C_WHITE)
        c.setFont(FONT_BOLD, 13)
        c.drawString(bx + 5*mm, by + 5*mm, self.user_name.upper())

        # Rodapé da capa
        c.setFillColor(HexColor('#475569'))
        c.setFont(FONT_REG, 8)
        c.drawCentredString(W / 2, 12*mm, "Documento confidencial gerado automaticamente pelo ContaComigo")


class KPICard(Flowable):
    """Card de KPI premium com indicador de tendência."""

    def __init__(self, title, value, subtitle, trend="neutral",
                 width=80*mm, height=38*mm, accent_color=None):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.title = title
        self.value = value
        self.subtitle = subtitle
        self.trend = trend
        self.accent = accent_color or C_CYAN

    def draw(self):
        c = self.canv
        x, y = 0, 0
        W, H = self.width, self.height

        # Sombra
        c.setFillColor(Color(0, 0, 0, 0.05))
        c.roundRect(x + 1.5, y - 1.5, W, H, 6, fill=True, stroke=False)

        # Fundo branco
        c.setFillColor(C_CARD_BG)
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.5)
        c.roundRect(x, y, W, H, 6, fill=True, stroke=True)

        # Barra de acento (lateral esquerda)
        c.setFillColor(self.accent)
        c.roundRect(x, y, 3, H, 3, fill=True, stroke=False)

        # Título
        c.setFillColor(C_MUTED)
        c.setFont(FONT_BOLD, 7.5)
        c.drawString(x + 7*mm, y + H - 10*mm, self.title.upper())

        # Valor principal
        c.setFillColor(C_NAVY)
        font_size = 19
        val_str = str(self.value)
        if len(val_str) > 13:
            font_size = 15
        elif len(val_str) > 10:
            font_size = 17
        c.setFont(FONT_BOLD, font_size)
        c.drawString(x + 7*mm, y + H / 2 - 2*mm, val_str)

        # Linha separadora
        c.setStrokeColor(C_SECTION)
        c.setLineWidth(0.4)
        c.line(x + 7*mm, y + 11*mm, x + W - 7*mm, y + 11*mm)

        # Ícone de tendência + subtítulo
        if self.trend == "up":
            icon, icon_color = "▲", C_EMERALD
        elif self.trend == "down":
            icon, icon_color = "▼", C_RED
        else:
            icon, icon_color = "•", C_MUTED

        c.setFont(FONT_REG, 8)
        c.setFillColor(icon_color)
        c.drawString(x + 7*mm, y + 5*mm, f"{icon}  {self.subtitle}")


class ScoreGauge(Flowable):
    """
    Arco semi-circular de score financeiro (0–100).
    Desenha um arco colorido com ponteiro e valor central.
    """

    def __init__(self, score: float, width=90*mm, height=52*mm):
        Flowable.__init__(self)
        self.score = min(max(float(score), 0), 100)
        self.width = width
        self.height = height

    def draw(self):
        import math
        c = self.canv
        cx, cy = self.width / 2, 16*mm
        r_out, r_in = 22*mm, 15*mm

        # Fundo cinza do arco
        c.setStrokeColor(C_BORDER)
        c.setLineWidth((r_out - r_in) / mm)
        c.setLineCap(1)
        c.arc(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
              startAng=180, extent=180)

        # Arco colorido preenchido até o score
        extent = (self.score / 100 * 180)
        if extent < 0.1: extent = 0.1 # Proteção contra ZeroDivisionError no ReportLab
        
        col = score_color(self.score)
        c.setStrokeColor(col)
        c.arc(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
              startAng=180, extent=extent)

        # Valor numérico
        c.setFillColor(C_NAVY)
        c.setFont(FONT_BOLD, 22)
        c.drawCentredString(cx, cy + 4*mm, f"{self.score:.0f}")

        # Label "/100"
        c.setFont(FONT_REG, 8)
        c.setFillColor(C_MUTED)
        c.drawCentredString(cx, cy - 3*mm, "/ 100")

        # Rótulo
        c.setFont(FONT_BOLD, 9)
        c.setFillColor(col)
        if self.score >= 75:
            label = "Excelente"
        elif self.score >= 50:
            label = "Moderado"
        else:
            label = "Atenção"
        c.drawCentredString(cx, cy - 10*mm, label)


class SectionHeader(Flowable):
    """Cabeçalho de seção com linha decorativa e ícone."""

    def __init__(self, title: str, icon: str = "●", width=170*mm):
        Flowable.__init__(self)
        self.title = title
        self.icon = icon
        self.width = width
        self.height = 14*mm

    def draw(self):
        c = self.canv
        W = self.width

        # Fundo
        c.setFillColor(C_NAVY)
        c.roundRect(0, 2*mm, W, 10*mm, 3, fill=True, stroke=False)

        # Linha cyan lateral
        c.setFillColor(C_CYAN)
        c.rect(0, 2*mm, 2.5, 10*mm, fill=True, stroke=False)

        # Texto
        c.setFillColor(C_WHITE)
        c.setFont(FONT_BOLD, 11)
        c.drawString(6*mm, 5.5*mm, f"{self.icon}  {self.title.upper()}")


class InsightCard(Flowable):
    """Card de insight com borda esquerda colorida."""

    def __init__(self, text: str, index: int = 0, width=170*mm):
        Flowable.__init__(self)
        self.text = text
        self.index = index
        self.width = width
        accent_colors = [C_CYAN, C_EMERALD, C_INDIGO, C_AMBER]
        self.accent = accent_colors[index % len(accent_colors)]
        # Altura dinâmica: ~5mm por 60 caracteres + padding
        lines = max(1, len(text) // 70 + 1)
        self.height = (lines * 4.5 + 10) * mm

    def draw(self):
        c = self.canv
        W, H = self.width, self.height

        # Fundo
        c.setFillColor(C_BG)
        c.roundRect(0, 0, W, H, 4, fill=True, stroke=False)

        # Borda accent
        c.setFillColor(self.accent)
        c.rect(0, 0, 3, H, fill=True, stroke=False)

        # Número
        c.setFillColor(self.accent)
        c.setFont(FONT_BOLD, 10)
        c.drawString(7*mm, H - 7*mm, str(self.index + 1))

        # Texto (truncado para caber)
        c.setFillColor(C_TEXT)
        c.setFont(FONT_REG, 8.5)
        # Simples quebra manual de texto
        words = self.text.split()
        line, lines = '', []
        for w in words:
            test = f"{line} {w}".strip()
            if len(test) * 2.3 < (W - 18*mm) / mm:
                line = test
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        for i, l in enumerate(lines[:6]):
            c.drawString(13*mm, H - 7*mm - i * 4.5*mm, l)


# ── Rodapé ──────────────────────────────────────────────────

def footer_canvas(canvas, doc):
    canvas.saveState()
    # Linha
    canvas.setStrokeColor(C_CYAN)
    canvas.setLineWidth(0.8)
    canvas.line(20*mm, 15*mm, A4[0] - 20*mm, 15*mm)
    # Textos
    canvas.setFont(FONT_REG, 7.5)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(20*mm, 9*mm, "ContaComigo  •  Relatório Confidencial")
    canvas.drawRightString(A4[0] - 20*mm, 9*mm, f"Página {doc.page}")
    canvas.restoreState()


# ── Função principal ─────────────────────────────────────────

# ── Helpers de Estilo ───────────────────────────────────────
def get_pdf_style(name, **kw):
    styles = getSampleStyleSheet()
    defaults = dict(fontName=FONT_REG, fontSize=10,
                    textColor=C_TEXT, leading=14)
    defaults.update(kw)
    return ParagraphStyle(name, parent=styles['Normal'], **defaults)

# Alias para manter compatibilidade com o código interno
style = get_pdf_style


def generate_financial_pdf(context: dict) -> bytes:
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4,
                          leftMargin=15*mm, rightMargin=15*mm,
                          topMargin=15*mm, bottomMargin=20*mm)
    
    # 1. Template da CAPA (Full Screen - Sem margens no Frame)
    frame_capa = Frame(0, 0, A4[0], A4[1], id='capa_frame', 
                       leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    template_capa = PageTemplate(id='Capa', frames=[frame_capa])
    
    # 2. Template NORMAL (Com margens e Rodapé)
    frame_normal = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal_frame')
    template_normal = PageTemplate(id='Normal', frames=[frame_normal], onPage=footer_canvas)
    
    doc.addPageTemplates([template_capa, template_normal])

    elements = []
    
    # Estilos básicos
    s_small  = style('small', fontSize=8.5, textColor=C_MUTED)
    s_label  = style('label', fontName=FONT_BOLD, fontSize=8,
                     textColor=C_MUTED, spaceBefore=0, spaceAfter=2)
    s_caption = style('caption', fontSize=8, textColor=C_MUTED,
                      alignment=1)  # centrado

    # Dados do contexto
    rec   = context.get('total_receitas', 0)
    desp  = context.get('total_gastos', 0)
    saldo = context.get('saldo_periodo', 0)
    poup  = context.get('taxa_poupanca', 0)
    tr_r  = context.get('tendencia_receita_percent', 0)
    tr_d  = context.get('tendencia_despesa_percent', 0)
    m3_r  = context.get('media_receitas_3m', 0)
    m3_d  = context.get('media_despesas_3m', 0)
    m3_s  = context.get('media_saldo_3m', 0)

    # Score financeiro
    score = context.get('score_financeiro')
    if score is None:
        base = min(poup / 30 * 60, 60)
        bonus_saldo = 20 if saldo > 0 else 0
        bonus_med   = 20 if m3_s > 0 else 0
        score = min(base + bonus_saldo + bonus_med, 100)

    # ── 1. CAPA ──────────────────────────────────────────────
    # Reduzimos um pouco mais para segurança (5mm)
    elements.append(GradientCover(
        A4[0] - 5*mm, A4[1] - 5*mm,
        context.get('usuario_nome', 'Investidor'),
        context.get('periodo_extenso', 'Período Atual'),
        context.get('mes_ano', ''),
    ))
    
    # Avisa que a PRÓXIMA página deve usar o template Normal
    elements.append(NextPageTemplate('Normal'))
    elements.append(PageBreak())

    # ── 2. RESUMO EXECUTIVO ───────────────────────────────────
    elements.append(SectionHeader("Resumo Executivo", "📊"))
    elements.append(Spacer(1, 5*mm))

    card_w, card_h = 83*mm, 40*mm
    arrow_r, col_r = trend_arrow(tr_r)
    arrow_d, col_d = trend_arrow(-tr_d)   # inverso: despesa subindo = ruim

    kpi_table = Table([
        [
            KPICard("Receitas Totais",   fmt_brl(rec),
                    f"{arrow_r} {fmt_pct(tr_r)} vs mês anterior",
                    "up", card_w, card_h, C_EMERALD),
            KPICard("Despesas Totais",   fmt_brl(desp),
                    f"{arrow_d} {fmt_pct(tr_d)} vs mês anterior",
                    "down", card_w, card_h, C_RED),
        ],
        [
            KPICard("Saldo Líquido",     fmt_brl(saldo),
                    "Caixa do período",
                    "up" if saldo > 0 else "down", card_w, card_h, C_INDIGO),
            KPICard("Taxa de Poupança",  fmt_pct(poup),
                    "Meta recomendada: 20%",
                    "up" if poup >= 20 else "down", card_w, card_h, C_AMBER),
        ],
    ], colWidths=[86*mm, 86*mm], rowHeights=[44*mm, 44*mm])
    kpi_table.setStyle(TableStyle([
        ('VALIGN',  (0, 0), (-1, -1), 'TOP'),
        ('ALIGN',   (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(kpi_table)

    # ── 3. SCORE FINANCEIRO + MÉTRICAS COMPLEMENTARES ────────
    elements.append(Spacer(1, 4*mm))
    elements.append(SectionHeader("Saúde Financeira do Mês", "🏅"))
    elements.append(Spacer(1, 4*mm))

    score_table_data = [
        [
            ScoreGauge(score, 88*mm, 54*mm),
            Table([
                [Paragraph("<b>Médias dos Últimos 3 Meses</b>", style('h3m', fontName=FONT_BOLD, fontSize=10))],
                [Table([
                    ["Média Receitas 3m",  fmt_brl(m3_r)],
                    ["Média Despesas 3m",  fmt_brl(m3_d)],
                    ["Média Saldo 3m",     fmt_brl(m3_s)],
                    ["Transações no mês",  str(context.get('total_transacoes', '-'))],
                    ["Dia com mais gastos", f"Dia {context.get('dia_mais_gasto', '-')}" if context.get('dia_mais_gasto') else '-'],
                    ["Categoria top",      str(context.get('categoria_top', '-'))[:28]],
                ], colWidths=[60*mm, 48*mm],
                   style=TableStyle([
                       ('FONTNAME',    (0, 0), (-1, -1), FONT_REG),
                       ('FONTSIZE',    (0, 0), (-1, -1), 8.5),
                       ('TEXTCOLOR',   (0, 0), (0, -1), C_MUTED),
                       ('TEXTCOLOR',   (1, 0), (1, -1), C_NAVY),
                       ('FONTNAME',    (1, 0), (1, -1), FONT_BOLD),
                       ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_BG, C_WHITE]),
                       ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                       ('TOPPADDING',    (0, 0), (-1, -1), 5),
                       ('LEFTPADDING',   (0, 0), (-1, -1), 6),
                       ('GRID', (0, 0), (-1, -1), 0.3, C_BORDER),
                   ]))]
            ], rowHeights=None)
        ]
    ]

    score_table = Table(score_table_data, colWidths=[92*mm, 82*mm])
    score_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(score_table)

    # ── 4. DISTRIBUIÇÃO DE GASTOS ─────────────────────────────
    elements.append(Spacer(1, 6*mm))
    elements.append(SectionHeader("Distribuição de Despesas", "🥧"))
    elements.append(Spacer(1, 4*mm))

    cats = context.get('gastos_agrupados', [])[:8]
    pizza_png = context.get('grafico_pizza_png')

    if pizza_png:
        img = Image(io.BytesIO(pizza_png))
        img.drawWidth  = 170*mm
        img.drawHeight = 85*mm
        elements.append(img)
        elements.append(Paragraph(
            "Transferências excluídas do cálculo de despesas.",
            s_caption
        ))
    else:
        elements.append(Paragraph("Gráfico indisponível.", s_body))

    elements.append(Spacer(1, 4*mm))

    # Tabela de categorias
    if cats:
        total_desp = float(desp) if desp else 1
        header = [
            Paragraph('<b>Categoria</b>', style('th', fontName=FONT_BOLD,
                      fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Valor</b>', style('th2', fontName=FONT_BOLD,
                      fontSize=9, textColor=C_WHITE, alignment=2)),
            Paragraph('<b>%</b>', style('th3', fontName=FONT_BOLD,
                      fontSize=9, textColor=C_WHITE, alignment=2)),
        ]
        rows = [header]
        for i, (cat, val) in enumerate(cats):
            val_f = float(val)
            pct   = val_f / total_desp * 100
            # Barra de progresso visual simples: █ chars
            bar_len = max(1, int(pct / 5))
            bar = '█' * bar_len
            rows.append([
                cat[:35],
                fmt_brl(val_f),
                f"{pct:.1f}%  {bar}",
            ])

        t_cat = Table(rows, colWidths=[80*mm, 40*mm, 50*mm])
        t_cat.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0),  C_NAVY),
            ('TEXTCOLOR',    (0, 0), (-1, 0),  C_WHITE),
            ('FONTNAME',     (0, 0), (-1, 0),  FONT_BOLD),
            ('FONTSIZE',     (0, 0), (-1, 0),  9),
            ('FONTNAME',     (0, 1), (-1, -1), FONT_REG),
            ('FONTSIZE',     (0, 1), (-1, -1), 8.5),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_BG, C_WHITE]),
            ('ALIGN',        (1, 0), (-1, -1), 'RIGHT'),
            ('TEXTCOLOR',    (1, 1), (1, -1),  C_NAVY),
            ('FONTNAME',     (1, 1), (1, -1),  FONT_BOLD),
            ('TEXTCOLOR',    (2, 1), (2, -1),  C_INDIGO),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 7),
            ('TOPPADDING',   (0, 0), (-1, -1), 7),
            ('LEFTPADDING',  (0, 0), (-1, -1), 8),
            ('LINEBELOW',    (0, 0), (-1, 0),  1.5, C_CYAN),
            ('LINEBELOW',    (0, 1), (-1, -2), 0.3, C_BORDER),
        ]))
        elements.append(t_cat)
    else:
        elements.append(Paragraph("Nenhum gasto registrado neste período.", s_body))

    # ── 5. EVOLUÇÃO 6 MESES ───────────────────────────────────
    elements.append(PageBreak())
    elements.append(SectionHeader("Evolução dos Últimos 6 Meses", "📈"))
    elements.append(Spacer(1, 4*mm))

    evolucao_png = context.get('grafico_evolucao_png')
    if evolucao_png:
        img2 = Image(io.BytesIO(evolucao_png))
        img2.drawWidth  = 170*mm
        img2.drawHeight = 90*mm
        elements.append(img2)
        elements.append(Paragraph(
            "Barras: Receitas (verde) e Despesas (vermelho). Linha roxa: Saldo líquido.",
            s_caption
        ))
    else:
        elements.append(Paragraph("Gráfico de evolução indisponível.", s_body))

    # ── 6. PERFIL SEMANAL DE GASTOS ───────────────────────────
    semanal_png = context.get('grafico_semanal_png')
    if semanal_png:
        elements.append(Spacer(1, 6*mm))
        elements.append(SectionHeader("Perfil Semanal de Movimentação", "🗓️"))
        elements.append(Spacer(1, 4*mm))
        img3 = Image(io.BytesIO(semanal_png))
        img3.drawWidth  = 170*mm
        img3.drawHeight = 70*mm
        elements.append(img3)
        elements.append(Paragraph(
            "Distribuição de entradas (verde) e saídas (vermelho) agrupadas por dia da semana.",
            s_caption
        ))

    # ── 7. TOP RECEITAS ───────────────────────────────────────
    top_receitas = context.get('top_receitas', [])
    if top_receitas:
        elements.append(Spacer(1, 8*mm))
        elements.append(SectionHeader("Maiores Entradas do Mês", "💰"))
        elements.append(Spacer(1, 4*mm))

        header_r = [
            Paragraph('<b>#</b>',         style('tr0', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Descrição</b>',  style('tr1', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Categoria</b>',  style('tr2', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Valor</b>',      style('tr3', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE, alignment=2)),
            Paragraph('<b>Data</b>',       style('tr4', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE, alignment=2)),
        ]
        rows_r = [header_r]
        for i, g in enumerate(top_receitas[:8], 1):
            desc = str(getattr(g, 'descricao', '') or '')[:40]
            cat  = str(getattr(getattr(g, 'categoria', None), 'nome', '') or '')[:20]
            val  = fmt_brl(float(getattr(g, 'valor', 0)))
            dt   = getattr(g, 'data_transacao', None)
            data_str = dt.strftime('%d/%m/%y') if dt else '-'
            rows_r.append([str(i), desc, cat, val, data_str])

        t_r = Table(rows_r, colWidths=[8*mm, 68*mm, 40*mm, 32*mm, 22*mm])
        t_r.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('FONTNAME',      (0, 0), (-1, 0),  FONT_BOLD),
            ('FONTSIZE',      (0, 0), (-1, -1), 8.5),
            ('FONTNAME',      (0, 1), (-1, -1), FONT_REG),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_BG, C_WHITE]),
            ('ALIGN',         (3, 0), (4, -1),  'RIGHT'),
            ('TEXTCOLOR',     (3, 1), (3, -1),  C_EMERALD),
            ('FONTNAME',      (3, 1), (3, -1),  FONT_BOLD),
            ('TEXTCOLOR',     (0, 1), (0, -1),  C_MUTED),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('LINEBELOW',     (0, 0), (-1, 0),  1.5, C_CYAN),
            ('LINEBELOW',     (0, 1), (-1, -2), 0.3, C_BORDER),
        ]))
        elements.append(t_r)

    # ── 8. TOP DESPESAS ───────────────────────────────────────
    elements.append(Spacer(1, 8*mm))
    elements.append(SectionHeader("Top Despesas do Mês", "💸"))
    elements.append(Spacer(1, 4*mm))

    top_gastos = context.get('top_gastos', [])
    if top_gastos:
        header_g = [
            Paragraph('<b>#</b>',         style('tg0', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Descrição</b>',  style('tg1', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Categoria</b>',  style('tg2', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Valor</b>',      style('tg3', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE, alignment=2)),
            Paragraph('<b>Data</b>',       style('tg4', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE, alignment=2)),
        ]
        rows_g = [header_g]
        for i, g in enumerate(top_gastos[:10], 1):
            desc = str(getattr(g, 'descricao', '') or '')[:40]
            cat  = str(getattr(getattr(g, 'categoria', None), 'nome', '') or '')[:20]
            val  = fmt_brl(abs(float(getattr(g, 'valor', 0))))
            dt   = getattr(g, 'data_transacao', None)
            data_str = dt.strftime('%d/%m/%y') if dt else '-'
            rows_g.append([str(i), desc, cat, val, data_str])

        t_g = Table(rows_g, colWidths=[8*mm, 68*mm, 40*mm, 32*mm, 22*mm])
        t_g.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('FONTNAME',      (0, 0), (-1, 0),  FONT_BOLD),
            ('FONTSIZE',      (0, 0), (-1, -1), 8.5),
            ('FONTNAME',      (0, 1), (-1, -1), FONT_REG),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_BG, C_WHITE]),
            ('ALIGN',         (3, 0), (4, -1),  'RIGHT'),
            ('TEXTCOLOR',     (3, 1), (3, -1),  C_RED),
            ('FONTNAME',      (3, 1), (3, -1),  FONT_BOLD),
            ('TEXTCOLOR',     (0, 1), (0, -1),  C_MUTED),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('LINEBELOW',     (0, 0), (-1, 0),  1.5, C_CYAN),
            ('LINEBELOW',     (0, 1), (-1, -2), 0.3, C_BORDER),
        ]))
        elements.append(t_g)
    else:
        elements.append(Paragraph("Nenhum gasto individual registrado neste período.", s_body))

    # ── 8. METAS ──────────────────────────────────────────────
    metas = context.get('metas', [])
    if metas:
        elements.append(Spacer(1, 8*mm))
        elements.append(SectionHeader("Metas Financeiras", "🎯"))
        elements.append(Spacer(1, 4*mm))

        header_m = [
            Paragraph('<b>Meta</b>',      style('tm1', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE)),
            Paragraph('<b>Atual</b>',     style('tm2', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE, alignment=2)),
            Paragraph('<b>Objetivo</b>',  style('tm3', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE, alignment=2)),
            Paragraph('<b>Progresso</b>', style('tm4', fontName=FONT_BOLD, fontSize=9, textColor=C_WHITE, alignment=2)),
        ]
        rows_m = [header_m]
        for m in metas[:8]:
            prog = float(m.get('progresso_percent', 0))
            bar  = '█' * int(min(prog, 100) / 10) + '░' * (10 - int(min(prog, 100) / 10))
            rows_m.append([
                str(m.get('descricao', 'Meta'))[:40],
                fmt_brl(m.get('valor_atual', 0)),
                fmt_brl(m.get('valor_meta', 0)),
                f"{prog:.0f}%  {bar}",
            ])

        t_m = Table(rows_m, colWidths=[70*mm, 30*mm, 30*mm, 42*mm])
        t_m.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C_NAVY),
            ('FONTNAME',      (0, 0), (-1, 0),  FONT_BOLD),
            ('FONTSIZE',      (0, 0), (-1, -1), 8.5),
            ('FONTNAME',      (0, 1), (-1, -1), FONT_REG),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_BG, C_WHITE]),
            ('ALIGN',         (1, 0), (-1, -1), 'RIGHT'),
            ('TEXTCOLOR',     (3, 1), (3, -1),  C_INDIGO),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING',    (0, 0), (-1, -1), 7),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('LINEBELOW',     (0, 0), (-1, 0),  1.5, C_CYAN),
            ('LINEBELOW',     (0, 1), (-1, -2), 0.3, C_BORDER),
        ]))
        elements.append(t_m)

    # ── 9. INSIGHTS DO ALFREDO ────────────────────────────────
    elements.append(PageBreak())
    elements.append(SectionHeader("Insights do Alfredo", "🤖"))
    elements.append(Spacer(1, 5*mm))

    analise_ia = context.get('analise_ia', '')
    insights   = context.get('insights', [])

    # Converte analise_ia em lista de insights individuais (separa por número ou ponto final duplo)
    all_insights = list(insights)
    if analise_ia and analise_ia not in insights:
        import re
        # Tenta separar em pontos de insight numerados: "1. xxx 2. yyy"
        partes = re.split(r'\n+|\d+\.\s+', analise_ia.strip())
        partes = [p.strip() for p in partes if len(p.strip()) > 20]
        all_insights = (partes if partes else [analise_ia]) + all_insights

    if not all_insights:
        all_insights = [
            "Continue registrando seus gastos para receber análises personalizadas do Alfredo."
        ]

    for i, insight in enumerate(all_insights[:6]):
        elements.append(InsightCard(insight, i))
        elements.append(Spacer(1, 3*mm))

    # Rodapé final
    elements.append(Spacer(1, 10*mm))
    elements.append(HRFlowable(width='100%', color=C_BORDER, thickness=0.5))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph(
        f"Relatório gerado em {__import__('datetime').datetime.now().strftime('%d/%m/%Y às %H:%M')} "
        f"• ContaComigo — Seu parceiro financeiro inteligente",
        style('footer_txt', fontSize=7.5, textColor=C_MUTED, alignment=1)
    ))

    # ── Build ─────────────────────────────────────────────────
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_livro_caixa_pdf(user_name: str, lancamentos: list, mes_ano_str: str) -> bytes:
    """
    Gera um PDF detalhado do Livro Caixa (Extrato Consolidado).
    Colunas: Data/Hora, Conta, Descrição, Categoria/Sub, Tipo, Valor.
    """
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4)
    
    # Margens e Frame
    frame = Frame(15*mm, 15*mm, A4[0] - 30*mm, A4[1] - 30*mm, id='normal')
    template = PageTemplate(id='Normal', frames=[frame], onPage=footer_canvas)
    doc.addPageTemplates([template])
    
    elements = []
    styles = getSampleStyleSheet()
    
    # ── Cabeçalho ─────────────────────────────────────────────
    safe_name = (user_name or "Usuário").upper()
    elements.append(Paragraph(f"<b>LIVRO CAIXA CONSOLIDADO</b>", 
                    style('h1', fontSize=18, textColor=C_NAVY, spaceAfter=5)))
    elements.append(Paragraph(f"Cliente: {safe_name}  |  Período: {mes_ano_str}", 
                    style('sub', fontSize=10, textColor=C_MUTED, spaceAfter=20)))

    # ── Resumo Rápido ─────────────────────────────────────────
    total_ent = sum(float(l.valor) for l in lancamentos if not is_expense_type(l.tipo))
    total_sai = sum(abs(float(l.valor)) for l in lancamentos if is_expense_type(l.tipo))
    saldo = total_ent - total_sai

    resumo_data = [
        [Paragraph("<b>Total Entradas</b>", style('r1', textColor=C_MUTED)), 
         Paragraph(f"<b>{fmt_brl(total_ent)}</b>", style('v1', textColor=C_EMERALD, alignment=2))],
        [Paragraph("<b>Total Saídas</b>", style('r2', textColor=C_MUTED)), 
         Paragraph(f"<b>{fmt_brl(total_sai)}</b>", style('v2', textColor=C_RED, alignment=2))],
        [Paragraph("<b>Saldo Líquido</b>", style('r3', textColor=C_NAVY)), 
         Paragraph(f"<b>{fmt_brl(saldo)}</b>", style('v3', textColor=C_INDIGO, alignment=2))]
    ]
    resumo_table = Table(resumo_data, colWidths=[40*mm, 40*mm])
    resumo_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(resumo_table)
    elements.append(Spacer(1, 10*mm))

    # ── Tabela de Lançamentos ─────────────────────────────────
    header = [
        Paragraph('<b>Data/Hora</b>', style('th0', fontSize=8, textColor=C_WHITE)),
        Paragraph('<b>Conta</b>',     style('th1', fontSize=8, textColor=C_WHITE)),
        Paragraph('<b>Descrição</b>', style('th2', fontSize=8, textColor=C_WHITE)),
        Paragraph('<b>Categoria</b>', style('th3', fontSize=8, textColor=C_WHITE)),
        Paragraph('<b>Valor</b>',     style('th4', fontSize=8, textColor=C_WHITE, alignment=2)),
    ]
    
    rows = [header]
    for l in lancamentos:
        dt_str = l.data_transacao.strftime('%d/%m/%y %H:%M') if l.data_transacao else '-'
        conta = (l.conta.nome if l.conta else (l.forma_pagamento or '-'))[:15]
        desc = (l.descricao or '-')[:35]
        
        cat = (l.categoria.nome if l.categoria else 'Outros')
        sub = (f" / {l.subcategoria.nome}" if l.subcategoria else '')
        cat_full = f"{cat}{sub}"[:25]
        
        is_exp = is_expense_type(l.tipo)
        val_f = abs(float(l.valor))
        val_str = fmt_brl(val_f)
        val_para_tabela = Paragraph(f"<b>{'-' if is_exp else '+'}{val_str}</b>", 
                                   style('val', fontSize=8, textColor=(C_RED if is_exp else C_EMERALD), alignment=2))

        rows.append([
            Paragraph(dt_str, style('td0', fontSize=7)),
            Paragraph(conta,  style('td1', fontSize=7)),
            Paragraph(desc,   style('td2', fontSize=7)),
            Paragraph(cat_full, style('td3', fontSize=7)),
            val_para_tabela
        ])

    # ColWidths: total ~180mm
    t = Table(rows, colWidths=[28*mm, 30*mm, 55*mm, 42*mm, 25*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), C_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_BG, C_WHITE]),
        ('GRID', (0, 0), (-1, -1), 0.2, C_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
