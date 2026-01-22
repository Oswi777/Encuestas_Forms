import io
from datetime import datetime
from typing import Optional, List, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analytics import compute_campaign_analytics

# Si tienes utilidades de tiempo local, úsalo; si no, fallback a UTC string
try:
    from app.utils.time import fmt_dt_local
except Exception:  # pragma: no cover
    def fmt_dt_local(dt, tz_name=None):
        if not dt:
            return ""
        return dt.strftime("%Y-%m-%d %H:%M")


# ------------------------- Branding -------------------------
BW_DARK = colors.HexColor("#051729")
BW_BLUE = colors.HexColor("#00386C")
BW_SEA = colors.HexColor("#0E8187")
BW_TECH = colors.HexColor("#2DFAD9")

PAGE_W, PAGE_H = letter
MARGIN_X = 0.70 * inch
MARGIN_TOP = 0.75 * inch
MARGIN_BOTTOM = 0.70 * inch


def _likert_labels(preset: str, lang: str = "es"):
    preset = (preset or "satisfaction").lower()
    dict_ = {
        "satisfaction": {
            "es": ["Muy malo", "Malo", "Regular", "Bueno", "Excelente"],
            "en": ["Very bad", "Bad", "Fair", "Good", "Excellent"],
        },
        "agreement": {
            "es": [
                "Totalmente en desacuerdo",
                "En desacuerdo",
                "Neutral",
                "De acuerdo",
                "Totalmente de acuerdo",
            ],
            "en": ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"],
        },
        "frequency": {
            "es": ["Nunca", "Rara vez", "A veces", "Casi siempre", "Siempre"],
            "en": ["Never", "Rarely", "Sometimes", "Often", "Always"],
        },
    }
    return dict_.get(preset, {}).get(lang) or dict_.get(preset, {}).get("es") or ["1", "2", "3", "4", "5"]


def _safe_text(s) -> str:
    return str(s or "").replace("\n", " ").strip()


def _try_register_fonts():
    """
    Optional: if you later add BW corporate fonts (TTF) under app/static/fonts/,
    you can register them here. For now, fall back to Helvetica safely.
    """
    # Example:
    # pdfmetrics.registerFont(TTFont("Montserrat", "app/static/fonts/Montserrat-Regular.ttf"))
    # pdfmetrics.registerFont(TTFont("Montserrat-Bold", "app/static/fonts/Montserrat-Bold.ttf"))
    pass


def _draw_header(c: canvas.Canvas, title: str, subtitle: str,
                 logo_left_path: Optional[str], logo_right_path: Optional[str],
                 page_no: int):
    """
    Corporate header band + optional logos + title.
    """
    band_h = 0.62 * inch
    c.setFillColor(BW_BLUE)
    c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)

    # Title on band
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN_X, PAGE_H - 0.40 * inch, title)

    c.setFont("Helvetica", 9.5)
    c.setFillColor(colors.white)
    c.drawString(MARGIN_X, PAGE_H - 0.56 * inch, subtitle)

    # Logos (PNG recommended)
    def _draw_logo(path, x, y, h):
        if not path:
            return
        try:
            img = ImageReader(path)
            iw, ih = img.getSize()
            w = (iw / ih) * h
            c.drawImage(img, x, y, width=w, height=h, mask="auto")
        except Exception:
            pass

    logo_h = 0.36 * inch
    y = PAGE_H - 0.49 * inch
    # Left logo near left margin (but not overlapping title too much)
    _draw_logo(logo_left_path, PAGE_W - (2.20 * inch), y, logo_h)
    # Right logo at far right
    _draw_logo(logo_right_path, PAGE_W - (0.70 * inch), y, logo_h)

    # Page number footer (set later too, but keep consistent)
    c.setFillColor(colors.HexColor("#A7B8D1"))


def _draw_footer(c: canvas.Canvas, page_no: int):
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#6B7C96"))
    c.drawRightString(PAGE_W - MARGIN_X, 0.40 * inch, f"Página {page_no}")


def _card(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str, value: str, note: str = ""):
    """
    KPI card.
    """
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#D6DFEA"))
    c.roundRect(x, y, w, h, 10, stroke=1, fill=1)

    # accent bar
    c.setFillColor(BW_SEA)
    c.roundRect(x, y + h - 0.12 * inch, w, 0.12 * inch, 10, stroke=0, fill=1)

    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(x + 0.18 * inch, y + h - 0.30 * inch, _safe_text(title)[:32])

    c.setFont("Helvetica-Bold", 18)
    c.drawString(x + 0.18 * inch, y + 0.35 * inch, _safe_text(value)[:18])

    if note:
        c.setFont("Helvetica", 8.5)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(x + 0.18 * inch, y + 0.18 * inch, _safe_text(note)[:40])


