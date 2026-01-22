import io
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ..models import Response, Area
from ..analytics.service import compute_campaign_analytics


def build_campaign_pdf(campaign, shifts=None) -> bytes:
    shifts = shifts or []
    analytics = compute_campaign_analytics(campaign)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    # Cover
    c.setFillColor(colors.HexColor('#204080'))
    c.rect(0, H-1.4*inch, W, 1.4*inch, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 20)
    c.drawString(0.75*inch, H-0.85*inch, 'BW Encuestas Pro')
    c.setFont('Helvetica', 12)
    c.drawString(0.75*inch, H-1.15*inch, 'Reporte de campaña')

    c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(0.75*inch, H-2.2*inch, campaign.name)
    c.setFont('Helvetica', 10)
    c.drawString(0.75*inch, H-2.5*inch, f'Generado: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}')

    # Summary cards
    y = H-3.2*inch
    c.setFont('Helvetica-Bold', 12)
    c.drawString(0.75*inch, y, 'Resumen ejecutivo')
    y -= 0.25*inch

    def card(x, y, title, value):
        c.setStrokeColor(colors.HexColor('#d0d7de'))
        c.setFillColor(colors.whitesmoke)
        c.rect(x, y-0.55*inch, 2.3*inch, 0.55*inch, fill=1, stroke=1)
        c.setFillColor(colors.HexColor('#111827'))
        c.setFont('Helvetica', 9)
        c.drawString(x+0.15*inch, y-0.2*inch, title)
        c.setFont('Helvetica-Bold', 16)
        c.drawString(x+0.15*inch, y-0.45*inch, str(value))

    card(0.75*inch, y, 'Respuestas', analytics['total_responses'])
    card(3.25*inch, y, 'Opt-in seguimiento', analytics['followup_optin'])
    card(5.75*inch, y, 'Campaña ID', campaign.id)

    # Charts page
    c.showPage()
    c.setFont('Helvetica-Bold', 14)
    c.drawString(0.75*inch, H-0.9*inch, 'Resultados')

    # Chart 1: responses by day
    series = analytics.get('series_by_day') or {}
    if series:
        xs = list(series.keys())
        ys = list(series.values())
        fig = plt.figure(figsize=(7.5, 2.5), dpi=120)
        plt.plot(xs, ys)
        plt.xticks(rotation=45, ha='right', fontsize=7)
        plt.tight_layout()
        img1 = io.BytesIO()
        fig.savefig(img1, format='png')
        plt.close(fig)
        img1.seek(0)
        c.drawImage(img1, 0.75*inch, H-3.1*inch, width=7.0*inch, height=2.0*inch, mask='auto')
        c.setFont('Helvetica', 9)
        c.drawString(0.75*inch, H-3.25*inch, 'Respuestas por día')

    # Chart 2: by area
    by_area = analytics.get('by_area') or {}
    if by_area:
        labels = list(by_area.keys())[:10]
        values = [by_area[k] for k in labels]
        fig = plt.figure(figsize=(7.5, 3.0), dpi=120)
        plt.bar(labels, values)
        plt.xticks(rotation=45, ha='right', fontsize=7)
        plt.tight_layout()
        img2 = io.BytesIO()
        fig.savefig(img2, format='png')
        plt.close(fig)
        img2.seek(0)
        c.drawImage(img2, 0.75*inch, H-6.4*inch, width=7.0*inch, height=2.4*inch, mask='auto')
        c.setFont('Helvetica', 9)
        c.drawString(0.75*inch, H-6.55*inch, 'Top Áreas (máx 10)')

    # Detailed question breakdown (text)
    c.showPage()
    c.setFont('Helvetica-Bold', 14)
    c.drawString(0.75*inch, H-0.9*inch, 'Detalle por pregunta (Top respuestas)')
    y = H-1.3*inch
    c.setFont('Helvetica', 9)
    for q in analytics.get('questions', [])[:20]:
        title = q.get('title', {}).get('es') or q.get('id')
        c.setFont('Helvetica-Bold', 10)
        c.drawString(0.75*inch, y, f"{q.get('id')}: {title}")
        y -= 0.18*inch
        c.setFont('Helvetica', 9)
        for ans, cnt in list((q.get('counts') or {}).items())[:5]:
            c.drawString(0.95*inch, y, f"- {ans}: {cnt}")
            y -= 0.16*inch
            if y < 1.0*inch:
                c.showPage()
                y = H-1.0*inch
        y -= 0.12*inch
        if y < 1.0*inch:
            c.showPage()
            y = H-1.0*inch

    c.save()
    return buf.getvalue()
