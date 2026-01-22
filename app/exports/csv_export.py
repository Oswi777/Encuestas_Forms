import csv
import io
from ..models import Response, Area


def build_responses_csv(campaign) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow([
        'response_id', 'campaign_id', 'campaign_name', 'submitted_at_utc', 'lang',
        'area', 'shift', 'source', 'wants_followup', 'contact_name', 'employee_no',
        'answers_json'
    ])

    rows = Response.query.filter_by(campaign_id=campaign.id).order_by(Response.submitted_at.asc()).all()
    for r in rows:
        area_name = None
        if r.area_id:
            a = Area.query.get(r.area_id)
            area_name = a.name if a else str(r.area_id)
        writer.writerow([
            r.id,
            campaign.id,
            campaign.name,
            r.submitted_at.isoformat() + 'Z',
            r.lang,
            area_name,
            r.shift,
            r.source,
            int(r.wants_followup),
            r.contact_name,
            r.employee_no,
            (r.answers_json or {}),
        ])

    return buf.getvalue().encode('utf-8')
