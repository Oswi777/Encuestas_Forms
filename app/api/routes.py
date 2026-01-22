import io
from datetime import datetime

from flask import Blueprint, request, abort, current_app, send_file

from ..extensions import db
from ..models import Campaign, Response, Area
from ..services.qr import make_qr_png

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.get('/areas')
def list_areas():
    """Return active Areas for public survey UI.

    The public survey runtime uses this endpoint to populate the Area selector
    when a campaign has require_area enabled.
    """
    areas = Area.query.filter_by(is_active=True).order_by(Area.name.asc()).all()
    return {
        'items': [{'id': a.id, 'name': a.name} for a in areas]
    }


@bp.get('/campaign/<token>')
def get_campaign(token: str):
    c = Campaign.query.filter_by(token=token).first()
    if not c or not c.is_active:
        abort(404)
    now = datetime.utcnow()
    if c.start_at and now < c.start_at:
        abort(404)
    if c.end_at and now > c.end_at:
        abort(404)

    return {
        'token': c.token,
        'campaign_id': c.id,
        'name': c.name,
        'require_area': c.require_area,
        'require_shift': c.require_shift,
        'shifts': current_app.config['SHIFTS'],
        'snapshot': c.snapshot_json,
    }


@bp.post('/submit/<token>')
def submit(token: str):
    c = Campaign.query.filter_by(token=token).first()
    if not c or not c.is_active:
        abort(404)

    payload = request.get_json(silent=True) or {}
    lang = (payload.get('lang') or current_app.config.get('DEFAULT_LANGUAGE', 'es'))[:8]

    area_id = payload.get('area_id')
    shift = payload.get('shift')
    answers = payload.get('answers') or {}
    wants_followup = bool(payload.get('wants_followup'))
    contact_name = (payload.get('contact_name') or '').strip()[:200]
    employee_no = (payload.get('employee_no') or '').strip()[:50]
    source = (payload.get('source') or 'kiosko')[:20]

    if c.require_area:
        if not area_id:
            return {'error': 'area_required'}, 400
        area = Area.query.get(int(area_id))
        if not area or not area.is_active:
            return {'error': 'invalid_area'}, 400

    if c.require_shift:
        if not shift:
            return {'error': 'shift_required'}, 400
        if shift not in current_app.config['SHIFTS']:
            return {'error': 'invalid_shift'}, 400
    else:
        if shift and shift not in current_app.config['SHIFTS']:
            return {'error': 'invalid_shift'}, 400

    if wants_followup:
        if not contact_name or not employee_no:
            return {'error': 'contact_required'}, 400
    else:
        contact_name = None
        employee_no = None

    r = Response(
        campaign_id=c.id,
        lang=lang,
        area_id=int(area_id) if area_id else None,
        shift=shift,
        wants_followup=wants_followup,
        contact_name=contact_name,
        employee_no=employee_no,
        answers_json=answers,
        user_agent=(request.headers.get('User-Agent') or '')[:300],
        source=source,
    )
    db.session.add(r)
    db.session.commit()

    return {'ok': True, 'id': r.id}


@bp.get('/qr/<token>.png')
def qr_png(token: str):
    c = Campaign.query.filter_by(token=token).first()
    if not c:
        abort(404)

    base_url = request.args.get('base_url')
    if not base_url:
        # Fallback: build from request
        base_url = request.host_url.rstrip('/')
    url = f"{base_url}/c/{c.token}"

    png_bytes = make_qr_png(url)
    return send_file(io.BytesIO(png_bytes), mimetype='image/png', download_name=f"qr_{c.token}.png")
