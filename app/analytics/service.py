from collections import defaultdict
from datetime import datetime
from ..models import Response, Area


def compute_campaign_analytics(campaign):
    # Returns JSON ready for dashboard
    responses = Response.query.filter_by(campaign_id=campaign.id).order_by(Response.submitted_at.asc()).all()
    total = len(responses)

    # Time series by day
    by_day = defaultdict(int)
    by_area = defaultdict(int)
    by_shift = defaultdict(int)
    wants_followup = 0

    # question analytics
    q_stats = defaultdict(lambda: defaultdict(int))  # qid->answer->count

    schema = (campaign.snapshot_json or {}).get('schema') or {}
    questions = schema.get('questions') or []
    q_index = {q.get('id'): q for q in questions if q.get('id')}

    for r in responses:
        day = r.submitted_at.strftime('%Y-%m-%d')
        by_day[day] += 1
        if r.area_id:
            a = Area.query.get(r.area_id)
            by_area[a.name if a else str(r.area_id)] += 1
        if r.shift:
            by_shift[r.shift] += 1
        if r.wants_followup:
            wants_followup += 1

        ans = r.answers_json or {}
        for qid, val in ans.items():
            if isinstance(val, list):
                key = '|'.join([str(x) for x in val])
                q_stats[qid][key] += 1
            else:
                q_stats[qid][str(val)] += 1

    # Build question summaries
    q_summaries = []
    for qid, counts in q_stats.items():
        q = q_index.get(qid, {})
        q_summaries.append({
            'id': qid,
            'type': q.get('type'),
            'title': q.get('title', {}),
            'counts': dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
        })

    return {
        'campaign_id': campaign.id,
        'total_responses': total,
        'followup_optin': wants_followup,
        'series_by_day': dict(sorted(by_day.items())),
        'by_area': dict(sorted(by_area.items(), key=lambda x: x[1], reverse=True)),
        'by_shift': dict(sorted(by_shift.items(), key=lambda x: x[1], reverse=True)),
        'questions': q_summaries,
    }