def _chart_png_bar(labels: List[str], values: List[int], title: str) -> bytes:
    fig = plt.figure(figsize=(7.2, 2.6))
    ax = fig.add_subplot(111)

    labels = [str(x) for x in labels]
    values = [int(v) if v is not None else 0 for v in values]

    ax.bar(range(len(labels)), values)

    ax.set_title(title, fontsize=11, fontweight="bold")

    # Formatting
    ax.grid(axis="y", alpha=0.18)
    ax.set_axisbelow(True)

    # Rotate if long labels
    max_len = max((len(x) for x in labels), default=0)
    rot = 0 if max_len <= 10 else 25
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=rot, ha="right" if rot else "center", fontsize=9)

    fig.tight_layout()
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=170)
    plt.close(fig)
    return out.getvalue()


def _chart_png_horizontal(labels: List[str], values: List[int], title: str) -> bytes:
    fig = plt.figure(figsize=(7.2, 2.8))
    ax = fig.add_subplot(111)

    labels = [str(x) for x in labels]
    values = [int(v) if v is not None else 0 for v in values]

    ax.barh(range(len(labels)), values)

    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.grid(axis="x", alpha=0.18)
    ax.set_axisbelow(True)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)

    fig.tight_layout()
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=170)
    plt.close(fig)
    return out.getvalue()


def _draw_png(c: canvas.Canvas, png_bytes: bytes, x: float, y: float, w: float, h: float):
    img = io.BytesIO(png_bytes)
    img.seek(0)
    c.drawImage(ImageReader(img), x, y, width=w, height=h, mask="auto")


def _section_title(c: canvas.Canvas, y: float, title: str) -> float:
    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN_X, y, title)
    # thin line
    c.setStrokeColor(colors.HexColor("#D6DFEA"))
    c.setLineWidth(1)
    c.line(MARGIN_X, y - 0.10 * inch, PAGE_W - MARGIN_X, y - 0.10 * inch)
    return y - 0.28 * inch


