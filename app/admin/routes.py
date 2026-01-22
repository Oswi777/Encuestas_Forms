import csv
import io
import json
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort
from flask_login import login_required, logout_user

from ..extensions import db
from ..models import Area, Survey, Campaign, Response


# Auto state sync for scheduled campaigns (UTC naive)
def sync_campaign_activity(now=None):
    if now is None:
        now = datetime.utcnow()
    changed = False
    qs = Campaign.query.filter((Campaign.start_at.isnot(None)) | (Campaign.end_at.isnot(None))).all()
    for c in qs:
        if c.end_at and now > c.end_at:
            if c.is_active:
                c.is_active = False
                changed = True
            continue
        if c.start_at and now >= c.start_at:
            if not c.is_active:
                c.is_active = True
                changed = True
    if changed:
        db.session.commit()

from ..services.analytics import compute_campaign_analytics
from ..services.pdf import build_campaign_pdf
from ..services.excel import import_areas_from_excel
from ..utils.time import local_naive_to_utc_naive, fmt_dt_local

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.get('/to-menu')
@login_required
def to_menu():
    """Log out admin session and redirect to the public menu.

    Requirement: moving from Admin panel to Menu must close the admin session.
    """
    logout_user()
    return redirect(url_for('public.menu'))


@bp.get('/')
@login_required
def dashboard():
    surveys = Survey.query.order_by(Survey.updated_at.desc()).limit(5).all()
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html', surveys=surveys, campaigns=campaigns)


# ---------- Areas ----------
@bp.get('/areas')
@login_required
def areas_list():
    areas = Area.query.order_by(Area.name.asc()).all()
    return render_template('admin/areas.html', areas=areas)


@bp.post('/areas')
@login_required
def areas_create():
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Nombre requerido.', 'error')
        return redirect(url_for('admin.areas_list'))
    if Area.query.filter_by(name=name).first():
        flash('Ya existe esa área.', 'error')
        return redirect(url_for('admin.areas_list'))
    a = Area(name=name, is_active=True)
    db.session.add(a)
    db.session.commit()
    flash('Área creada.', 'success')
    return redirect(url_for('admin.areas_list'))


@bp.post('/areas/<int:area_id>/toggle')
@login_required
def areas_toggle(area_id: int):
    a = Area.query.get_or_404(area_id)
    a.is_active = not a.is_active
    db.session.commit()
    return redirect(url_for('admin.areas_list'))


@bp.post('/areas/import')
@login_required
def areas_import():
    f = request.files.get('file')
    if not f:
        flash('Selecciona un archivo Excel.', 'error')
        return redirect(url_for('admin.areas_list'))
    try:
        created, skipped = import_areas_from_excel(f.stream)
        db.session.commit()
        flash(f'Importación completa. Nuevas: {created}, Omitidas: {skipped}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error importando: {e}', 'error')
    return redirect(url_for('admin.areas_list'))


# ---------- Surveys (templates) ----------
@bp.get('/surveys')
@login_required
def surveys_list():
    surveys = Survey.query.order_by(Survey.updated_at.desc()).all()
    return render_template('admin/surveys.html', surveys=surveys)


