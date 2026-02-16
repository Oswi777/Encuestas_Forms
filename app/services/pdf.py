import io
from datetime import datetime
from typing import Optional, List

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analytics import compute_campaign_analytics

try:
    from app.utils.time import fmt_dt_local
except Exception:  # pragma: no cover
    def fmt_dt_local(dt, tz_name=None, fmt="%Y-%m-%d %H:%M"):
        if not dt:
            return ""
        return dt.strftime(fmt)


# ------------------------- Branding -------------------------
BW_DARK = colors.HexColor("#051729")
BW_BLUE = colors.HexColor("#00386C")
BW_SEA  = colors.HexColor("#0E8187")
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


def _pct(n: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (float(n) / float(total)) * 100.0


def _draw_png(c: canvas.Canvas, png_bytes: bytes, x: float, y: float, w: float, h: float):
    img = io.BytesIO(png_bytes)
    img.seek(0)
    c.drawImage(ImageReader(img), x, y, width=w, height=h, mask="auto")


def _draw_header(c: canvas.Canvas, title: str, subtitle: str,
                 logo_left_path: Optional[str], logo_right_path: Optional[str],
                 page_no: int):
    band_h = 0.62 * inch
    c.setFillColor(BW_BLUE)
    c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN_X, PAGE_H - 0.40 * inch, title)

    c.setFont("Helvetica", 9.5)
    c.drawString(MARGIN_X, PAGE_H - 0.56 * inch, subtitle)

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
    _draw_logo(logo_left_path, PAGE_W - (2.20 * inch), y, logo_h)
    _draw_logo(logo_right_path, PAGE_W - (0.70 * inch), y, logo_h)


def _draw_footer(c: canvas.Canvas, page_no: int):
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#6B7C96"))
    c.drawRightString(PAGE_W - MARGIN_X, 0.40 * inch, f"Página {page_no}")


def _section_title(c: canvas.Canvas, y: float, title: str) -> float:
    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN_X, y, title)
    c.setStrokeColor(colors.HexColor("#D6DFEA"))
    c.setLineWidth(1)
    c.line(MARGIN_X, y - 0.10 * inch, PAGE_W - MARGIN_X, y - 0.10 * inch)
    return y - 0.28 * inch


def _card(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str, value: str, note: str = ""):
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#D6DFEA"))
    c.roundRect(x, y, w, h, 10, stroke=1, fill=1)

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
        c.drawString(x + 0.18 * inch, y + 0.18 * inch, _safe_text(note)[:45])


# ---------------------- Charts (bonitos + % + conteo) ----------------------

def _style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_alpha(0.35)
    ax.spines["bottom"].set_alpha(0.35)
    ax.grid(axis="y", alpha=0.18, linewidth=0.8)
    ax.set_axisbelow(True)


def _chart_png_bar(labels: List[str], values: List[int], title: str, subtitle: str = "") -> bytes:
    labels = [str(x) for x in labels]
    values = [int(v) if v is not None else 0 for v in values]
    total = sum(values)

    fig = plt.figure(figsize=(7.2, 2.75), dpi=180)
    ax = fig.add_subplot(111)

    bar_color = "#00386C"  # BW_BLUE
    bars = ax.bar(range(len(labels)), values, color=bar_color, alpha=0.92)

    ax.set_title(title or "", fontsize=11.5, fontweight="bold", pad=10)
    if subtitle:
        ax.text(0.0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, alpha=0.75)

    _style_axes(ax)

    max_len = max((len(x) for x in labels), default=0)
    rot = 0 if max_len <= 12 and len(labels) <= 6 else 22
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=rot, ha="right" if rot else "center", fontsize=9)

    ax.set_ylabel("Respuestas", fontsize=9)

    ymax = max(values) if values else 0
    ax.set_ylim(0, max(1, int(ymax * 1.25)))

    for rect, v in zip(bars, values):
        if total > 0:
            p = _pct(v, total)
            lab = f"{v} ({p:.1f}%)"
        else:
            lab = f"{v}"
        ax.text(
            rect.get_x() + rect.get_width() / 2.0,
            rect.get_height() + (0.03 * ax.get_ylim()[1]),
            lab,
            ha="center",
            va="bottom",
            fontsize=8.5,
            color="#0B1E33",
        )

    fig.tight_layout()
    out = io.BytesIO()
    fig.savefig(out, format="png", transparent=False)
    plt.close(fig)
    return out.getvalue()