def _draw_table(c: canvas.Canvas, y: float, title: str, columns: List[str], rows: List[List[str]],
                col_widths: List[float], max_rows: int = 12) -> float:
    """
    Simple table renderer (no Platypus dependency).
    y is top-left anchor.
    """
    y = _section_title(c, y, title)

    header_h = 0.26 * inch
    row_h = 0.22 * inch
    table_w = sum(col_widths)

    # Header background
    c.setFillColor(colors.HexColor("#EEF3FA"))
    c.rect(MARGIN_X, y - header_h, table_w, header_h, stroke=0, fill=1)

    c.setStrokeColor(colors.HexColor("#D6DFEA"))
    c.rect(MARGIN_X, y - header_h, table_w, header_h, stroke=1, fill=0)

    # Header text
    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 9)

    x = MARGIN_X + 0.06 * inch
    for i, col in enumerate(columns):
        c.drawString(x, y - 0.19 * inch, _safe_text(col)[:40])
        x += col_widths[i]

    y -= header_h

    # Rows
    c.setFont("Helvetica", 8.6)
    for r_i, row in enumerate(rows[:max_rows]):
        y -= row_h
        # Zebra
        if r_i % 2 == 0:
            c.setFillColor(colors.white)
        else:
            c.setFillColor(colors.HexColor("#FAFCFF"))
        c.rect(MARGIN_X, y, table_w, row_h, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#E2EAF4"))
        c.rect(MARGIN_X, y, table_w, row_h, stroke=1, fill=0)

        x = MARGIN_X + 0.06 * inch
        c.setFillColor(colors.HexColor("#102842"))
        for i, cell in enumerate(row):
            c.drawString(x, y + 0.06 * inch, _safe_text(cell)[:52])
            x += col_widths[i]

    return y - 0.22 * inch


def build_campaign_pdf(campaign, shifts=None) -> bytes:
    """
    Professional PDF Export (Executive-ready).
    Requires: reportlab, matplotlib. Works with in-memory images.
    """
    _try_register_fonts()

    analytics = compute_campaign_analytics(campaign)
    totals = analytics.get("totals", {}) or {}

    # Logo paths (PNG recommended)
    # Cambia estas rutas según tu proyecto: ideal en app/static/img/
    # Si no existen, el PDF sale sin logos.
    logo_bw = getattr(campaign, "logo_bw_path", None)  # optional if you added field
    logo_gptw = getattr(campaign, "logo_gptw_path", None)
    # Fallbacks typical locations (you can adjust):
    if not logo_bw:
        logo_bw = "app/static/img/BorgWarner_Logo_Technology_Blue.png"
    if not logo_gptw:
        logo_gptw = "app/static/img/GPTW_Logo.png"

    tz_name = getattr(campaign, "time_zone", None)  # optional
    generated_local = fmt_dt_local(datetime.utcnow(), tz_name)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    page_no = 1

    # ---------------- Page 1 (Executive Summary) ----------------
    _draw_header(
        c,
        title="BorgWarner Encuestas",
        subtitle=f"Campaña: {_safe_text(campaign.name)}",
        logo_left_path=logo_bw,
        logo_right_path=logo_gptw,
        page_no=page_no,
    )

    y = PAGE_H - (0.92 * inch)

    # Campaign meta block
    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN_X, y, "Resumen de campaña")
    y -= 0.22 * inch

    c.setFont("Helvetica", 9.8)
    c.setFillColor(colors.HexColor("#102842"))
    c.drawString(MARGIN_X, y, f"Token: {_safe_text(campaign.token)}")
    y -= 0.18 * inch

    cat = getattr(campaign, "category", "") or (analytics.get("campaign", {}) or {}).get("category", "")
    c.drawString(MARGIN_X, y, f"Categoría: {_safe_text(cat or 'GENERAL')}")
    y -= 0.18 * inch

    start = getattr(campaign, "start_at", None)
    end = getattr(campaign, "end_at", None)
    c.drawString(MARGIN_X, y, f"Ventana: {fmt_dt_local(start, tz_name) or '—'}  a  {fmt_dt_local(end, tz_name) or '—'}")
    y -= 0.18 * inch

    c.setFillColor(colors.HexColor("#526581"))
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN_X, y, f"Generado (hora local): {generated_local}")
    y -= 0.32 * inch

    # KPI cards row
    kpi_h = 1.05 * inch
    gap = 0.18 * inch
    card_w = (PAGE_W - (2 * MARGIN_X) - (3 * gap)) / 4
    x0 = MARGIN_X
    _card(c, x0 + 0*(card_w+gap), y - kpi_h, card_w, kpi_h, "Respuestas", str(totals.get("responses", 0)), "Total en campaña")
    _card(c, x0 + 1*(card_w+gap), y - kpi_h, card_w, kpi_h, "Seguimiento", str(totals.get("followup_opt_in", 0)), "Opt-in de contacto")

    main = analytics.get("special", {}).get("main_likert")
    main_avg = (main or {}).get("avg")
    preset = (main or {}).get("likert_preset") or "satisfaction"
    if main_avg is None:
        avg_txt = "—"
        note = "Sin datos"
    else:
        # translate avg to label
        try:
            a = float(main_avg)
            idx = min(4, max(0, int(round(a)) - 1))
            lab = _likert_labels(preset, "es")[idx]
            avg_txt = f"{a:.2f}"
            note = lab
        except Exception:
            avg_txt = str(main_avg)
            note = ""
    _card(c, x0 + 2*(card_w+gap), y - kpi_h, card_w, kpi_h, "Promedio", avg_txt, note)
    _card(c, x0 + 3*(card_w+gap), y - kpi_h, card_w, kpi_h, "Estado", "Activa" if getattr(campaign, "is_active", False) else "Inactiva", "Auto por horario")

    y -= (kpi_h + 0.35 * inch)

    # Charts: Shift + Area (2 stack)
    # Shift
    by_shift = analytics.get("by_shift") or []
    if by_shift:
        labels = [x[0] for x in by_shift]
        values = [x[1] for x in by_shift]
        try:
            png = _chart_png_bar(labels, values, "Respuestas por turno")
            _draw_png(c, png, MARGIN_X, y - 2.25 * inch, PAGE_W - 2*MARGIN_X, 2.25 * inch)
            y -= 2.50 * inch
        except Exception:
            pass

    # Area
    by_area = analytics.get("by_area") or []
    if by_area:
        labels = [x[0] for x in by_area[:10]]
        values = [x[1] for x in by_area[:10]]
        try:
            png = _chart_png_horizontal(labels, values, "Top 10 áreas por respuestas")
            if y < (2.90 * inch):
                _draw_footer(c, page_no)
                c.showPage()
                page_no += 1
                _draw_header(c, "BorgWarner Encuestas", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
                y = PAGE_H - (0.92 * inch)

            _draw_png(c, png, MARGIN_X, y - 2.55 * inch, PAGE_W - 2*MARGIN_X, 2.55 * inch)
            y -= 2.80 * inch
        except Exception:
            pass

    # Questions sample (first 4)
    y = _section_title(c, y, "Resultados por pregunta (muestra)")
    for q in (analytics.get("questions") or [])[:4]:
        qtext = (q.get("text") or {}).get("es") or (q.get("text") or {}).get("en") or q.get("id", "")
        labels = q.get("labels") or []
        values = q.get("values") or []
        if q.get("type") == "likert":
            preset_q = q.get("likert_preset") or "satisfaction"
            scale = len(labels) or 5
            if all(str(x).isdigit() for x in labels):
                labels = _likert_labels(preset_q, "es")[:scale]

        if y < (2.80 * inch):
            _draw_footer(c, page_no)
            c.showPage()
            page_no += 1
            _draw_header(c, "BW Encuestas Pro — Reporte Ejecutivo", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
            y = PAGE_H - (0.92 * inch)

        try:
            png = _chart_png_bar([str(x) for x in labels], [int(v) for v in values], _safe_text(qtext)[:80])
            _draw_png(c, png, MARGIN_X, y - 2.05 * inch, PAGE_W - 2*MARGIN_X, 2.05 * inch)
            y -= 2.25 * inch
        except Exception:
            pass

    _draw_footer(c, page_no)

    # ---------------- Page 2 (Comments / Follow-ups annex) ----------------
    c.showPage()
    page_no += 1
    _draw_header(c, "BW Encuestas Pro — Anexos", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)

    y = PAGE_H - (0.92 * inch)

    # Comments (top)
    comments = analytics.get("comments") or []  # if your analytics provides it
    # If not provided, keep empty; PDF still renders well.
    if comments:
        rows = []
        for r in comments[:25]:
            rows.append([
                fmt_dt_local(r.get("submitted_at"), tz_name) if isinstance(r, dict) else "",
                _safe_text((r.get("area") if isinstance(r, dict) else "") or "-"),
                _safe_text((r.get("shift") if isinstance(r, dict) else "") or "-"),
                _safe_text((r.get("question") if isinstance(r, dict) else "") or "-")[:34],
                _safe_text((r.get("text") if isinstance(r, dict) else "") or "")[:56],
            ])
        y = _draw_table(
            c, y,
            title="Comentarios (muestra)",
            columns=["Fecha", "Área", "Turno", "Pregunta", "Comentario"],
            rows=rows,
            col_widths=[1.20*inch, 1.00*inch, 0.80*inch, 1.60*inch, 2.70*inch],
            max_rows=12
        )
    else:
        y = _section_title(c, y, "Comentarios")
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(MARGIN_X, y, "No hay comentarios registrados en esta campaña.")
        y -= 0.40 * inch

    # Followups (top)
    followups = analytics.get("followups") or []  # if your analytics provides it
    if followups:
        rows = []
        for r in followups[:25]:
            rows.append([
                fmt_dt_local(r.get("submitted_at"), tz_name) if isinstance(r, dict) else "",
                _safe_text((r.get("name") if isinstance(r, dict) else "") or "-")[:24],
                _safe_text((r.get("employee_no") if isinstance(r, dict) else "") or "-"),
                _safe_text((r.get("area") if isinstance(r, dict) else "") or "-"),
                _safe_text((r.get("shift") if isinstance(r, dict) else "") or "-"),
            ])
        if y < (2.40 * inch):
            _draw_footer(c, page_no)
            c.showPage()
            page_no += 1
            _draw_header(c, "BW Encuestas Pro — Anexos", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
            y = PAGE_H - (0.92 * inch)

        y = _draw_table(
            c, y,
            title="Solicitudes de seguimiento (muestra)",
            columns=["Fecha", "Nombre", "No. Empleado", "Área", "Turno"],
            rows=rows,
            col_widths=[1.20*inch, 1.60*inch, 1.10*inch, 1.50*inch, 1.05*inch],
            max_rows=12
        )
    else:
        y = _section_title(c, y, "Solicitudes de seguimiento")
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(MARGIN_X, y, "No hay solicitudes de contacto (opt-in) registradas.")
        y -= 0.40 * inch

    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#6B7C96"))
    c.drawString(MARGIN_X, 0.55 * inch, "Nota: Para análisis detallado, utilice la exportación CSV desde el panel de administrador.")
    _draw_footer(c, page_no)

    c.save()
    return buf.getvalue()