@bp.post('/surveys/seed')
@login_required
def surveys_seed():
    """Create baseline templates (Comedor/Transporte/Satisfacción general)."""
    created = 0
    skipped = 0

    def upsert(title: str, category: str, description: str, schema_json: dict):
        nonlocal created, skipped
        existing = Survey.query.filter_by(title=title).first()
        if existing:
            skipped += 1
            return
        s = Survey(title=title, category=category, description=description, schema_json=schema_json)
        db.session.add(s)
        created += 1

    # --- Shared settings ---
    base_settings = {
        'languages': ['es', 'en'],
        'settings': {
            'collect_area': True,
            'collect_shift': True,
            'collect_followup_opt_in': True,
        },
    }

    # --- Comedor ---
    comedor = {
        **base_settings,
        'questions': [
            {
                'id': 'q_satisfaccion',
                'type': 'likert',
                'scale': 5,
                'likert_preset': 'satisfaction',
                'required': True,
                'text': {
                    'es': '¿Qué tan satisfecho(a) estás con el comedor hoy?',
                    'en': 'How satisfied are you with the cafeteria today?'
                }
            },
            {
                'id': 'q_porque_excelente',
                'type': 'single',
                'required': True,
                'text': {'es': '¿Por qué fue excelente?', 'en': 'Why was it excellent?'},
                'options': [
                    {'value': 'sabor', 'label': {'es': 'Sabor', 'en': 'Taste'}},
                    {'value': 'rapidez', 'label': {'es': 'Rapidez', 'en': 'Speed'}},
                    {'value': 'limpieza', 'label': {'es': 'Limpieza', 'en': 'Cleanliness'}},
                    {'value': 'porciones', 'label': {'es': 'Porciones', 'en': 'Portions'}},
                ],
                'show_if': [{'question': 'q_satisfaccion', 'op': 'eq', 'value': '5'}]
            },
            {
                'id': 'q_motivo_inconformidad',
                'type': 'single',
                'required': True,
                'text': {'es': '¿Cuál fue el principal motivo de inconformidad?', 'en': 'What was the main issue?'},
                'options': [
                    {'value': 'sabor', 'label': {'es': 'Sabor', 'en': 'Taste'}},
                    {'value': 'tiempo', 'label': {'es': 'Tiempo de espera', 'en': 'Waiting time'}},
                    {'value': 'limpieza', 'label': {'es': 'Limpieza', 'en': 'Cleanliness'}},
                    {'value': 'temperatura', 'label': {'es': 'Temperatura de alimentos', 'en': 'Food temperature'}},
                    {'value': 'porciones', 'label': {'es': 'Porciones', 'en': 'Portions'}},
                ],
                # Show for 1 or 2
                'show_if': [{'question': 'q_satisfaccion', 'op': 'in', 'value': '1,2'}]
            },
            {
                'id': 'q_comentario',
                'type': 'text',
                'required': False,
                'text': {'es': 'Comentario (opcional)', 'en': 'Comment (optional)'},
                'show_if': [{'question': 'q_satisfaccion', 'op': 'in', 'value': '1,2'}]
            }
        ]
    }
    upsert(
        title='Plantilla — Comedor',
        category='COMEDOR',
        description='Plantilla base para medir satisfacción del comedor con ramificación.',
        schema_json=comedor,
    )

    # --- Transporte ---
    transporte = {
        **base_settings,
        'questions': [
            {
                'id': 'q_satisfaccion_trans',
                'type': 'likert',
                'scale': 5,
                'likert_preset': 'satisfaction',
                'required': True,
                'text': {
                    'es': '¿Qué tan satisfecho(a) estás con el transporte hoy?',
                    'en': 'How satisfied are you with the transportation service today?'
                }
            },
            {
                'id': 'q_porque_excelente_trans',
                'type': 'single',
                'required': True,
                'text': {'es': '¿Por qué fue excelente?', 'en': 'Why was it excellent?'},
                'options': [
                    {'value': 'puntualidad', 'label': {'es': 'Puntualidad', 'en': 'Punctuality'}},
                    {'value': 'trato', 'label': {'es': 'Trato del operador', 'en': 'Operator treatment'}},
                    {'value': 'limpieza', 'label': {'es': 'Limpieza', 'en': 'Cleanliness'}},
                    {'value': 'comodidad', 'label': {'es': 'Comodidad', 'en': 'Comfort'}},
                    {'value': 'seguridad', 'label': {'es': 'Seguridad', 'en': 'Safety'}},
                ],
                'show_if': [{'question': 'q_satisfaccion_trans', 'op': 'eq', 'value': '5'}]
            },
            {
                'id': 'q_motivo_inconformidad_trans',
                'type': 'single',
                'required': True,
                'text': {'es': '¿Cuál fue el principal problema?', 'en': 'What was the main issue?'},
                'options': [
                    {'value': 'tiempo', 'label': {'es': 'Tiempo / demoras', 'en': 'Time / delays'}},
                    {'value': 'trato', 'label': {'es': 'Trato del operador', 'en': 'Operator treatment'}},
                    {'value': 'limpieza', 'label': {'es': 'Limpieza', 'en': 'Cleanliness'}},
                    {'value': 'seguridad', 'label': {'es': 'Seguridad', 'en': 'Safety'}},
                    {'value': 'ruta', 'label': {'es': 'Ruta / paradas', 'en': 'Route / stops'}},
                ],
                'show_if': [{'question': 'q_satisfaccion_trans', 'op': 'in', 'value': '1,2'}]
            },
            {
                'id': 'q_comentario_trans',
                'type': 'text',
                'required': False,
                'text': {'es': 'Comentario (opcional)', 'en': 'Comment (optional)'},
                'show_if': [{'question': 'q_satisfaccion_trans', 'op': 'in', 'value': '1,2'}]
            }
        ]
    }
    upsert(
        title='Plantilla — Transporte',
        category='TRANSPORTE',
        description='Plantilla base para medir satisfacción del transporte con ramificación.',
        schema_json=transporte,
    )

    # --- Satisfacción general ---
    general_questions_es = [
        'Los líderes evitan favoritismo',
        'Los líderes cumplen sus promesas',
        'Los líderes reconocen el trabajo bien hecho y el esfuerzo adicional',
        'Siento que marco una diferencia aquí',
        'Este es un lugar psicológica y emocionalmente saludable/seguro para trabajar',
        'Quiero trabajar aquí por mucho tiempo',
        'Recibo un buen trato independientemente de mi posición en la organización',
        'Me siento orgulloso de lo que logramos',
        'En esta organización celebramos eventos especiales',
    ]
    general_qs = []
    for i, text_es in enumerate(general_questions_es, start=1):
        preset = 'agreement'
        if 'celebramos' in text_es.lower():
            preset = 'frequency'
        general_qs.append({
            'id': f'q_g_{i}',
            'type': 'likert',
            'scale': 5,
            'likert_preset': preset,
            'required': True,
            'text': {'es': text_es, 'en': ''}
        })
    general_qs.append({
        'id': 'q_g_comment',
        'type': 'text',
        'required': False,
        'text': {'es': 'Comentario (opcional)', 'en': 'Comment (optional)'}
    })
    satisfaccion_general = {**base_settings, 'questions': general_qs}
    upsert(
        title='Plantilla — Satisfacción general',
        category='GENERAL',
        description='Plantilla base de clima/satisfacción general (acuerdo y frecuencia).',
        schema_json=satisfaccion_general,
    )

    db.session.commit()
    flash(f'Plantillas base listas. Creadas: {created}, ya existentes: {skipped}', 'success')
    return redirect(url_for('admin.surveys_list'))


