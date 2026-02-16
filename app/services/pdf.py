import io
from datetime import datetime
from typing import Optional, List, Tuple

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
BW_SEA = colors.HexColor("#0E8187")
BW_TECH = colors.HexColor("#2DFAD9")

PAGE_W, PAGE_H = letter
MARGIN_X = 0.70 * inch
MARGIN_TOP = 0.85 * inch
MARGIN_BOTTOM = 0.70 * inch


def _safe_text(s) -> str:
    return str(s or "").replace("\n", " ").strip()


def _wrap_lines(text: str, max_chars: int) -> List[str]:
    """
    Wrap simple (char-based) para no depender de medidas de font.
    Suficiente para reportes.
    """
    text = _safe_text(text)
    if not text:
        return []
    words = text.split()
    lines = []
    line = ""
    for w in words:
        if not line:
            line = w
            continue
        if len(line) + 1 + len(w) <= max_chars:
            line += " " + w
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _draw_logo_safe(c: canvas.Canvas, path: Optional[str], x: float, y: float, h: float):
    if not path:
        return
    try:
        img = ImageReader(path)  # PNG/JPG recommended
        iw, ih = img.getSize()
        w = (iw / ih) * h
        c.drawImage(img, x, y, width=w, height=h, mask="auto")
    except Exception:
        # si es SVG o no existe, simplemente no dibuja
        return


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

    logo_h = 0.36 * inch
    y = PAGE_H - 0.49 * inch

    # logos to the right (two slots)
    _draw_logo_safe(c, logo_left_path, PAGE_W - (2.10 * inch), y, logo_h)
    _draw_logo_safe(c, logo_right_path, PAGE_W - (0.85 * inch), y, logo_h)


def _draw_footer(c: canvas.Canvas, page_no: int):
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#6B7C96"))
    c.drawString(MARGIN_X, 0.45 * inch, "BW — Saltillo")
    c.drawRightString(PAGE_W - MARGIN_X, 0.45 * inch, f"Página {page_no}")


def _new_page(c: canvas.Canvas, page_no: int,
              hdr_title: str, hdr_sub: str,
              logo_bw: Optional[str], logo_gptw: Optional[str]) -> Tuple[int, float]:
    _draw_footer(c, page_no)
    c.showPage()
    page_no += 1
    _draw_header(c, hdr_title, hdr_sub, logo_bw, logo_gptw, page_no)
    y = PAGE_H - (0.92 * inch)
    return page_no, y


def _ensure_space(c: canvas.Canvas, y: float, needed: float,
                  page_no: int, hdr_title: str, hdr_sub: str,
                  logo_bw: Optional[str], logo_gptw: Optional[str]) -> Tuple[int, float]:
    if y - needed < (MARGIN_BOTTOM + 0.45 * inch):
        return _new_page(c, page_no, hdr_title, hdr_sub, logo_bw, logo_gptw)
    return page_no, y


def _section_title(c: canvas.Canvas, y: float, title: str) -> float:
    c.setFillColor(colors.HexColor("#0B1E33"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN_X, y, title)
    c.setStrokeColor(colors.HexColor("#D6DFEA"))
    c.setLineWidth(1)
    c.line(MARGIN_X, y - 0.10 * inch, PAGE_W - MARGIN_X, y - 0.10 * inch)
    return y - 0.30 * inch


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
        c.drawString(x + 0.18 * inch, y + 0.18 * inch, _safe_text(note)[:55])


def _chart_png_bar(labels: List[str], values: List[int], title: str) -> bytes:
    fig = plt.figure(figsize=(7.2, 2.6))
    ax = fig.add_subplot(111)

    labels = [str(x) for x in labels]
    values = [int(v) if v is not None else 0 for v in values]

    ax.bar(range(len(labels)), values)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.18)
    ax.set_axisbelow(True)

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


def _draw_kv(c: canvas.Canvas, x: float, y: float, k: str, v: str):
    c.setFont("Helvetica-Bold", 9.2)
    c.setFillColor(colors.HexColor("#0B1E33"))
    c.drawString(x, y, _safe_text(k))
    c.setFont("Helvetica", 9.2)
    c.setFillColor(colors.HexColor("#102842"))
    c.drawString(x + 1.10 * inch, y, _safe_text(v))