def _chart_png_horizontal(labels: List[str], values: List[int], title: str, subtitle: str = "") -> bytes:
    labels = [str(x) for x in labels]
    values = [int(v) if v is not None else 0 for v in values]
    total = sum(values)

    h = 2.6 + (0.18 * min(len(labels), 12))
    fig = plt.figure(figsize=(7.2, h), dpi=180)
    ax = fig.add_subplot(111)

    bar_color = "#0E8187"  # BW_SEA
    bars = ax.barh(range(len(labels)), values, color=bar_color, alpha=0.92)

    ax.set_title(title or "", fontsize=11.5, fontweight="bold", pad=10)
    if subtitle:
        ax.text(0.0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, alpha=0.75)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_alpha(0.35)
    ax.spines["bottom"].set_alpha(0.35)
    ax.grid(axis="x", alpha=0.18, linewidth=0.8)
    ax.set_axisbelow(True)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)

    ax.set_xlabel("Respuestas", fontsize=9)

    xmax = max(values) if values else 0
    ax.set_xlim(0, max(1, int(xmax * 1.30)))

    for rect, v in zip(bars, values):
        if total > 0:
            p = _pct(v, total)
            lab = f"{v} ({p:.1f}%)"
        else:
            lab = f"{v}"
        ax.text(
            rect.get_width() + (0.02 * ax.get_xlim()[1]),
            rect.get_y() + rect.get_height() / 2.0,
            lab,
            va="center",
            ha="left",
            fontsize=8.5,
            color="#0B1E33",
        )

    fig.tight_layout()
    out = io.BytesIO()
    fig.savefig(out, format="png", transparent=False)
    plt.close(fig)
    return out.getvalue()


# ---------------------- Tables (paginadas) ----------------------

def _draw_table_page(c: canvas.Canvas, y: float, title: str, columns: List[str], rows: List[List[str]],
                     col_widths: List[float], max_rows: int = 18) -> float:
    """
    Tabla simple sin Platypus. Devuelve y final.
    """
    y = _section_title(c, y, title)

    header_h = 0.26 * inch
    row_h = 0.22 * inch
    table_w = sum(col_widths)

    c.setFillColor(colors.HexColor("#EEF3FA"))
    c.rect(MARGIN_X, y - header_h, table_w, header_h, stroke=0, fill=1)

    c.setStrokeColor(colors.HexColor("#D6DFEA"))
    c.rect(MARGIN_X, y - header_h, table_w, header_h, stroke=1, fill=0)

    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 9)

    x = MARGIN_X + 0.06 * inch
    for i, col in enumerate(columns):
        c.drawString(x, y - 0.19 * inch, _safe_text(col)[:40])
        x += col_widths[i]

    y -= header_h
    c.setFont("Helvetica", 8.6)

    for r_i, row in enumerate(rows[:max_rows]):
        y -= row_h
        c.setFillColor(colors.white if r_i % 2 == 0 else colors.HexColor("#FAFCFF"))
        c.rect(MARGIN_X, y, table_w, row_h, stroke=0, fill=1)

        c.setStrokeColor(colors.HexColor("#E2EAF4"))
        c.rect(MARGIN_X, y, table_w, row_h, stroke=1, fill=0)

        x = MARGIN_X + 0.06 * inch
        c.setFillColor(colors.HexColor("#102842"))
        for i, cell in enumerate(row):
            c.drawString(x, y + 0.06 * inch, _safe_text(cell)[:120])
            x += col_widths[i]

    return y - 0.22 * inch