@bp.get('/surveys/new')
@login_required
def surveys_new():
    return render_template('admin/survey_edit.html', survey=None, shifts=current_app.config['SHIFTS'])


@bp.get('/surveys/<int:survey_id>/edit')
@login_required
def surveys_edit(survey_id: int):
    survey = Survey.query.get_or_404(survey_id)
    return render_template('admin/survey_edit.html', survey=survey, shifts=current_app.config['SHIFTS'])


@bp.post('/surveys/save')
@login_required
def surveys_save():
    survey_id = request.form.get('survey_id')
    title = (request.form.get('title') or '').strip()
    category = (request.form.get('category') or 'GENERAL').strip()[:60]
    description = (request.form.get('description') or '').strip()
    schema_text = request.form.get('schema_json') or ''

    try:
        schema_json = json.loads(schema_text) if schema_text else {}
    except Exception as e:
        flash(f'JSON inválido: {e}', 'error')
        return redirect(request.referrer or url_for('admin.surveys_list'))

    if not title:
        flash('Título requerido.', 'error')
        return redirect(request.referrer or url_for('admin.surveys_list'))

    if survey_id:
        s = Survey.query.get_or_404(int(survey_id))
        s.title = title
        s.category = category
        s.description = description
        s.schema_json = schema_json
        db.session.commit()
        flash('Encuesta actualizada.', 'success')
        return redirect(url_for('admin.surveys_list'))

    s = Survey(title=title, category=category, description=description, schema_json=schema_json)
    db.session.add(s)
    db.session.commit()
    flash('Encuesta creada.', 'success')
    return redirect(url_for('admin.surveys_list'))