def _draw_table_simple(c: canvas.Canvas, y: float, columns: List[str], rows: List[List[str]],
                       col_widths: List[float]) -> float:
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
    for r_i, row in enumerate(rows):
        y -= row_h
        c.setFillColor(colors.white if r_i % 2 == 0 else colors.HexColor("#FAFCFF"))
        c.rect(MARGIN_X, y, table_w, row_h, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#E2EAF4"))
        c.rect(MARGIN_X, y, table_w, row_h, stroke=1, fill=0)

        x = MARGIN_X + 0.06 * inch
        c.setFillColor(colors.HexColor("#102842"))
        for i, cell in enumerate(row):
            c.drawString(x, y + 0.06 * inch, _safe_text(cell)[:80])
            x += col_widths[i]

    return y - 0.20 * inch


def _question_title(q: dict, lang: str = "es") -> str:
    qtext = q.get("text") or {}
    if isinstance(qtext, dict):
        return qtext.get(lang) or qtext.get("es") or qtext.get("en") or q.get("id", "")
    return str(qtext or q.get("id", ""))


def build_campaign_pdf(campaign, shifts=None) -> bytes:
    """
    PDF profesional:
      - Resumen ejecutivo
      - TODAS las preguntas: gráfica + tabla conteos/% (si aplica)
      - TODOS los comentarios (texto)
      - TODOS los followups (opt-in)
    """
    analytics = compute_campaign_analytics(campaign)
    totals = analytics.get("totals", {}) or {}

    # Logos (PNG recomendado; SVG no lo dibuja ReportLab)
    logo_bw = "app/static/img/BorgWarner_Logo_Technology_Blue.png"
    logo_gptw = "app/static/img/GPTW_Logo.png"

    tz_name = getattr(campaign, "time_zone", None)
    generated_local = fmt_dt_local(datetime.utcnow(), tz_name)

    hdr_title = "BW Encuestas Pro — Reporte"
    hdr_sub = f"Campaña: {_safe_text(getattr(campaign, 'name', ''))}"

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    page_no = 1
    _draw_header(c, hdr_title, hdr_sub, logo_bw, logo_gptw, page_no)
    y = PAGE_H - (0.92 * inch)

    # ---------------- Page: Executive Summary ----------------
    y = _section_title(c, y, "Resumen ejecutivo")

    c.setFont("Helvetica", 9.5)
    c.setFillColor(colors.HexColor("#102842"))
    _draw_kv(c, MARGIN_X, y, "Token:", _safe_text(getattr(campaign, "token", "")))
    y -= 0.18 * inch

    cat = (analytics.get("campaign", {}) or {}).get("category", "") or getattr(campaign, "category", "") or "GENERAL"
    _draw_kv(c, MARGIN_X, y, "Categoría:", _safe_text(cat))
    y -= 0.18 * inch

    start = getattr(campaign, "start_at", None)
    end = getattr(campaign, "end_at", None)
    _draw_kv(c, MARGIN_X, y, "Ventana:", f"{fmt_dt_local(start, tz_name) or '—'} a {fmt_dt_local(end, tz_name) or '—'}")
    y -= 0.18 * inch

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#526581"))
    c.drawString(MARGIN_X, y, f"Generado (hora local): {generated_local}")
    y -= 0.30 * inch

    # KPI cards
    kpi_h = 1.05 * inch
    gap = 0.18 * inch
    card_w = (PAGE_W - (2 * MARGIN_X) - (3 * gap)) / 4
    x0 = MARGIN_X

    main = (analytics.get("special") or {}).get("main_likert") or {}
    main_avg = main.get("avg")
    avg_txt = "—" if main_avg is None else f"{float(main_avg):.2f}"

    _card(c, x0 + 0*(card_w+gap), y - kpi_h, card_w, kpi_h, "Respuestas", str(totals.get("responses", 0)), "Total")
    _card(c, x0 + 1*(card_w+gap), y - kpi_h, card_w, kpi_h, "Seguimiento", str(totals.get("followup_opt_in", 0)), "Opt-in")
    _card(c, x0 + 2*(card_w+gap), y - kpi_h, card_w, kpi_h, "Promedio", avg_txt, "Pregunta principal")
    _card(c, x0 + 3*(card_w+gap), y - kpi_h, card_w, kpi_h, "Estado", "Activa" if getattr(campaign, "is_active", False) else "Inactiva", "")

    y -= (kpi_h + 0.32 * inch)

    # Charts shift + area
    by_shift = analytics.get("by_shift") or []
    if by_shift:
        labels = [x[0] for x in by_shift]
        values = [x[1] for x in by_shift]
        page_no, y = _ensure_space(c, y, needed=2.55 * inch, page_no=page_no,
                                  hdr_title=hdr_title, hdr_sub=hdr_sub, logo_bw=logo_bw, logo_gptw=logo_gptw)
        png = _chart_png_bar(labels, values, "Respuestas por turno")
        _draw_png(c, png, MARGIN_X, y - 2.25 * inch, PAGE_W - 2*MARGIN_X, 2.25 * inch)
        y -= 2.50 * inch

    by_area = analytics.get("by_area") or []
    if by_area:
        labels = [x[0] for x in by_area[:10]]
        values = [x[1] for x in by_area[:10]]
        page_no, y = _ensure_space(c, y, needed=2.85 * inch, page_no=page_no,
                                  hdr_title=hdr_title, hdr_sub=hdr_sub, logo_bw=logo_bw, logo_gptw=logo_gptw)
        png = _chart_png_horizontal(labels, values, "Top 10 áreas por respuestas")
        _draw_png(c, png, MARGIN_X, y - 2.55 * inch, PAGE_W - 2*MARGIN_X, 2.55 * inch)
        y -= 2.80 * inch

    # ---------------- All questions ----------------
    page_no, y = _new_page(c, page_no, hdr_title, hdr_sub, logo_bw, logo_gptw)
    y = _section_title(c, y, "Resultados por pregunta (todas)")

    questions = analytics.get("questions") or []
    # default language from campaign snapshot if you want; for now ES
    lang = "es"

    for idx, q in enumerate(questions, start=1):
        qtype = (q.get("type") or "").lower()
        q_title = _question_title(q, lang=lang)

        # Compute block height rough:
        # - title (0.35in) + chart (2.15in for likert/single) + table (~0.9in)
        # For text questions we don't chart (only show "filled") and rely on comments section.
        if qtype in ("likert", "single"):
            needed = 0.40*inch + 2.25*inch + 1.30*inch
        else:
            needed = 0.65*inch

        page_no, y = _ensure_space(c, y, needed=needed, page_no=page_no,
                                  hdr_title=hdr_title, hdr_sub=hdr_sub, logo_bw=logo_bw, logo_gptw=logo_gptw)

        # question header
        c.setFillColor(colors.HexColor("#0B1E33"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGIN_X, y, f"{idx}. {_safe_text(q_title)[:110]}")
        y -= 0.20 * inch

        total_n = int(q.get("total_n") or 0)
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(MARGIN_X, y, f"Total respuestas válidas: {total_n}")
        y -= 0.18 * inch

        if qtype in ("likert", "single"):
            labels = q.get("labels") or []
            values = q.get("values") or []

            # chart
            if qtype == "single":
                # reduce: show top 10
                pairs = list(zip(labels, values))
                pairs = sorted(pairs, key=lambda x: (-int(x[1] or 0), str(x[0])))
                pairs = pairs[:10]
                clabs = [p[0] for p in pairs]
                cvals = [p[1] for p in pairs]
                png = _chart_png_horizontal(clabs, cvals, "Distribución (Top)")
            else:
                png = _chart_png_bar(labels, values, "Distribución")

            _draw_png(c, png, MARGIN_X, y - 2.10 * inch, PAGE_W - 2*MARGIN_X, 2.10 * inch)
            y -= 2.25 * inch

            # table counts/% (all labels)
            counts = q.get("counts") or {}
            perc = q.get("percentages") or {}

            rows = []
            for lab in labels:
                rows.append([str(lab), str(int(counts.get(lab, 0))), f"{float(perc.get(lab, 0.0)):.1f}%"])

            # if many rows, split pages
            # each row ~0.22in; header+spacing ~0.35in
            max_rows_per_page = 12
            i = 0
            while i < len(rows):
                chunk = rows[i:i+max_rows_per_page]
                need_tbl = 0.30*inch + (0.26+0.22*len(chunk))*inch
                page_no, y = _ensure_space(c, y, needed=2.20*inch, page_no=page_no,
                                          hdr_title=hdr_title, hdr_sub=hdr_sub, logo_bw=logo_bw, logo_gptw=logo_gptw)

                c.setFont("Helvetica-Bold", 10)
                c.setFillColor(colors.HexColor("#0B1E33"))
                c.drawString(MARGIN_X, y, "Detalle (conteo y porcentaje)")
                y -= 0.16 * inch

                y = _draw_table_simple(
                    c, y,
                    columns=["Opción", "Conteo", "%"],
                    rows=chunk,
                    col_widths=[4.80*inch, 1.00*inch, 0.90*inch],
                )
                i += max_rows_per_page

        else:
            # text question: summary only
            c.setFont("Helvetica", 9.2)
            c.setFillColor(colors.HexColor("#526581"))
            c.drawString(MARGIN_X, y, "Tipo texto: ver sección de Comentarios para el detalle.")
            y -= 0.28 * inch

        # spacing between questions
        y -= 0.10 * inch

    # ---------------- Comments (ALL) ----------------
    page_no, y = _new_page(c, page_no, hdr_title, hdr_sub, logo_bw, logo_gptw)
    y = _section_title(c, y, "Comentarios (todos)")

    comments = analytics.get("comments") or []
    if not comments:
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(MARGIN_X, y, "No hay comentarios registrados en esta campaña.")
        y -= 0.30 * inch
    else:
        for item in comments:
            # Each comment block (wrap + meta)
            dt = fmt_dt_local(item.get("submitted_at"), tz_name)
            area = _safe_text(item.get("area") or "-")
            shift = _safe_text(item.get("shift") or "-")
            qlbl = _safe_text(item.get("question") or "-")
            txt = _safe_text(item.get("text") or "")

            meta = f"{dt}  |  Área: {area}  |  Turno: {shift}"
            qline = f"Pregunta: {qlbl}"

            # estimate needed space:
            lines = _wrap_lines(txt, max_chars=92)
            needed = 0.18*inch + 0.18*inch + (0.16*inch * max(1, len(lines))) + 0.20*inch
            page_no, y = _ensure_space(c, y, needed=needed, page_no=page_no,
                                      hdr_title=hdr_title, hdr_sub=hdr_sub, logo_bw=logo_bw, logo_gptw=logo_gptw)

            # meta
            c.setFont("Helvetica-Bold", 9.2)
            c.setFillColor(colors.HexColor("#0B1E33"))
            c.drawString(MARGIN_X, y, meta)
            y -= 0.18 * inch

            c.setFont("Helvetica", 9.0)
            c.setFillColor(colors.HexColor("#102842"))
            c.drawString(MARGIN_X, y, qline[:120])
            y -= 0.18 * inch

            # text (wrapped)
            c.setFillColor(colors.HexColor("#102842"))
            c.setFont("Helvetica", 9.0)
            for ln in lines[:40]:  # safety cap
                c.drawString(MARGIN_X, y, ln)
                y -= 0.16 * inch

            # divider
            c.setStrokeColor(colors.HexColor("#E2EAF4"))
            c.setLineWidth(1)
            c.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)
            y -= 0.22 * inch

    # ---------------- Followups (ALL) ----------------
    page_no, y = _new_page(c, page_no, hdr_title, hdr_sub, logo_bw, logo_gptw)
    y = _section_title(c, y, "Solicitudes de seguimiento (opt-in)")

    followups = analytics.get("followups") or []
    if not followups:
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.HexColor("#526581"))
        c.drawString(MARGIN_X, y, "No hay solicitudes de contacto (opt-in) registradas.")
        y -= 0.30 * inch
    else:
        # We'll draw as a paginated table
        rows = []
        for r in followups:
            rows.append([
                fmt_dt_local(r.get("submitted_at"), tz_name),
                _safe_text(r.get("name") or "-")[:28],
                _safe_text(r.get("employee_no") or "-")[:18],
                _safe_text(r.get("phone") or "-")[:18],
                _safe_text(r.get("area") or "-")[:20],
                _safe_text(r.get("shift") or "-")[:10],
            ])

        cols = ["Fecha", "Nombre", "No. Empleado", "Tel.", "Área", "Turno"]
        colw = [1.15*inch, 1.55*inch, 1.05*inch, 0.90*inch, 1.45*inch, 0.65*inch]

        i = 0
        max_rows = 18
        while i < len(rows):
            chunk = rows[i:i+max_rows]
            needed = 0.45*inch + (0.26 + 0.22*len(chunk))*inch
            page_no, y = _ensure_space(c, y, needed=3.2*inch, page_no=page_no,
                                      hdr_title=hdr_title, hdr_sub=hdr_sub, logo_bw=logo_bw, logo_gptw=logo_gptw)

            y = _draw_table_simple(c, y, cols, chunk, colw)
            i += max_rows

            if i < len(rows):
                page_no, y = _new_page(c, page_no, hdr_title, hdr_sub, logo_bw, logo_gptw)

    _draw_footer(c, page_no)
    c.save()
    return buf.getvalue()