def _paginate_rows(rows: List[List[str]], per_page: int) -> List[List[List[str]]]:
    pages = []
    for i in range(0, len(rows), per_page):
        pages.append(rows[i:i + per_page])
    return pages


# ---------------------- Main PDF ----------------------

def build_campaign_pdf(campaign, shifts=None) -> bytes:
    analytics = compute_campaign_analytics(campaign)
    totals = analytics.get("totals", {}) or {}

    # Ajusta rutas según tu repo (si no existen, no truena)
    logo_bw = "app/static/img/BorgWarner_Logo_Technology_Blue.png"
    logo_gptw = "app/static/img/GPTW_Logo.png"

    tz_name = getattr(campaign, "time_zone", None)
    generated_local = fmt_dt_local(datetime.utcnow(), tz_name)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    page_no = 1

    # ---------------- Page 1: Executive Summary ----------------
    _draw_header(
        c,
        title="BorgWarner Encuestas",
        subtitle=f"Campaña: {_safe_text(campaign.name)}",
        logo_left_path=logo_bw,
        logo_right_path=logo_gptw,
        page_no=page_no,
    )

    y = PAGE_H - (0.92 * inch)

    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN_X, y, "Resumen de campaña")
    y -= 0.22 * inch

    c.setFont("Helvetica", 9.8)
    c.setFillColor(colors.HexColor("#102842"))
    c.drawString(MARGIN_X, y, f"Token: {_safe_text(getattr(campaign, 'token', ''))}")
    y -= 0.18 * inch

    cat = (analytics.get("campaign", {}) or {}).get("category") or getattr(campaign, "category", "") or "GENERAL"
    c.drawString(MARGIN_X, y, f"Categoría: {_safe_text(cat)}")
    y -= 0.18 * inch

    start = getattr(campaign, "start_at", None)
    end = getattr(campaign, "end_at", None)
    c.drawString(MARGIN_X, y, f"Ventana: {fmt_dt_local(start, tz_name) or '—'}  a  {fmt_dt_local(end, tz_name) or '—'}")
    y -= 0.18 * inch

    c.setFillColor(colors.HexColor("#526581"))
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN_X, y, f"Generado (hora local): {generated_local}")
    y -= 0.32 * inch

    # KPI cards
    kpi_h = 1.05 * inch
    gap = 0.18 * inch
    card_w = (PAGE_W - (2 * MARGIN_X) - (3 * gap)) / 4
    x0 = MARGIN_X

    _card(c, x0 + 0*(card_w+gap), y - kpi_h, card_w, kpi_h, "Respuestas", str(totals.get("responses", 0)), "Total en campaña")
    _card(c, x0 + 1*(card_w+gap), y - kpi_h, card_w, kpi_h, "Seguimiento", str(totals.get("followup_opt_in", 0)), "Opt-in de contacto")

    main = (analytics.get("special", {}) or {}).get("main_likert") or {}
    main_avg = main.get("avg")
    preset = (main.get("likert_preset") or "satisfaction")

    if main_avg is None:
        avg_txt, note = "—", "Sin datos"
    else:
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
    _card(c, x0 + 3*(card_w+gap), y - kpi_h, card_w, kpi_h, "Estado",
          "Activa" if getattr(campaign, "is_active", False) else "Inactiva", "Auto por horario")

    y -= (kpi_h + 0.35 * inch)

    # (Opcional) charts por turno / área en portada
    by_shift = analytics.get("by_shift") or []
    if by_shift:
        labels = [x[0] for x in by_shift]
        values = [x[1] for x in by_shift]
        png = _chart_png_bar(labels, values, "Respuestas por turno", subtitle=f"Total: {sum(values)}")
        _draw_png(c, png, MARGIN_X, y - 2.25 * inch, PAGE_W - 2*MARGIN_X, 2.25 * inch)
        y -= 2.55 * inch

    by_area = analytics.get("by_area") or []
    if by_area:
        labels = [x[0] for x in by_area[:10]]
        values = [x[1] for x in by_area[:10]]
        if y < (3.20 * inch):
            _draw_footer(c, page_no)
            c.showPage()
            page_no += 1
            _draw_header(c, "BorgWarner Encuestas", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
            y = PAGE_H - (0.92 * inch)

        png = _chart_png_horizontal(labels, values, "Top 10 áreas por respuestas", subtitle=f"Total: {sum(values)}")
        _draw_png(c, png, MARGIN_X, y - 2.65 * inch, PAGE_W - 2*MARGIN_X, 2.65 * inch)
        y -= 2.95 * inch

    # Nota breve
    if y < (1.45 * inch):
        _draw_footer(c, page_no)
        c.showPage()
        page_no += 1
        _draw_header(c, "BorgWarner Encuestas", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
        y = PAGE_H - (0.92 * inch)

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#526581"))
    c.drawString(MARGIN_X, y, "Este reporte incluye resultados por pregunta (conteo y porcentaje) y anexos de comentarios/seguimiento.")
    y -= 0.25 * inch

    _draw_footer(c, page_no)
    c.showPage()
    page_no += 1

    # ---------------- Section: Todas las preguntas ----------------
    _draw_header(c, "BW Encuestas Pro — Resultados", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
    y = PAGE_H - (0.92 * inch)

    y = _section_title(c, y, "Resultados por pregunta (todas)")
    y -= 0.10 * inch

    questions = analytics.get("questions") or []
    for idx, q in enumerate(questions, start=1):
        qid = q.get("id", "")
        qtype = (q.get("type") or "").lower()
        qtext = (q.get("text") or {}).get("es") or (q.get("text") or {}).get("en") or qid
        qtext = _safe_text(qtext)

        labels = q.get("labels") or []
        values = q.get("values") or []

        # Fix likert numeric labels if needed
        if qtype == "likert":
            preset_q = q.get("likert_preset") or "satisfaction"
            scale = len(labels) or 5
            if all(str(x).isdigit() for x in labels):
                labels = _likert_labels(preset_q, "es")[:scale]

        # Title line
        if y < (3.10 * inch):
            _draw_footer(c, page_no)
            c.showPage()
            page_no += 1
            _draw_header(c, "BW Encuestas Pro — Resultados", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
            y = PAGE_H - (0.92 * inch)

        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(colors.HexColor("#0B1E33"))
        c.drawString(MARGIN_X, y, f"{idx}. {qtext[:110]}")
        y -= 0.18 * inch

        total_q = sum(int(v) for v in values) if values else 0
        subtitle = f"Total respuestas de esta pregunta: {total_q}" if total_q else "Sin respuestas registradas"

        # Si es texto: no graficar barras, solo mostrar indicador
        if qtype in ("text", "textarea", "comment"):
            c.setFont("Helvetica", 9.2)
            c.setFillColor(colors.HexColor("#526581"))
            c.drawString(MARGIN_X, y, f"Tipo: Texto. Respuestas capturadas: {total_q}")
            y -= 0.28 * inch
            continue

        # Top 10 si hay demasiadas opciones
        if qtype == "single" and len(labels) > 12:
            pairs = list(zip(labels, values))
            pairs.sort(key=lambda x: int(x[1]), reverse=True)
            pairs = pairs[:10]
            labels = [p[0] for p in pairs]
            values = [p[1] for p in pairs]

        # Decide tipo de chart
        use_horizontal = (len(labels) > 7) or any(len(str(x)) > 18 for x in labels)

        if use_horizontal:
            png = _chart_png_horizontal([str(x) for x in labels], [int(v) for v in values], "", subtitle=subtitle)
            chart_h = 2.45 * inch + (0.10 * inch * min(len(labels), 10))
        else:
            png = _chart_png_bar([str(x) for x in labels], [int(v) for v in values], "", subtitle=subtitle)
            chart_h = 2.10 * inch

        if y < (chart_h + 1.10 * inch):
            _draw_footer(c, page_no)
            c.showPage()
            page_no += 1
            _draw_header(c, "BW Encuestas Pro — Resultados", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
            y = PAGE_H - (0.92 * inch)

        _draw_png(c, png, MARGIN_X, y - chart_h, PAGE_W - 2*MARGIN_X, chart_h)
        y -= (chart_h + 0.35 * inch)

    _draw_footer(c, page_no)
    c.showPage()
    page_no += 1

    # ---------------- Anexos: Comentarios (TODOS) ----------------
    _draw_header(c, "BW Encuestas Pro — Anexos", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
    y = PAGE_H - (0.92 * inch)

    comments = analytics.get("comments") or []
    if not comments:
        y = _section_title(c, y, "Comentarios")
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(MARGIN_X, y, "No hay comentarios registrados en esta campaña.")
        y -= 0.40 * inch
        _draw_footer(c, page_no)
    else:
        rows = []
        for r in comments:
            rows.append([
                fmt_dt_local(r.get("submitted_at"), tz_name),
                _safe_text(r.get("area") or "-"),
                _safe_text(r.get("shift") or "-"),
                _safe_text(r.get("question") or "-"),
                _safe_text(r.get("text") or ""),
            ])

        pages = _paginate_rows(rows, per_page=18)
        for pi, page_rows in enumerate(pages, start=1):
            if pi > 1:
                _draw_footer(c, page_no)
                c.showPage()
                page_no += 1
                _draw_header(c, "BW Encuestas Pro — Anexos", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
                y = PAGE_H - (0.92 * inch)

            title = f"Comentarios (página {pi}/{len(pages)})"
            y = _draw_table_page(
                c, y,
                title=title,
                columns=["Fecha", "Área", "Turno", "Pregunta", "Comentario"],
                rows=page_rows,
                col_widths=[1.25*inch, 1.05*inch, 0.85*inch, 1.55*inch, 2.80*inch],
                max_rows=18
            )

        _draw_footer(c, page_no)

    c.showPage()
    page_no += 1

    # ---------------- Anexos: Followups (TODOS) ----------------
    _draw_header(c, "BW Encuestas Pro — Anexos", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
    y = PAGE_H - (0.92 * inch)

    followups = analytics.get("followups") or []
    if not followups:
        y = _section_title(c, y, "Solicitudes de seguimiento")
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(MARGIN_X, y, "No hay solicitudes de contacto (opt-in) registradas.")
        y -= 0.40 * inch
        _draw_footer(c, page_no)
    else:
        rows = []
        for r in followups:
            rows.append([
                fmt_dt_local(r.get("submitted_at"), tz_name),
                _safe_text(r.get("name") or "-"),
                _safe_text(r.get("employee_no") or "-"),
                _safe_text(r.get("phone") or "-"),
                _safe_text(r.get("area") or "-"),
                _safe_text(r.get("shift") or "-"),
            ])

        pages = _paginate_rows(rows, per_page=18)
        for pi, page_rows in enumerate(pages, start=1):
            if pi > 1:
                _draw_footer(c, page_no)
                c.showPage()
                page_no += 1
                _draw_header(c, "BW Encuestas Pro — Anexos", f"Campaña: {_safe_text(campaign.name)}", logo_bw, logo_gptw, page_no)
                y = PAGE_H - (0.92 * inch)

            title = f"Solicitudes de seguimiento (página {pi}/{len(pages)})"
            y = _draw_table_page(
                c, y,
                title=title,
                columns=["Fecha", "Nombre", "No. Empleado", "Teléfono", "Área", "Turno"],
                rows=page_rows,
                col_widths=[1.15*inch, 1.45*inch, 1.05*inch, 1.10*inch, 1.25*inch, 1.00*inch],
                max_rows=18
            )

        c.setFont("Helvetica", 8.5)
        c.setFillColor(colors.HexColor("#6B7C96"))
        c.drawString(MARGIN_X, 0.55 * inch, "Nota: Para análisis detallado, utilice la exportación CSV desde el panel de administrador.")
        _draw_footer(c, page_no)

    c.save()
    return buf.getvalue()
