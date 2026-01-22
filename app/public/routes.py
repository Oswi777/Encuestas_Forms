from datetime import datetime
from flask import Blueprint, render_template, abort, request

from ..models import Campaign
from ..extensions import db

bp = Blueprint('public', __name__)

def sync_campaign_activity(now=None):
    """
    Synchronize Campaign.is_active based on start/end window (UTC naive).
    Rules:
      - If start_at is set and now < start_at -> inactive
      - If end_at is set and now > end_at -> inactive
      - Otherwise -> active
    """
    if now is None:
        now = datetime.utcnow()

    changed = False
    qs = Campaign.query.filter(
        (Campaign.start_at.isnot(None)) | (Campaign.end_at.isnot(None))
    ).all()

    for c in qs:
        # Determine should_be_active
        should_be_active = True

        if c.start_at and now < c.start_at:
            should_be_active = False
        if c.end_at and now > c.end_at:
            should_be_active = False

        if c.is_active != should_be_active:
            c.is_active = should_be_active
            changed = True

    if changed:
        db.session.commit()


@bp.get('/')
def landing():
    return render_template('public/landing.html')


@bp.get('/menu')
def menu():
    now = datetime.utcnow()

    # Sync scheduled activity (fixes "active" not updating and start not appearing)
    sync_campaign_activity(now)

    # Auto-refresh for kiosk (default 60s), disable with ?norefresh=1
    no_refresh = request.args.get('norefresh') == '1'
    refresh_seconds = 60 if not no_refresh else 0

    # Only active campaigns (already synced)
    campaigns = (
        Campaign.query
        .filter_by(is_active=True)
        .order_by(Campaign.created_at.desc())
        .all()
    )

    return render_template(
        'public/menu.html',
        campaigns=campaigns,
        refresh_seconds=refresh_seconds
    )


@bp.get('/c/<token>')
def campaign(token: str):
    c = Campaign.query.filter_by(token=token).first()
    if not c:
        abort(404)

    now = datetime.utcnow()
    sync_campaign_activity(now)

    # Reload is_active state after sync (optional but safe)
    if not c.is_active:
        abort(404)

    return render_template('public/campaign.html', campaign=c)