@bp.post('/surveys/<int:survey_id>/delete')
@login_required
def surveys_delete(survey_id: int):
    s = Survey.query.get_or_404(survey_id)
    db.session.delete(s)
    db.session.commit()
    flash('Encuesta eliminada.', 'success')
    return redirect(url_for('admin.surveys_list'))


# ---------- Campaigns (lists) ----------
@bp.get('/campaigns')
@login_required
def campaigns_list():
    sync_campaign_activity(datetime.utcnow())
    # Filters
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = 10
    q = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or 'all').strip().lower()
    category = (request.args.get('category') or 'all').strip().upper()

    query = Campaign.query.join(Survey, Campaign.survey_id == Survey.id)

    if q:
        like = f"%{q}%"
        query = query.filter((Campaign.name.ilike(like)) | (Campaign.token.ilike(like)))

    if status == 'active':
        query = query.filter(Campaign.is_active.is_(True))
    elif status == 'inactive':
        query = query.filter(Campaign.is_active.is_(False))

    if category != 'ALL':
        query = query.filter(Survey.category == category)

    total = query.count()
    pages = max((total + per_page - 1) // per_page, 1)
    if page > pages:
        page = pages

    campaigns = query.order_by(Campaign.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    surveys = Survey.query.order_by(Survey.title.asc()).all()
    categories = [c[0] for c in Survey.query.with_entities(Survey.category).distinct().order_by(Survey.category.asc()).all()]

    return render_template(
        'admin/campaigns.html',
        campaigns=campaigns,
        surveys=surveys,
        categories=categories,
        filters={'q': q, 'status': status, 'category': category},
        pagination={'page': page, 'pages': pages, 'total': total, 'per_page': per_page},
    )



@bp.post('/campaigns')
@login_required
def campaigns_create():
    survey_id = int(request.form.get('survey_id') or 0)
    name = (request.form.get('name') or '').strip()
    require_area = True if (request.form.get('require_area') == 'on') else False
    require_shift = True if (request.form.get('require_shift') == 'on') else False
    start_at = request.form.get('start_at') or ''
    end_at = request.form.get('end_at') or ''

    if not survey_id or not name:
        flash('Selecciona encuesta y nombre de lista/campaña.', 'error')
        return redirect(url_for('admin.campaigns_list'))

    survey = Survey.query.get_or_404(survey_id)

    def parse_dt(s: str):
        if not s:
            return None
        try:
            return local_naive_to_utc_naive(datetime.fromisoformat(s), current_app.config.get('TIME_ZONE'))
        except Exception:
            return None

    c = Campaign(
        token=Campaign.new_token(),
        survey_id=survey.id,
        name=name,
        snapshot_json={
            'survey_id': survey.id,
            'title': survey.title,
            'description': survey.description,
            'category': survey.category,
            'schema': survey.schema_json,
        },
        is_active=False,
        start_at=parse_dt(start_at),
        end_at=parse_dt(end_at),
        require_area=require_area,
        require_shift=require_shift,
    )

    db.session.add(c)
    db.session.commit()
    flash('Campaña creada (snapshot). Ahora puedes activarla.', 'success')
    return redirect(url_for('admin.campaigns_list'))


@bp.post('/campaigns/<int:campaign_id>/toggle')
@login_required
def campaigns_toggle(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    c.is_active = not c.is_active
    db.session.commit()
    return redirect(url_for('admin.campaigns_list'))



@bp.get('/campaigns/<int:campaign_id>/edit')
@login_required
def campaigns_edit(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    surveys = Survey.query.order_by(Survey.title.asc()).all()
    return render_template('admin/campaign_edit.html', c=c, surveys=surveys)


@bp.post('/campaigns/<int:campaign_id>/edit')
@login_required
def campaigns_edit_post(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    c.name = (request.form.get('name') or c.name).strip()
    # allow changing linked survey only if no responses yet (preserves data integrity)
    survey_id = request.form.get('survey_id')
    if survey_id and (Response.query.filter_by(campaign_id=c.id).count() == 0):
        c.survey_id = int(survey_id)

    def _dt(name):
        v = request.form.get(name) or ''
        if not v:
            return None
        try:
            return local_naive_to_utc_naive(datetime.fromisoformat(v), current_app.config.get('TIME_ZONE'))
        except Exception:
            return None

    c.start_at = _dt('start_at')
    c.end_at = _dt('end_at')
    c.require_area = bool(request.form.get('require_area'))
    c.require_shift = bool(request.form.get('require_shift'))

    db.session.commit()
    flash('Campaña actualizada.', 'success')
    return redirect(url_for('admin.campaigns_list'))


@bp.get('/campaigns/<int:campaign_id>/report')
@login_required
def campaigns_report(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    return render_template('admin/report.html', campaign=c, shifts=current_app.config['SHIFTS'])


@bp.get('/api/campaigns/<int:campaign_id>/analytics')
@login_required
def api_campaign_analytics(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    data = compute_campaign_analytics(c)
    return data



@bp.get('/api/campaigns/<int:campaign_id>/responses')
@login_required
def api_campaign_responses(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = min(max(int(request.args.get('per_page', 10) or 10), 1), 50)

    q = Response.query.filter_by(campaign_id=c.id)
    total = q.count()
    pages = max((total + per_page - 1) // per_page, 1)
    if page > pages:
        page = pages

    rows = q.order_by(Response.submitted_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    items = []
    for r in rows:
        items.append({
            'id': r.id,
            'submitted_at': r.submitted_at.isoformat(),
            'submitted_at_mx': fmt_dt_local(r.submitted_at, current_app.config.get('TIME_ZONE')),
            'lang': r.lang,
            'area': (r.area.name if r.area else None),
            'shift': r.shift,
            'source': r.source,
            'wants_followup': bool(r.wants_followup),
        })

    return {
        'items': items,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
    }


def _extract_text_comments(snapshot: dict, answers: dict, lang: str) -> list:
    """Return list of {question, text} for non-empty text answers.

    Snapshot formats supported:
      - snapshot['questions'] (legacy)
      - snapshot['schema']['questions'] (current)

    Answer formats supported:
      - string (preferred)
      - dict with 'text' or 'value' (compat with older clients)
    """
    schema = snapshot.get('schema') if isinstance(snapshot, dict) else None
    questions = []
    if isinstance(snapshot, dict) and isinstance(snapshot.get('questions'), list):
        questions = snapshot.get('questions') or []
    elif isinstance(schema, dict) and isinstance(schema.get('questions'), list):
        questions = schema.get('questions') or []

    qmeta = {str(q.get('id')): q for q in questions if isinstance(q, dict)}
    out = []

    for qid, val in (answers or {}).items():
        q = qmeta.get(str(qid))
        if not q:
            continue

        qtype = (q.get('type') or '').lower()
        if qtype not in ('text', 'textarea', 'comment'):
            continue

        text_val = None
        if isinstance(val, str):
            text_val = val
        elif isinstance(val, dict):
            if isinstance(val.get('text'), str):
                text_val = val.get('text')
            elif isinstance(val.get('value'), str):
                text_val = val.get('value')

        if not text_val:
            continue

        text_val = str(text_val).strip()
        if not text_val:
            continue

        qtext = q.get('text') or {}
        if isinstance(qtext, dict):
            qlabel = qtext.get(lang) or qtext.get('es') or qtext.get('en')
        else:
            qlabel = str(qtext)

        out.append({'question': qlabel or str(qid), 'text': text_val})

    return out

@bp.get('/api/campaigns/<int:campaign_id>/comments')
@login_required
def api_campaign_comments(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = min(max(int(request.args.get('per_page', 10) or 10), 1), 50)

    # pull latest responses and extract text comments
    q = Response.query.filter_by(campaign_id=c.id).order_by(Response.submitted_at.desc())
    rows = q.all()
    comments = []
    for r in rows:
        for it in _extract_text_comments(c.snapshot_json or {}, r.answers_json or {}, r.lang or 'es'):
            comments.append({
                'response_id': r.id,
                'submitted_at': r.submitted_at.isoformat(),
            'submitted_at_mx': fmt_dt_local(r.submitted_at, current_app.config.get('TIME_ZONE')),
                'lang': r.lang,
                'area': (r.area.name if r.area else None),
                'shift': r.shift,
                'question': it['question'],
                'text': it['text'],
            })

    total = len(comments)
    pages = max((total + per_page - 1) // per_page, 1)
    if page > pages:
        page = pages
    start = (page - 1) * per_page
    items = comments[start:start + per_page]

    return {
        'items': items,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
    }


@bp.get('/api/campaigns/<int:campaign_id>/followups')
@login_required
def api_campaign_followups(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = min(max(int(request.args.get('per_page', 10) or 10), 1), 50)

    q = Response.query.filter_by(campaign_id=c.id).filter(Response.wants_followup.is_(True))
    total = q.count()
    pages = max((total + per_page - 1) // per_page, 1)
    if page > pages:
        page = pages

    rows = q.order_by(Response.submitted_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    items = []
    for r in rows:
        items.append({
            'response_id': r.id,
            'submitted_at': r.submitted_at.isoformat(),
            'submitted_at_mx': fmt_dt_local(r.submitted_at, current_app.config.get('TIME_ZONE')),
            'lang': r.lang,
            'area': (r.area.name if r.area else None),
            'shift': r.shift,
            'name': r.contact_name,
            'employee_no': r.employee_no,
        })

    return {
        'items': items,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
    }


@bp.get('/campaigns/<int:campaign_id>/export.csv')
@login_required
def campaigns_export_csv(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    rows = Response.query.filter_by(campaign_id=c.id).order_by(Response.submitted_at.desc()).all()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        'response_id', 'submitted_at', 'lang', 'area', 'shift', 'wants_followup', 'contact_name', 'employee_no', 'source', 'answers_json'
    ])
    for r in rows:
        writer.writerow([
            r.id,
            r.submitted_at.isoformat(sep=' ', timespec='seconds'),
            r.lang,
            r.area.name if r.area else '',
            r.shift or '',
            '1' if r.wants_followup else '0',
            r.contact_name or '',
            r.employee_no or '',
            r.source or '',
            json.dumps(r.answers_json, ensure_ascii=False),
        ])

    data = out.getvalue().encode('utf-8')
    return send_file(
        io.BytesIO(data),
        mimetype='text/csv; charset=utf-8',
        download_name=f"campaign_{c.id}_responses.csv",
        as_attachment=True,
    )


@bp.get('/campaigns/<int:campaign_id>/export.pdf')
@login_required
def campaigns_export_pdf(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    pdf_bytes = build_campaign_pdf(c)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        download_name=f"campaign_{c.id}_report.pdf",
        as_attachment=True,
    )


@bp.post('/campaigns/<int:campaign_id>/delete')
@login_required
def campaigns_delete(campaign_id: int):
    c = Campaign.query.get_or_404(campaign_id)
    # Responses should remain? For simplicity we delete campaign only if no responses.
    if Response.query.filter_by(campaign_id=c.id).count() > 0:
        flash('No se puede eliminar: la campaña ya tiene respuestas.', 'error')
        return redirect(url_for('admin.campaigns_list'))
    db.session.delete(c)
    db.session.commit()
    flash('Campaña eliminada.', 'success')
    return redirect(url_for('admin.campaigns_list'))
